#!/usr/bin/env python3
"""
根据输入的四指（不含拇指）关节1角度，利用 Excel(G/H列)的映射关系计算关节2角度，并通过 ROS2 发布到仿真。

功能:
- 读取 Excel: 驱动器行程与角度关系表.xls
  使用 G3:G2003 -> 关节1角度，H3:H2003 -> 关节2角度
- 将 Excel 角度(deg)转换为仿真用角度(rad): rad_sim = pi - deg2rad(deg)
  注: 该方向转换与之前在临时脚本中的处理一致，便于与 URDF 关节正向一致
- 使用线性插值 (numpy.interp) 构建 j2 = f(j1)
- 支持一次性发布(--once) 或按频率重复发布(--rate)
- 支持统一角度(--angle) 或针对单指分别指定(--index/--middle/--ring/--little)
- 支持 hand=left/right 与对应 model 名称参数
- 话题格式: /model/<model>/joint/<joint>/cmd_pos (std_msgs/Float64)

示例:
  右手四指统一角度(弧度)一次性发布:
    python3 scripts/fingers_from_joint1_and_publish.py --hand right --model ftp_right_hand --angle 0.6 --unit rad --once

  左手每根手指单独角度(角度制)循环发布:
    python3 scripts/fingers_from_joint1_and_publish.py --hand left --model ftp_left_hand \
      --index 30 --middle 35 --ring 25 --little 20 --unit deg --rate 10

若未检测到 rclpy，将只打印即将发布的话题和值，不实际发布。
"""
import argparse
import math
from pathlib import Path
from typing import Tuple, List, Dict

import numpy as np

try:
    import pandas as pd
except Exception:
    pd = None

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Float64
except Exception:
    rclpy = None


def load_mapping_from_excel(xls_path: Path) -> Tuple[np.ndarray, np.ndarray]:
    """从 Excel 读取映射数据，返回 (j1_rad_sim_sorted, j2_rad_sim_sorted)。
    - 读取 G3:G2003 (iloc 2:2003, col 6) 作为 j1_deg
    - 读取 H3:H2003 (iloc 2:2003, col 7) 作为 j2_deg
    - 转换为仿真角度: rad_sim = pi - deg2rad(deg)
    - 排序并去除 NaN
    """
    if pd is None:
        raise RuntimeError('pandas 不可用，请在已安装 pandas 的环境中运行或先安装 pandas')

    df = pd.read_excel(str(xls_path), header=None)
    j1_deg = pd.to_numeric(df.iloc[2:2003, 6], errors='coerce').values  # G 列
    j2_deg = pd.to_numeric(df.iloc[2:2003, 7], errors='coerce').values  # H 列

    mask = ~(np.isnan(j1_deg) | np.isnan(j2_deg))
    j1_deg = j1_deg[mask]
    j2_deg = j2_deg[mask]
    if len(j1_deg) < 2:
        raise ValueError('Excel 有效数据太少，无法构建插值映射')

    # 方向转换：与仿真一致（0 为伸直，增大为弯曲）
    j1_rad_sim = np.pi - np.deg2rad(j1_deg)
    j2_rad_sim = np.pi - np.deg2rad(j2_deg)

    # 限制在合理范围（可选）：[0, pi/2]，避免奇异数据干扰
    valid = (j1_rad_sim >= 0.0) & (j1_rad_sim <= (np.pi / 2 + 1e-6))
    j1_rad_sim = j1_rad_sim[valid]
    j2_rad_sim = j2_rad_sim[valid]

    # 按 j1 升序排序，便于插值
    order = np.argsort(j1_rad_sim)
    j1_sorted = j1_rad_sim[order]
    j2_sorted = j2_rad_sim[order]

    # 去重（若 j1 有重复值）
    uniq_x, idx = np.unique(j1_sorted, return_index=True)
    uniq_y = j2_sorted[idx]
    return uniq_x, uniq_y


def build_interpolator(j1_x: np.ndarray, j2_y: np.ndarray):
    """构建线性插值函数，允许边界外线性外推。"""
    def f(x: float) -> float:
        # numpy.interp 不支持外推，这里做成线性外推
        if x <= j1_x[0]:
            # 外推到左边界
            if len(j1_x) >= 2:
                x0, x1 = j1_x[0], j1_x[1]
                y0, y1 = j2_y[0], j2_y[1]
                if x1 != x0:
                    slope = (y1 - y0) / (x1 - x0)
                    return float(y0 + slope * (x - x0))
            return float(j2_y[0])
        if x >= j1_x[-1]:
            # 外推到右边界
            if len(j1_x) >= 2:
                x0, x1 = j1_x[-2], j1_x[-1]
                y0, y1 = j2_y[-2], j2_y[-1]
                if x1 != x0:
                    slope = (y1 - y0) / (x1 - x0)
                    return float(y1 + slope * (x - x1))
            return float(j2_y[-1])
        return float(np.interp(x, j1_x, j2_y))
    return f


FINGERS = ['index', 'middle', 'ring', 'little']


def joint_name(hand: str, finger: str, idx: int) -> str:
    """生成关节名: left_index_1_joint / right_index_2_joint ..."""
    assert finger in FINGERS and idx in (1, 2)
    return f"{hand}_{finger}_{idx}_joint"


def resolve_topics(model: str, hand: str) -> Dict[str, Tuple[str, str]]:
    """返回每根手指的 (topic_j1, topic_j2)。"""
    topics = {}
    for finger in FINGERS:
        j1 = joint_name(hand, finger, 1)
        j2 = joint_name(hand, finger, 2)
        t1 = f"/model/{model}/joint/{j1}/cmd_pos"
        t2 = f"/model/{model}/joint/{j2}/cmd_pos"
        topics[finger] = (t1, t2)
    return topics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xls', default=str(Path(__file__).resolve().parents[1] / '驱动器行程与角度关系表.xls'))
    parser.add_argument('--hand', choices=['left', 'right'], required=True, help='控制左手或右手')
    parser.add_argument('--model', default='ftp_right_hand', help='仿真模型名（/model/<model>）')
    parser.add_argument('--unit', choices=['rad', 'deg'], default='rad', help='输入角度单位')
    parser.add_argument('--angle', type=float, default=None, help='四指统一关节1角度（与 --index 等不能同时使用）')
    parser.add_argument('--index', type=float, default=None, help='食指关节1角度')
    parser.add_argument('--middle', type=float, default=None, help='中指关节1角度')
    parser.add_argument('--ring', type=float, default=None, help='无名指关节1角度')
    parser.add_argument('--little', type=float, default=None, help='小指关节1角度')
    parser.add_argument('--once', action='store_true', help='发布一次后退出')
    parser.add_argument('--rate', type=float, default=10.0, help='非 --once 模式下的发布频率 Hz')
    args = parser.parse_args()

    xls_path = Path(args.xls)
    if not xls_path.exists():
        print('ERROR: Excel 文件不存在:', xls_path)
        return

    # 加载映射并构建插值器
    j1_x, j2_y = load_mapping_from_excel(xls_path)
    f_map = build_interpolator(j1_x, j2_y)

    # 解析输入角度
    inputs: Dict[str, float] = {}
    if args.angle is not None:
        for f in FINGERS:
            inputs[f] = float(args.angle)
    else:
        provided = {k: getattr(args, k) for k in FINGERS if getattr(args, k) is not None}
        if not provided:
            print('ERROR: 请通过 --angle 统一设置或使用 --index/--middle/--ring/--little 指定至少一个角度')
            return
        # 没提供的用第一个已提供值补齐
        default_val = next(iter(provided.values()))
        for f in FINGERS:
            inputs[f] = float(provided.get(f, default_val))

    # 单位转换：输入 -> 仿真角度
    def to_sim_rad(v):
        val_rad = v if args.unit == 'rad' else math.radians(v)
        return float(val_rad)

    # 准备 ROS2 话题
    topics = resolve_topics(args.model, args.hand)

    # 计算并准备要发布的消息
    desired_msgs = {}
    for finger, a1_in in inputs.items():
        a1_sim = to_sim_rad(a1_in)
        a2_sim = f_map(a1_sim)
        t1, t2 = topics[finger]
        desired_msgs[finger] = (t1, a1_sim, t2, a2_sim)

    # 打印预览
    print('将发布如下关节命令 (单位: rad):')
    for finger in FINGERS:
        t1, a1, t2, a2 = desired_msgs[finger]
        print(f'  {finger:6s} -> {t1}: {a1:.6f} ; {t2}: {a2:.6f}')

    if rclpy is None:
        print('\nNOTE: 未检测到 rclpy（ROS2 Python），当前仅打印，不实际发布。请在已 source ROS2 的终端中运行以发布。')
        return

    # 发布
    rclpy.init()
    node = Node('fingers_from_joint1_publisher')

    pubs: Dict[str, Tuple] = {}
    for finger in FINGERS:
        t1, _, t2, _ = desired_msgs[finger]
        p1 = node.create_publisher(Float64, t1, 10)
        p2 = node.create_publisher(Float64, t2, 10)
        pubs[finger] = (p1, p2)

    try:
        if args.once:
            for finger in FINGERS:
                p1, p2 = pubs[finger]
                _, a1, _, a2 = desired_msgs[finger]
                m1 = Float64(); m1.data = float(a1)
                m2 = Float64(); m2.data = float(a2)
                p1.publish(m1)
                p2.publish(m2)
            print('已发布一次。')
        else:
            rate = float(args.rate)
            print(f'以 {rate} Hz 发布，Ctrl-C 结束...')
            import time
            while rclpy.ok():
                for finger in FINGERS:
                    p1, p2 = pubs[finger]
                    _, a1, _, a2 = desired_msgs[finger]
                    m1 = Float64(); m1.data = float(a1)
                    m2 = Float64(); m2.data = float(a2)
                    p1.publish(m1)
                    p2.publish(m2)
                rclpy.spin_once(node, timeout_sec=0.0)
                time.sleep(1.0 / max(rate, 1e-6))
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
