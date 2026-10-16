#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
"""Compute the affine transform to overlay STR onto MECH using the ACTUAL
grid axis line coordinates (not text label positions which are offset).

Strategy:
  STR axes (from GridLine-* blocks, the dotted DXK_LINE_DOT5 LINE):
    - Vertical axes (A, B, C, D): identified by X being constant
    - Horizontal axes (1, 2, 3): identified by Y being constant

  MECH axes (from top-level LINE entities on layer CEN):
    - Identify each label's axis by matching text-X (for letters) or text-Y (for numbers)
      against the longest lines in the file.

  Then fit scale + translation via least-squares.
"""

import ezdxf
import re
import numpy as np

GRID_RE = re.compile(r"^\s*TP104-([A-D1-3])\s*$")
MECH = ROOT / "dxf/TP-104 MECH GA_clean2.dxf"
STR   = ROOT / "dxf/TP-104 STR GA_clean3.dxf"


# ---- STR axis X and Y for each label --------------------------------------

doc_s = ezdxf.readfile(STR)
str_axes = {}  # label -> {"x": ..., "y": ...}

for block in doc_s.blocks:
    if not block.name.startswith("GridLine-"):
        continue
    label = None
    axis_x = axis_y = None
    for e in block:
        if e.dxftype() == "TEXT":
            m = GRID_RE.match(e.dxf.text.strip())
            if m:
                label = "TP104-" + m.group(1)
        elif e.dxftype() == "LINE" and e.dxf.linetype == "DXK_LINE_DOT5":
            sx, sy = e.dxf.start[0], e.dxf.start[1]
            ex, ey = e.dxf.end[0],   e.dxf.end[1]
            if abs(sx - ex) < abs(sy - ey):
                # vertical axis — constant X
                axis_x = (sx + ex) / 2
                axis_y = (sy + ey) / 2
            else:
                # horizontal axis — constant Y
                axis_x = (sx + ex) / 2
                axis_y = (sy + ey) / 2
    if label and axis_x is not None:
        str_axes[label] = {"x": axis_x, "y": axis_y, "is_vert": abs(sx-ex) < abs(sy-ey)}


# ---- MECH axis X and Y ----------------------------------------------------

doc_m = ezdxf.readfile(MECH)
ms = doc_m.modelspace()

# All long CEN-layer lines
all_cen = []  # (sx,sy,ex,ey,is_horiz,axis_coord)
for e in ms:
    if e.dxftype() != "LINE" or e.dxf.layer != "CEN":
        continue
    sx, sy = e.dxf.start[0], e.dxf.start[1]
    ex, ey = e.dxf.end[0],   e.dxf.end[1]
    L = ((ex-sx)**2 + (ey-sy)**2) ** 0.5
    if L < 3000:   # skip short tick marks
        continue
    is_horiz = abs(ex - sx) > abs(ey - sy)
    coord = sy if is_horiz else sx
    all_cen.append((sx, sy, ex, ey, is_horiz, coord, L))


# MECH label positions
mech_labels = {}
for e in ms:
    if e.dxftype() != "TEXT":
        continue
    m = GRID_RE.match(e.dxf.text.strip())
    if not m:
        continue
    pos = (e.dxf.insert[0], e.dxf.insert[1])
    try:
        if e.dxf.alignment_point:
            pos = (e.dxf.alignment_point[0], e.dxf.alignment_point[1])
    except Exception:
        pass
    mech_labels["TP104-" + m.group(1)] = pos


# For each label, find the matching axis
# Letters (A,B,C,D): pick vertical CEN line whose X is closest to label_X
# Numbers (1,2,3): pick horizontal CEN line whose Y is closest to label_Y
mech_axes = {}
for label, (lx, ly) in mech_labels.items():
    if label[-1] in "ABCD":
        candidates = [(s, sy, ex, ey, L) for s, sy, ex, ey, h, c, L in all_cen if not h]
    else:
        candidates = [(s, sy, ex, ey, L) for s, sy, ex, ey, h, c, L in all_cen if h]
    if not candidates:
        continue
    if label[-1] in "ABCD":
        best = min(candidates, key=lambda r: abs(r[0] - lx))
        axis_x = best[0]
        axis_y = (best[1] + best[3]) / 2
    else:
        best = min(candidates, key=lambda r: abs(r[1] - ly))
        axis_y = best[1]
        axis_x = (best[0] + best[2]) / 2
    mech_axes[label] = {"x": axis_x, "y": axis_y}


# ---- Solve transform ------------------------------------------------------

common = sorted(set(str_axes) & set(mech_axes))
print(f"Common grid labels: {common}\n")

print(f"{'Label':<10} {'STR axis X':>10} {'STR axis Y':>10}    {'MECH axis X':>10} {'MECH axis Y':>10}")
print("-" * 70)
for label in common:
    s = str_axes[label]; m = mech_axes[label]
    print(f"{label:<10} {s['x']:>10.2f} {s['y']:>10.2f}    {m['x']:>10.2f} {m['y']:>10.2f}")

# Least-squares
A, b = [], []
for label in common:
    A.append([str_axes[label]["x"], 1, 0, 0]);  b.append(mech_axes[label]["x"])
    A.append([0, 0, str_axes[label]["y"], 1]);  b.append(mech_axes[label]["y"])
A = np.array(A, dtype=float); b = np.array(b, dtype=float)
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
s, tx, _, ty = sol

print(f"\n--- Fitted transform (using ACTUAL axis lines) ---")
print(f"  scale (X and Y share):  {s:.6f}")
print(f"  translation X:          {tx:.3f}")
print(f"  translation Y:          {ty:.3f}")

print(f"\n--- Verification: transform every STR axis position and check vs MECH ---")
print(f"{'Label':<10} {'STR pos':<22} {'predicted':<22} {'MECH actual':<22} {'residual':<14}")
for label in common:
    xs, ys = str_axes[label]["x"], str_axes[label]["y"]
    xm_pred = s * xs + tx
    ym_pred = s * ys + ty
    xm_act, ym_act = mech_axes[label]["x"], mech_axes[label]["y"]
    dx, dy = xm_pred - xm_act, ym_pred - ym_act
    r = (dx**2 + dy**2) ** 0.5
    print(f"{label:<10} ({xs:>9.2f},{ys:>9.2f})    "
          f"({xm_pred:>9.2f},{ym_pred:>9.2f})    "
          f"({xm_act:>9.2f},{ym_act:>9.2f})    "
          f"r={r:.2f}")

print(f"\n=== FINAL OVERLAY FORMULA ===")
print(f"  x_m = {s:.6f} * x_s + ({tx:.3f})")
print(f"  y_m = {s:.6f} * y_s + ({ty:.3f})")
print(f"  where (x_s, y_s) is a STR coordinate and (x_m, y_m) is the corresponding MECH coordinate.")
