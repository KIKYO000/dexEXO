#!/usr/bin/env python3
"""Given thumb joint2 angle, compute joint3 and joint4 using the new mapping and publish via ROS2.

Loads `data/thumb_mapping_new_coeffs.json` created by the fit script.
Usage examples:
  # compute & print only
  python3 publish_from_joint2_new.py --angle 140 --input-unit deg --print-only --model ftp_right_hand

  # publish (requires sourced ROS2 and rclpy available)
  python3 publish_from_joint2_new.py --angle 2.3 --input-unit rad --model ftp_right_hand
"""
import argparse
from pathlib import Path
import json
import numpy as np
import math

parser = argparse.ArgumentParser()
parser.add_argument('--angle', type=float, required=True, help='Joint2 angle (value)')
parser.add_argument('--input-unit', choices=['deg','rad'], default='deg')
parser.add_argument('--output-unit', choices=['deg','rad'], default='deg')
parser.add_argument('--model', default='ftp_right_hand', help='model name in Gazebo to publish to')
parser.add_argument('--once', action='store_true', help='Publish once and exit')
parser.add_argument('--print-only', action='store_true', help='Do not attempt ROS2 publish; just print values')
args = parser.parse_args()

ROOT = Path(__file__).resolve().parents[2]
coeff_file = ROOT / 'data' / 'thumb_mapping_new_coeffs.json'
if not coeff_file.exists():
    raise SystemExit(f'Coefficients file not found: {coeff_file}. Run fit script first.')

data = json.loads(coeff_file.read_text())
def poly_eval(coeffs, x):
    return np.polyval(coeffs, x)

# If input is rad convert to deg for mapping (we assume mapping is in degrees)
angle_in = args.angle
if args.input_unit == 'rad':
    angle_in = math.degrees(angle_in)

# invert joint2 polynomial: find stroke x such that poly(x) == angle_in
coeffs2 = data['joint2']['coeffs']
stroke_range = data.get('stroke_range', [0.0, 1.0])

def invert_cubic(coeffs, y_target, stroke_range):
    # coeffs: [a,b,c,d] for a*x^3 + b*x^2 + c*x + d
    a, b, c, d = coeffs
    # form polynomial a x^3 + b x^2 + c x + (d - y_target) = 0
    p = [a, b, c, d - y_target]
    roots = np.roots(p)
    real_roots = [r.real for r in roots if abs(r.imag) < 1e-6]
    # choose root within stroke range
    for r in real_roots:
        if stroke_range[0] - 1e-6 <= r <= stroke_range[1] + 1e-6:
            return float(r)
    # otherwise pick the real root closest to midpoint
    if real_roots:
        mid = 0.5*(stroke_range[0] + stroke_range[1])
        real_roots.sort(key=lambda x: abs(x-mid))
        return float(real_roots[0])
    raise RuntimeError('No valid real root found for inversion')

stroke_x = invert_cubic(coeffs2, angle_in, stroke_range)

# compute joint3/4 from stroke
coeffs3 = data['joint3']['coeffs']
coeffs4 = data['joint4']['coeffs']
joint2 = angle_in
joint3 = poly_eval(coeffs3, stroke_x)
joint4 = poly_eval(coeffs4, stroke_x)

# convert back to requested output units
def to_output(val_deg):
    return math.radians(val_deg) if args.output_unit=='rad' else float(val_deg)

out2 = to_output(joint2)
out3 = to_output(joint3)
out4 = to_output(joint4)

topics = [
    (f'/model/{args.model}/joint/{args.model.split("_")[1]}_thumb_2_joint/cmd_pos' if '_' in args.model else f'/model/{args.model}/joint/left_thumb_2_joint/cmd_pos', out2),
    (f'/model/{args.model}/joint/{args.model.split("_")[1]}_thumb_3_joint/cmd_pos' if '_' in args.model else f'/model/{args.model}/joint/left_thumb_3_joint/cmd_pos', out3),
    (f'/model/{args.model}/joint/{args.model.split("_")[1]}_thumb_4_joint/cmd_pos' if '_' in args.model else f'/model/{args.model}/joint/left_thumb_4_joint/cmd_pos', out4),
]

print('Resolved stroke x =', stroke_x)
print('Computed angles (joint2,joint3,joint4) in', args.output_unit, ':', out2, out3, out4)
for t,v in topics:
    print('Will publish ->', t, v)

if args.print_only:
    print('print-only mode: skipping ROS2 publish')
    raise SystemExit(0)

# Try to publish using rclpy
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Float64
except Exception:
    print('rclpy not available: cannot publish; run with --print-only to only print values')
    raise

class PublisherNode(Node):
    def __init__(self):
        super().__init__('thumb_pub_new')
        self.pubs = [self.create_publisher(Float64, t, 10) for t,_ in topics]
    def publish_once(self):
        msgs = [Float64(data=float(v)) for _,v in topics]
        for p,m in zip(self.pubs, msgs):
            p.publish(m)

def main():
    rclpy.init()
    node = PublisherNode()
    if args.once:
        node.publish_once()
        print('Published once (ROS2)')
    else:
        try:
            # publish periodically until Ctrl-C
            import time
            while rclpy.ok():
                node.publish_once()
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
