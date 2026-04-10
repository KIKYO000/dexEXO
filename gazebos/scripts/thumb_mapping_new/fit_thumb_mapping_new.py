#!/usr/bin/env python3
"""Fit cubic polynomials stroke->angle for thumb joints 2/3/4 and save coefficients.

Reads Excel `驱动器行程与角度关系表.xls` from repository root (or current dir).
Expects stroke in column A (index 0) rows 3..2003 (iloc 2:2003) and joints in C/D/E (indices 2,3,4).
Saves JSON to `data/thumb_mapping_new_coeffs.json` with structure:
  { "joint2": {"coeffs":[a,b,c,d]}, "joint3":..., "joint4":..., "stroke_range":[min,max] }

This is a standalone new mapping (does not reuse existing mapping files).
"""
from pathlib import Path
import json
import sys
import numpy as np
try:
    import pandas as pd
except Exception:
    print('ERROR: pandas is required to run this script')
    raise

ROOT = Path(__file__).resolve().parents[1]
XL_PATHS = [ROOT / '驱动器行程与角度关系表.xls', ROOT / '..' / '驱动器行程与角度关系表.xls', Path('驱动器行程与角度关系表.xls')]
xls = None
for p in XL_PATHS:
    if p.exists():
        xls = p
        break

if xls is None:
    print('ERROR: Excel file 驱动器行程与角度关系表.xls not found in expected locations')
    sys.exit(2)

print('Using Excel:', xls)
df = pd.read_excel(xls, header=None)
start_row = 2
end_row = 2003

# stroke column A -> index 0
stroke = pd.to_numeric(df.iloc[start_row:end_row, 0], errors='coerce').values
cols = {'joint2':2, 'joint3':3, 'joint4':4}

results = {}
valid_mask = np.isfinite(stroke)
for name, col_idx in cols.items():
    y = pd.to_numeric(df.iloc[start_row:end_row, col_idx], errors='coerce').values
    mask = valid_mask & np.isfinite(y)
    xs = stroke[mask]
    ys = y[mask]
    if len(xs) < 4:
        print(f'Not enough data for {name} (found {len(xs)} samples)')
        continue
    coeffs = np.polyfit(xs, ys, 3)
    # compute residual RMS
    y_fit = np.polyval(coeffs, xs)
    rms = np.sqrt(np.mean((y_fit - ys)**2))
    results[name] = {'coeffs': coeffs.tolist(), 'rms': float(rms)}
    print(f'Fitted {name}: rms={rms:.4f}, coeffs={coeffs}')

stroke_valid = stroke[np.isfinite(stroke)]
if stroke_valid.size == 0:
    print('ERROR: no valid stroke values found')
    sys.exit(3)

results['stroke_range'] = [float(np.nanmin(stroke_valid)), float(np.nanmax(stroke_valid))]

out_dir = ROOT / 'data'
out_dir.mkdir(exist_ok=True)
out_file = out_dir / 'thumb_mapping_new_coeffs.json'
out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
print('Saved coefficients to', out_file)
