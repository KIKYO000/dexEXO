#!/usr/bin/env python3
"""Unitree G1 Inspire 灵巧手触觉桥接 -> 发送目标力到树莓派。

从 DDS 话题 rt/inspire_hand/touch/* 读取触觉数据，转换为目标力，
再通过 TCP 向树莓派发送 N:2:NUM 指令。

需要安装:
- unitree_sdk2_python
- inspire_hand_sdk (或包含 inspire_hand_touch idl 的模块)
"""
import argparse
import socket
import sys
import time
from typing import Iterable, Optional


def mean(values: Iterable[int]) -> Optional[float]:
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def extract_touch_value(msg, finger: str, region: str) -> Optional[float]:
    key_map = {
        ("pinky", "tip"): "fingerone_tip_touch",
        ("pinky", "top"): "fingerone_top_touch",
        ("pinky", "palm"): "fingerone_palm_touch",
        ("ring", "tip"): "fingertwo_tip_touch",
        ("ring", "top"): "fingertwo_top_touch",
        ("ring", "palm"): "fingertwo_palm_touch",
        ("middle", "tip"): "fingerthree_tip_touch",
        ("middle", "top"): "fingerthree_top_touch",
        ("middle", "palm"): "fingerthree_palm_touch",
        ("index", "tip"): "fingerfour_tip_touch",
        ("index", "top"): "fingerfour_top_touch",
        ("index", "palm"): "fingerfour_palm_touch",
        ("thumb", "tip"): "fingerfive_tip_touch",
        ("thumb", "top"): "fingerfive_top_touch",
        ("thumb", "middle"): "fingerfive_middle_touch",
        ("thumb", "palm"): "fingerfive_palm_touch",
    }
    key = key_map.get((finger, region))
    if not key:
        return None
    values = getattr(msg, key, None)
    if values is None:
        return None
    return mean(values)


def main() -> int:
    parser = argparse.ArgumentParser(description="Unitree Inspire touch -> force bridge")
    parser.add_argument("--pi-ip", required=True, help="树莓派 IP")
    parser.add_argument("--port", type=int, default=8888, help="树莓派 TCP 端口")
    parser.add_argument("--topic", default="rt/inspire_hand/touch/r", help="DDS 触觉话题")
    parser.add_argument("--finger", default="index", help="pinky/ring/middle/index/thumb")
    parser.add_argument("--region", default="tip", help="tip/top/palm/middle")
    parser.add_argument("--scale", type=float, default=1.0, help="触觉值->N 比例")
    parser.add_argument("--offset", type=float, default=0.0, help="触觉值->N 偏移")
    parser.add_argument("--interval", type=float, default=0.1, help="发送周期秒")
    args = parser.parse_args()

    try:
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
    except Exception as exc:  # noqa: BLE001
        print("未找到 unitree_sdk2_python，请先安装: pip install -e unitree_sdk2_python")
        print(f"导入错误: {exc}")
        return 1

    try:
        from inspire_hand_sdk.hand_idl.inspire_hand_touch import inspire_hand_touch
    except Exception:
        try:
            from unitree_sdk2py.idl.inspire_hand_touch import inspire_hand_touch  # type: ignore
        except Exception as exc:  # noqa: BLE001
            print("未找到 inspire_hand_touch IDL，请确认 inspire_hand_sdk 已安装")
            print(f"导入错误: {exc}")
            return 1

    ChannelFactoryInitialize(0)
    sub = ChannelSubscriber(args.topic, inspire_hand_touch)
    sub.Init()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((args.pi_ip, args.port))
    print(f"已连接树莓派 {args.pi_ip}:{args.port}，订阅 {args.topic}")

    last_send = 0.0
    while True:
        msg = sub.Read()
        if msg is None:
            time.sleep(0.01)
            continue
        now = time.time()
        if now - last_send < args.interval:
            continue
        value = extract_touch_value(msg, args.finger, args.region)
        if value is None:
            continue
        target_force = value * args.scale + args.offset
        cmd = f"N:2:{target_force:.2f}"
        sock.sendall(cmd.encode("utf-8"))
        print(f"Sent: {cmd}")
        last_send = now


if __name__ == "__main__":
    raise SystemExit(main())
