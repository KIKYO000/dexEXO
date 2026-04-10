#!/usr/bin/env python3
"""
五个 Dynamixel XL330-M288T 舵机的力反馈控制（BLE 触摸数据闭环）
通过 BLE 接收 STM32 发送的 JSON: {"touch_sensors": [..]}，用于力反馈闭环
"""
import sys
import time
import threading
import socket
import json
import re
import asyncio
import signal
from typing import List, Tuple

from dynamixel_sdk import *
from bleak import BleakClient

# ===== BLE 配置 =====
DEVICE_ADDRESSES = [
	"F0:FD:45:02:85:B3",  # 设备1 MAC地址
	"F0:FD:45:02:67:3B",  # 设备2 MAC地址
]
TX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # 发送数据的特征 UUID
RX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # 接收数据的特征 UUID

# ===== 调试开关 =====
BLE_DEBUG = False
BLE_DEBUG_INTERVAL = 1.0

# ===== 力反馈方向 =====
# +1: touch>target 时后退，touch<target 时前进
# -1: 反向
FORCE_DIRECTION = 1

# ===== 几何力比例 =====
# 绳索拉力约为指尖力的倍数（例如 2.0 表示拉力约为指尖力的两倍）
GEOMETRY_FORCE_RATIO = 2.0

# ===== 目标力 -> 电流缩放 =====
# 数值越大，寻觅拉力越明显（注意不要超过电流限制）
FORCE_TO_CURRENT_SCALE = 10.0

# ===== 主动寻觅/顺应参数 =====
SEEK_CURRENT_SIGN = 1
SEEK_STABLE_POS_DELTA = 3
SEEK_STABLE_COUNT = 8
COMPLY_FORCE_DELTA = 0.3
COMPLY_RELEASE_CURRENT = 20
COMPLY_RELEASE_HYSTERESIS = 0.1
SEEK_HOLD_MIN_FORCE = 0.6

# ===== 硬件串口 & 舵机参数 =====
DEVICENAME = "/dev/ttyAMA0"
BAUDRATE = 57600
PROTOCOL_VERSION = 2.0
DXL_IDS = [1, 2, 3, 4, 5]

# XL330 Control Table Addresses
ADDR_OPERATING_MODE = 11
ADDR_CURRENT_LIMIT = 38
ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_CURRENT = 102
ADDR_GOAL_POSITION = 116
ADDR_PRESENT_CURRENT = 126
ADDR_PRESENT_POSITION = 132
ADDR_PROFILE_VELOCITY = 112
ADDR_PROFILE_ACCELERATION = 108

# Operating Modes
OP_CURRENT_BASED_POSITION = 5
OP_CURRENT_CONTROL = 0


class TouchDataStore:
	"""保存 BLE 触摸数据的线程安全存储"""

	def __init__(self, size: int) -> None:
		self._lock = threading.Lock()
		self._values = [0.0] * size
		self._last_update = 0.0
		self._last_payload = {}

	def update_from_json(self, payload: dict) -> None:
		if not isinstance(payload, dict):
			return
		if "touch_sensors" in payload:
			sensors = payload.get("touch_sensors")
		elif "force" in payload:
			sensors = [payload.get("force")]
		else:
			return
		if isinstance(sensors, list):
			if len(sensors) == 0:
				return
			values = sensors
		else:
			values = [sensors]

		try:
			value_list = [float(v) for v in values]
		except (TypeError, ValueError):
			return

		with self._lock:
			if len(value_list) == 1:
				self._values = [value_list[0]] * len(self._values)
			else:
				for i in range(min(len(self._values), len(value_list))):
					self._values[i] = value_list[i]
			self._last_update = time.time()
			self._last_payload = payload

	def get_values(self) -> Tuple[List[float], float]:
		with self._lock:
			values = list(self._values)
			last_update = self._last_update
		age = time.time() - last_update if last_update > 0 else float("inf")
		return values, age


class JsonStreamParser:
	"""处理 BLE 分包/粘包 JSON 数据"""

	def __init__(self) -> None:
		self._buffer = ""
		self._decoder = json.JSONDecoder()

	def feed(self, text: str) -> List[dict]:
		self._buffer += text
		outputs: List[dict] = []

		while self._buffer:
			self._buffer = self._buffer.lstrip()
			if not self._buffer:
				break
			if not self._buffer.startswith("{") and not self._buffer.startswith("["):
				next_obj = self._buffer.find("{")
				if next_obj == -1:
					break
				self._buffer = self._buffer[next_obj:]
				continue
			try:
				obj, idx = self._decoder.raw_decode(self._buffer)
				if isinstance(obj, dict):
					outputs.append(obj)
				self._buffer = self._buffer[idx:]
				continue
			except json.JSONDecodeError:
				if "\n" in self._buffer:
					line, self._buffer = self._buffer.split("\n", 1)
					line = line.strip()
					if not line:
						continue
					try:
						outputs.append(json.loads(line))
					except json.JSONDecodeError:
						continue
				else:
					break
		return outputs


def extract_touch_sensors(text: str) -> List[float]:
	"""从原始文本中兜底提取 touch_sensors 数值"""
	results: List[float] = []
	pattern = re.compile(r'"touch_sensors"\s*:\s*\[([^\]]+)\]')
	for match in pattern.findall(text):
		parts = [p.strip() for p in match.split(",") if p.strip()]
		try:
			values = [float(p) for p in parts]
		except ValueError:
			continue
		if values:
			results.extend(values)
	return results


def extract_force(text: str) -> List[float]:
	"""兜底提取 force 数值"""
	match = re.search(r'"force"\s*:\s*([0-9.+-eE]+)', text)
	if not match:
		return []
	try:
		return [float(match.group(1))]
	except ValueError:
		return []


def print_payload(payload: dict) -> None:
	"""按 finger.py 的格式输出 JSON"""
	try:
		print(json.dumps(payload, ensure_ascii=False))
	except Exception:
		print(payload)


class ServoController:
	"""单个舵机的控制器"""

	def __init__(self, servo_id: int):
		self.servo_id = servo_id
		self.targetForceN = 0.0
		self.kN_per_mA = 0.8
		self.hysteresisN = 1.5
		self.currentLimit_mA = 450
		self.touchMode = False
		self.holdMode = False
		self.freeModeActive = False
		self.goal_pos = 0
		self.home_pos = 0
		self.admittance_gain = 15.0
		self.admittance_gain_positive = 25.0
		self.max_step_per_loop = 25
		self.calMin_mA = 5
		self.mA_window = []
		self.window_size = 10
		self.state = "IDLE"
		self.command_updated = False
		self.target_current_mA = 0.0
		self.last_pos = 0
		self.stable_count = 0
		self.hold_force = 0.0
		self.last_target_force = 0.0


servo_controllers = [ServoController(servo_id) for servo_id in DXL_IDS]
touch_store = TouchDataStore(len(DXL_IDS))
portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)
dxl_lock = threading.Lock()
running = True


def read2ByteSigned(servo_id: int, addr: int) -> int:
	with dxl_lock:
		val, res, err = packetHandler.read2ByteTxRx(portHandler, servo_id, addr)
	if res != COMM_SUCCESS:
		print(f"[舵机{servo_id}] 读取错误: {packetHandler.getTxRxResult(res)}")
	elif err != 0:
		print(f"[舵机{servo_id}] 硬件错误: {packetHandler.getRxPacketError(err)}")
	if val > 32767:
		val -= 65536
	return val


def read4ByteSigned(servo_id: int, addr: int) -> int:
	with dxl_lock:
		val, res, err = packetHandler.read4ByteTxRx(portHandler, servo_id, addr)
	if res != COMM_SUCCESS:
		print(f"[舵机{servo_id}] 读取错误: {packetHandler.getTxRxResult(res)}")
	elif err != 0:
		print(f"[舵机{servo_id}] 硬件错误: {packetHandler.getRxPacketError(err)}")
	if val > 2147483647:
		val -= 4294967296
	return val


def write1Byte(servo_id: int, addr: int, val: int) -> None:
	with dxl_lock:
		res, _ = packetHandler.write1ByteTxRx(portHandler, servo_id, addr, val)
	if res != COMM_SUCCESS:
		print(f"[舵机{servo_id}] 写入错误: {packetHandler.getTxRxResult(res)}")


def write2Byte(servo_id: int, addr: int, val: int) -> None:
	with dxl_lock:
		res, _ = packetHandler.write2ByteTxRx(portHandler, servo_id, addr, val)
	if res != COMM_SUCCESS:
		print(f"[舵机{servo_id}] 写入错误: {packetHandler.getTxRxResult(res)}")


def write2ByteSigned(servo_id: int, addr: int, val: int) -> None:
	if val < 0:
		val = (1 << 16) + val
	write2Byte(servo_id, addr, val)


def write4Byte(servo_id: int, addr: int, val: int) -> None:
	with dxl_lock:
		res, _ = packetHandler.write4ByteTxRx(portHandler, servo_id, addr, int(val))
	if res != COMM_SUCCESS:
		print(f"[舵机{servo_id}] 写入错误: {packetHandler.getTxRxResult(res)}")


def torqueOn(servo_id: int) -> None:
	write1Byte(servo_id, ADDR_TORQUE_ENABLE, 1)


def torqueOff(servo_id: int) -> None:
	write1Byte(servo_id, ADDR_TORQUE_ENABLE, 0)


def set_operating_mode(servo_id: int, mode: int) -> None:
	torqueOff(servo_id)
	write1Byte(servo_id, ADDR_OPERATING_MODE, mode)
	torqueOn(servo_id)


def write_goal_current(servo_id: int, current_mA: float) -> None:
	current_cmd = int(round(current_mA))
	write2ByteSigned(servo_id, ADDR_GOAL_CURRENT, current_cmd)


def enterFreeMode(controller: ServoController) -> None:
	torqueOff(controller.servo_id)
	controller.freeModeActive = True
	print(f"[舵机{controller.servo_id}] 自由模式")


def exitFreeMode(controller: ServoController) -> None:
	ppos = read4ByteSigned(controller.servo_id, ADDR_PRESENT_POSITION)
	torqueOn(controller.servo_id)
	controller.goal_pos = ppos
	write4Byte(controller.servo_id, ADDR_GOAL_POSITION, controller.goal_pos)
	controller.freeModeActive = False
	print(f"[舵机{controller.servo_id}] 退出自由模式")


def parse_command(buf: str) -> None:
	global running

	try:
		buf = buf.replace("：", ":").strip().upper()

		if buf.startswith("N:"):
			parts = buf.split(":")
			if len(parts) >= 3:
				try:
					servo_idx = int(parts[1]) - 1
					force_val = float(parts[2])

					if 0 <= servo_idx < len(servo_controllers):
						controller = servo_controllers[servo_idx]
						if force_val == 0:
							controller.targetForceN = 0
							controller.touchMode = False
							controller.state = "IDLE"
							print(f"[舵机{controller.servo_id}] 目标力=0，进入自由模式")
						else:
							if controller.freeModeActive:
								exitFreeMode(controller)
							controller.targetForceN = abs(force_val)
							controller.touchMode = True
							controller.command_updated = True
							print(f"[舵机{controller.servo_id}] 目标力={controller.targetForceN}N")
					else:
						print(f"[错误] 舵机索引超出范围: {servo_idx+1}")
				except ValueError:
					print("[错误] 无效的数值格式")
			else:
				print("[错误] 格式: N:舵机ID:力值  例如: N:1:5")

		elif buf.startswith("NALL:"):
			try:
				force_val = float(buf[5:])
				for controller in servo_controllers:
					if force_val == 0:
						controller.targetForceN = 0
						controller.touchMode = False
						controller.state = "IDLE"
					else:
						if controller.freeModeActive:
							exitFreeMode(controller)
						controller.targetForceN = abs(force_val)
						controller.touchMode = True
						controller.command_updated = True
				print(f"[全部] 目标力={force_val}N")
			except ValueError:
				print("[错误] 无效的数值格式")

		elif buf.startswith("HOLD:"):
			try:
				servo_idx = int(buf[5:]) - 1
				if 0 <= servo_idx < len(servo_controllers):
					servo_controllers[servo_idx].holdMode = True
					print(f"[舵机{servo_idx+1}] 保持模式")
			except ValueError:
				print("[错误] 无效的舵机ID")

		elif buf.startswith("FREE:"):
			try:
				servo_idx = int(buf[5:]) - 1
				if 0 <= servo_idx < len(servo_controllers):
					controller = servo_controllers[servo_idx]
					controller.targetForceN = 0
					controller.touchMode = False
					controller.holdMode = False
					enterFreeMode(controller)
			except ValueError:
				print("[错误] 无效的舵机ID")

		elif buf == "STATUS":
			values, age = touch_store.get_values()
			print("\n=== 五舵机状态 ===")
			print(f"[BLE] touch_sensors age={age:.2f}s values={values}")
			for controller in servo_controllers:
				ppos = read4ByteSigned(controller.servo_id, ADDR_PRESENT_POSITION)
				pcur = read2ByteSigned(controller.servo_id, ADDR_PRESENT_CURRENT)
				print(
					f"舵机{controller.servo_id}: 位置={ppos}, 电流={pcur}mA, 目标力={controller.targetForceN:.2f}N"
				)

		elif buf.startswith("CAL:"):
			parts = buf.split(":")
			if len(parts) >= 3:
				try:
					servo_idx = int(parts[1]) - 1
					real_force = float(parts[2])
					if 0 <= servo_idx < len(servo_controllers):
						controller = servo_controllers[servo_idx]
						pcur = read2ByteSigned(controller.servo_id, ADDR_PRESENT_CURRENT)
						if abs(pcur) >= controller.calMin_mA:
							new_k = abs(real_force / float(pcur))
							if new_k > 0.1:
								print(
									f"[错误] 舵机{controller.servo_id} 标定系数过大 ({new_k:.6f})! 忽略。"
								)
								print("       原因: 电流相对于力太小。请确保舵机真的在用力。")
							else:
								old_k = controller.kN_per_mA
								controller.kN_per_mA = new_k
								print(
									f"[舵机{controller.servo_id}] kN_per_mA: {old_k:.6f} -> {new_k:.6f}"
								)
						else:
							print(
								f"[舵机{controller.servo_id}] 电流太小(<{controller.calMin_mA}mA)，请加大外力"
							)
				except ValueError:
					print("[错误] 无效的数值格式")

		elif buf.startswith("KN:"):
			parts = buf.split(":")
			if len(parts) >= 3:
				try:
					servo_idx = int(parts[1]) - 1
					new_k = float(parts[2])
					if 0 <= servo_idx < len(servo_controllers):
						servo_controllers[servo_idx].kN_per_mA = new_k
						print(f"[舵机{servo_idx+1}] kN_per_mA set to {new_k:.6f}")
				except ValueError:
					print("Invalid Value")

		elif buf == "HELP":
			print("\n=== 五舵机控制指令 ===")
			print("N:ID:力值    - 设定单个舵机目标力 (例: N:1:5)")
			print("NALL:力值    - 设定所有舵机目标力 (例: NALL:5)")
			print("KN:ID:系数   - 手动设定力系数 (例: KN:1:0.025)")
			print("HOLD:ID      - 保持舵机当前位置 (例: HOLD:1)")
			print("FREE:ID      - 舵机进入自由模式 (例: FREE:1)")
			print("CAL:ID:力值  - 标定舵机力系数 (例: CAL:1:3)")
			print("STATUS       - 查看所有舵机状态")
			print("EXIT         - 退出程序")

		elif buf == "EXIT":
			running = False
			print("正在退出...")

		else:
			print(f"[未知指令] {buf}")

	except Exception as e:
		print(f"[命令错误] {e}")


def wifi_server_thread() -> None:
	HOST = "0.0.0.0"
	PORT = 8888

	server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	try:
		server_socket.bind((HOST, PORT))
		server_socket.listen(1)
		print(f"=== WiFi Server Listening on {HOST}:{PORT} ===")

		while running:
			try:
				server_socket.settimeout(1.0)
				conn, addr = server_socket.accept()
				print(f"[WiFi] Connected by {addr}")
				try:
					while running:
						data = conn.recv(1024)
						if not data:
							break
						cmd = data.decode("utf-8").strip()
						if cmd:
							print(f"[WiFi] Recv: {cmd}")
							parse_command(cmd)
							conn.sendall(b"CMD_RECEIVED\n")
				except Exception as e:
					print(f"[WiFi] Connection Error: {e}")
				finally:
					conn.close()
					print(f"[WiFi] Disconnected {addr}")
			except socket.timeout:
				continue
			except Exception as e:
				if running:
					print(f"[WiFi] Server Error: {e}")
	except Exception as e:
		print(f"[WiFi] Fatal Error: {e}")
	finally:
		server_socket.close()


def input_thread() -> None:
	print("=== 命令输入就绪 (输入 HELP 查看指令) ===")
	while running:
		try:
			line = sys.stdin.readline()
			if not line:
				break
			buf = line.strip()
			if not buf:
				continue
			parse_command(buf)
		except Exception as e:
			print(f"[输入错误] {e}")


async def ble_session(address: str, parser: JsonStreamParser) -> None:
	print(f"[BLE] 尝试连接: {address}")

	async with BleakClient(address) as client:
		if not client.is_connected:
			raise RuntimeError(f"无法连接到 {address}")
		print(f"[BLE] 已连接: {address}")
		raw_buffer = ""
		last_debug = 0.0

		def notification_handler(_, data: bytearray) -> None:
			try:
				text = bytes(data).decode("utf-8", errors="ignore")
				nonlocal last_debug
				if BLE_DEBUG and time.time() - last_debug >= BLE_DEBUG_INTERVAL:
					print(f"[BLE RAW] {text.strip()}")
					last_debug = time.time()
				nonlocal raw_buffer
				raw_buffer += text
				payloads = parser.feed(text)
				for payload in payloads:
					if BLE_DEBUG and time.time() - last_debug >= BLE_DEBUG_INTERVAL:
						print(f"[BLE JSON] {payload}")
						print_payload(payload)
						last_debug = time.time()
					touch_store.update_from_json(payload)
				values = extract_touch_sensors(raw_buffer)
				if not values:
					values = extract_force(raw_buffer)
				if values:
					if BLE_DEBUG and time.time() - last_debug >= BLE_DEBUG_INTERVAL:
						print(f"[BLE FALLBACK] touch_sensors={values}")
					payload = {"touch_sensors": values}
					if BLE_DEBUG and time.time() - last_debug >= BLE_DEBUG_INTERVAL:
						print_payload(payload)
						last_debug = time.time()
					touch_store.update_from_json(payload)
					raw_buffer = ""
				if len(raw_buffer) > 512:
					raw_buffer = raw_buffer[-512:]
			except Exception as e:
				print(f"[BLE] 解析错误: {e}")

		await client.start_notify(RX_CHAR_UUID, notification_handler)
		try:
			while running:
				await asyncio.sleep(0.5)
		finally:
			await client.stop_notify(RX_CHAR_UUID)


async def ble_main() -> None:
	parser = JsonStreamParser()
	while running:
		for addr in DEVICE_ADDRESSES:
			if not running:
				break
			try:
				await ble_session(addr, parser)
			except Exception as e:
				print(f"[BLE] 连接失败 {addr}: {e}")
				await asyncio.sleep(1.0)
		await asyncio.sleep(1.0)


def ble_thread() -> None:
	try:
		asyncio.run(ble_main())
	except Exception as e:
		print(f"[BLE] 线程退出: {e}")


def setup() -> None:
	if portHandler.openPort():
		print("串口打开成功")
	else:
		print("串口打开失败")
		sys.exit(1)

	if portHandler.setBaudRate(BAUDRATE):
		print("波特率设置成功")
	else:
		print("波特率设置失败")
		sys.exit(1)

	for controller in servo_controllers:
		servo_id = controller.servo_id
		model_number, res, err = packetHandler.ping(portHandler, servo_id)
		if res != COMM_SUCCESS:
			print(f"[舵机{servo_id}] Ping 失败: {packetHandler.getTxRxResult(res)}")
			continue
		print(f"[舵机{servo_id}] Ping 成功, Model: {model_number}")

		torqueOff(servo_id)
		write1Byte(servo_id, ADDR_OPERATING_MODE, OP_CURRENT_BASED_POSITION)
		write2Byte(servo_id, ADDR_CURRENT_LIMIT, controller.currentLimit_mA)
		write4Byte(servo_id, ADDR_PROFILE_VELOCITY, 200)
		write4Byte(servo_id, ADDR_PROFILE_ACCELERATION, 100)
		torqueOn(servo_id)

		controller.home_pos = read4ByteSigned(servo_id, ADDR_PRESENT_POSITION)
		controller.goal_pos = controller.home_pos
		write4Byte(servo_id, ADDR_GOAL_POSITION, controller.goal_pos)

		time.sleep(0.05)

	print("\n五舵机力反馈系统就绪")


def loop() -> None:
	global running
	last_print = time.time()

	while running:
		try:
			current_time = time.time()
			touch_values, touch_age = touch_store.get_values()

			for idx, controller in enumerate(servo_controllers):
				if controller.holdMode or controller.freeModeActive:
					continue
				if not controller.touchMode:
					continue

				if controller.servo_id != 2:
					continue

				if controller.targetForceN != controller.last_target_force:
					controller.command_updated = True
					controller.last_target_force = controller.targetForceN

				present_pos = read4ByteSigned(controller.servo_id, ADDR_PRESENT_POSITION)
				present_mA = read2ByteSigned(controller.servo_id, ADDR_PRESENT_CURRENT)

				controller.mA_window.append(present_mA)
				if len(controller.mA_window) > controller.window_size:
					controller.mA_window.pop(0)
				filt_mA = sum(controller.mA_window) / len(controller.mA_window)

				feedbackN = touch_values[0] if touch_values else 0.0

				if controller.command_updated:
					controller.command_updated = False
					controller.state = "SEEK"
					controller.stable_count = 0
					controller.last_pos = present_pos
					controller.hold_force = feedbackN
					target_current = (
						controller.targetForceN
						* GEOMETRY_FORCE_RATIO
						* FORCE_TO_CURRENT_SCALE
						/ controller.kN_per_mA
					)
					controller.target_current_mA = min(
						abs(target_current), controller.currentLimit_mA
					)
					set_operating_mode(controller.servo_id, OP_CURRENT_CONTROL)

				if controller.state == "SEEK":
					write_goal_current(
						controller.servo_id,
						SEEK_CURRENT_SIGN * controller.target_current_mA,
					)
					if abs(present_pos - controller.last_pos) <= SEEK_STABLE_POS_DELTA:
						controller.stable_count += 1
					else:
						controller.stable_count = 0
					controller.last_pos = present_pos
					if controller.stable_count >= SEEK_STABLE_COUNT:
						if feedbackN >= SEEK_HOLD_MIN_FORCE:
							controller.state = "HOLD"
							controller.hold_force = feedbackN
							write_goal_current(controller.servo_id, 0)

				elif controller.state == "HOLD":
					write_goal_current(controller.servo_id, 0)
					if feedbackN - controller.hold_force > COMPLY_FORCE_DELTA:
						controller.state = "COMPLY"

				elif controller.state == "COMPLY":
					release_current = -SEEK_CURRENT_SIGN * COMPLY_RELEASE_CURRENT
					write_goal_current(controller.servo_id, release_current)
					if feedbackN <= controller.hold_force + COMPLY_RELEASE_HYSTERESIS:
						controller.state = "HOLD"
						write_goal_current(controller.servo_id, 0)

			if current_time - last_print > 1.0:
				active_servos = [c for c in servo_controllers if c.touchMode]
				if active_servos:
					print(
						f"\n[状态] 活动舵机: {len(active_servos)} | touch_age={touch_age:.2f}s | touch={touch_values}"
					)
					for c in active_servos:
						ppos = read4ByteSigned(c.servo_id, ADDR_PRESENT_POSITION)
						pcur = read2ByteSigned(c.servo_id, ADDR_PRESENT_CURRENT)
						feedbackN = touch_values[0] if touch_values else 0.0
						err = feedbackN - c.targetForceN
						print(
							f"  舵机{c.servo_id}: POS={ppos}, CUR={pcur}mA, "
							f"state={c.state}, feedbackN={feedbackN:.2f}N, "
							f"target={c.targetForceN:.1f}N, err={err:.2f}N"
						)
				last_print = current_time

			time.sleep(0.005)

		except KeyboardInterrupt:
			signal_handler(signal.SIGINT, None)
			break
		except Exception as e:
			print(f"[循环错误] {e}")


def signal_handler(signum, frame) -> None:
	global running
	if running:
		print("\n接收到 Ctrl+C，正在停止...")
	running = False


if __name__ == "__main__":
	try:
		signal.signal(signal.SIGINT, signal_handler)
		setup()

		t_input = threading.Thread(target=input_thread, daemon=True)
		t_input.start()

		t_wifi = threading.Thread(target=wifi_server_thread, daemon=True)
		t_wifi.start()

		t_ble = threading.Thread(target=ble_thread, daemon=True)
		t_ble.start()

		loop()

	except KeyboardInterrupt:
		print("\n程序被用户中断")
	except Exception as e:
		print(f"[致命错误] {e}")
	finally:
		print("\n正在关闭舵机...")
		for controller in servo_controllers:
			torqueOff(controller.servo_id)
		portHandler.closePort()
		print("程序已退出")
