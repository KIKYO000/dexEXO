#!/usr/bin/env python3
"""
输入: 大拇指关节2的角度（deg 或 rad）
流程:
 1. 读取 thumb_mapping_coeffs.json 中 f2,f3,f4 (x -> angle_deg)
 2. 求解 f2(x) = angle2 得到 x（使用 numpy.roots 反解三次多项式）
 3. 计算 angle3 = f3(x), angle4 = f4(x)
 4. 发布 angle2/3/4 到 ros2 话题: /model/<model>/joint/<joint>/cmd_pos (std_msgs/Float64)

如果没有 rclpy，会输出要发布的主题和值而不实际发布。

示例:
  ./thumb_from_joint2_and_publish.py --angle 140 --input-unit deg --output-unit deg --model ftp_right_hand --joint2 right_thumb_2_joint --joint3 right_thumb_3_joint --joint4 right_thumb_4_joint --once

"""
import argparse
import json
import math
from pathlib import Path
import numpy as np

try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Float64
except Exception:
    rclpy = None


def poly_eval(coeffs, x):
    # coeffs: [a,b,c,d] (deg3 highest->lowest)
    return coeffs[0]*x**3 + coeffs[1]*x**2 + coeffs[2]*x + coeffs[3]


def invert_cubic(coeffs, y_target, x_range=None):
    # Solve a*x^3 + b*x^2 + c*x + d = y_target
    a,b,c,d = coeffs
    # polynomial coefficients for roots: a x^3 + b x^2 + c x + (d - y_target) = 0
    p = [a, b, c, d - y_target]
    roots = np.roots(p)
    real_roots = [r.real for r in roots if abs(r.imag) < 1e-6]
    if not real_roots:
        # broaden tolerance
        real_roots = [r.real for r in roots if abs(r.imag) < 1e-3]
    if not real_roots:
        return None, roots
    # If x_range provided, prefer roots inside range
    if x_range is not None:
        filtered = [xr for xr in real_roots if (x_range[0] - 1e-8) <= xr <= (x_range[1] + 1e-8)]
        if filtered:
            # if multiple, choose closest to midpoint
            mid = 0.5*(x_range[0] + x_range[1])
            best = min(filtered, key=lambda rr: abs(rr-mid))
            return best, roots
    # otherwise pick the root closest to zero (or to mean)
    best = min(real_roots, key=lambda rr: abs(rr))
    return best, roots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--angle', type=float, required=True, help='Input angle for joint2 (deg or rad per --input-unit)')
    parser.add_argument('--input-unit', choices=['deg','rad'], default='deg')
    parser.add_argument('--output-unit', choices=['deg','rad'], default='deg')
    parser.add_argument('--coeffs', default=str(Path(__file__).resolve().parents[1] / 'thumb_mapping_coeffs.json'))
    parser.add_argument('--model', default='ftp_right_hand')
    parser.add_argument('--joint2', default='right_thumb_2_joint')
    parser.add_argument('--joint3', default='right_thumb_3_joint')
    parser.add_argument('--joint4', default='right_thumb_4_joint')
    parser.add_argument('--topic-template', default=None, help='Full topic template, use {model} {joint} placeholders e.g. /model/{model}/joint/{joint}/cmd_pos')
    parser.add_argument('--once', action='store_true', help='Publish once and exit')
    parser.add_argument('--rate', type=float, default=10.0, help='Publish rate when not --once (Hz)')
    parser.add_argument('--xls', default=str(Path(__file__).resolve().parents[1] / '驱动器行程与角度关系表.xls'), help='(optional) Excel to get stroke range')
    args = parser.parse_args()

    coeffs_path = Path(args.coeffs)
    if not coeffs_path.exists():
        print('ERROR: coeffs file not found:', coeffs_path)
        return
    coeffs = json.loads(coeffs_path.read_text())
    f2 = coeffs.get('joint2')
    f3 = coeffs.get('joint3')
    f4 = coeffs.get('joint4')
    if f2 is None or f3 is None or f4 is None:
        print('ERROR: coeffs missing joint2/3/4 in file')
        return

    # convert input angle to degrees (coeffs map to degrees as saved)
    angle_in = args.angle
    if args.input_unit == 'rad':
        angle_deg = math.degrees(angle_in)
    else:
        angle_deg = angle_in

    # try to get x range from excel if exists
    x_range = None
    x_mean = None
    x_data = None
    xls_path = Path(args.xls)
    if xls_path.exists():
        try:
            import pandas as pd
            df = pd.read_excel(xls_path, header=None)
            start_row = 2
            end_row = 2003
            # assume column 0 is stroke like before
            xcol = pd.to_numeric(df.iloc[start_row:end_row, 0], errors='coerce')
            x_data = xcol.dropna().values
            if len(x_data) > 0:
                x_range = (float(np.min(x_data)), float(np.max(x_data)))
                x_mean = float(np.mean(x_data))
        except Exception as e:
            # ignore
            pass

    x, raw_roots = invert_cubic(f2, angle_deg, x_range=x_range)
    if x is None:
        print('ERROR: failed to invert cubic for joint2. Raw roots:', raw_roots)
        # still try to choose best real approx
        real_roots = [r.real for r in raw_roots if abs(r.imag) < 1e-3]
        if real_roots:
            x = real_roots[0]
        else:
            return

    angle2_deg = poly_eval(f2, x)
    angle3_deg = poly_eval(f3, x)
    angle4_deg = poly_eval(f4, x)

    # convert outputs if needed
    if args.output_unit == 'rad':
        angle2_out = math.radians(angle2_deg)
        angle3_out = math.radians(angle3_deg)
        angle4_out = math.radians(angle4_deg)
    else:
        angle2_out = angle2_deg
        angle3_out = angle3_deg
        angle4_out = angle4_deg

    # prepare topics
    if args.topic_template:
        topic2 = args.topic_template.format(model=args.model, joint=args.joint2)
        topic3 = args.topic_template.format(model=args.model, joint=args.joint3)
        topic4 = args.topic_template.format(model=args.model, joint=args.joint4)
    else:
        topic2 = f'/model/{args.model}/joint/{args.joint2}/cmd_pos'
        topic3 = f'/model/{args.model}/joint/{args.joint3}/cmd_pos'
        topic4 = f'/model/{args.model}/joint/{args.joint4}/cmd_pos'

    print('Resolved x=', x)
    print('Computed angles (deg): joint2={:.6f}, joint3={:.6f}, joint4={:.6f}'.format(angle2_deg, angle3_deg, angle4_deg))
    print('Publishing values (', args.output_unit, '):')
    print(topic2, angle2_out)
    print(topic3, angle3_out)
    print(topic4, angle4_out)

    if rclpy is None:
        print('\nNOTE: ROS2 (rclpy) not available - not publishing. Run in ROS2-enabled environment to publish.')
        return

    # else publish using rclpy
    rclpy.init()
    node = Node('thumb_from_joint2_publisher')
    pub2 = node.create_publisher(Float64, topic2, 10)
    pub3 = node.create_publisher(Float64, topic3, 10)
    pub4 = node.create_publisher(Float64, topic4, 10)

    msg2 = Float64()
    msg3 = Float64()
    msg4 = Float64()
    msg2.data = float(angle2_out)
    msg3.data = float(angle3_out)
    msg4.data = float(angle4_out)

    try:
        if args.once:
            pub2.publish(msg2)
            pub3.publish(msg3)
            pub4.publish(msg4)
            print('Published once.')
        else:
            rate = args.rate
            print(f'Publishing at {rate} Hz until Ctrl-C...')
            import time
            while rclpy.ok():
                pub2.publish(msg2)
                pub3.publish(msg3)
                pub4.publish(msg4)
                rclpy.spin_once(node, timeout_sec=1.0/rate)
                time.sleep(1.0/rate)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
