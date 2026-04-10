#!/usr/bin/env python3
import sys
import json
from pathlib import Path
import numpy as np
try:
    import pandas as pd
except Exception as e:
    print('PANDAS_MISSING')
    raise

xls = Path('../驱动器行程与角度关系表.xls')
if not xls.exists():
    xls = Path('驱动器行程与角度关系表.xls')
if not xls.exists():
    print('ERROR: Excel file not found at expected paths')
    sys.exit(2)

# Try to read the workbook
df = pd.read_excel(xls, header=None)
print('Excel shape:', df.shape)
# Show first 6 rows
print('Sample rows (0-5):')
print(df.iloc[0:6, 0:10].to_string(index=False))

# We assume columns C,D,E correspond to indices 2,3,4 and rows 3-2003 -> iloc 2:2003
start_row = 2
end_row = 2003
cols = [2,3,4]
sub = df.iloc[start_row:end_row, cols].dropna()
print('\nSelected data shape:', sub.shape)
# If there is an X (actuator stroke) in column 0 or 1, try to detect it
x_candidates = []
for c in [0,1]:
    col = df.iloc[start_row:end_row, c]
    if not col.isnull().all():
        x_candidates.append((c, col.values))

if x_candidates:
    # choose first candidate
    xcol_idx = x_candidates[0][0]
    x = pd.to_numeric(df.iloc[start_row:end_row, xcol_idx], errors='coerce').values
    print(f'Using column {xcol_idx} as X values (stroke)')
else:
    # fallback: use index (row number)
    x = np.arange(start_row, start_row + len(sub))
    print('No explicit X column found; using row index as X')

results = {}
for i, joint_col in enumerate(cols, start=2):
    y = pd.to_numeric(df.iloc[start_row:end_row, joint_col], errors='coerce').values
    # create mask where both x and y are finite numbers
    mask = np.isfinite(x) & np.isfinite(y)
    x_masked = x[mask]
    y_masked = y[mask]
    if len(x_masked) < 4:
        print(f'Not enough data for column index {joint_col}')
        continue
    # Fit cubic
    coeffs = np.polyfit(x_masked, y_masked, 3)
    # Store with highest->lowest
    results[f'joint{ i }'] = coeffs.tolist()
    print(f'Joint col {joint_col} -> coeffs (deg3):', coeffs)

# Save results
out = Path('../thumb_mapping_coeffs.json')
out2 = Path('thumb_mapping_coeffs.json')
out.write_text(json.dumps(results, indent=2))
print('\nSaved coefficients to', out)
print('Done')
