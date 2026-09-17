#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
"""Compute the affine transform to overlay STR on MECH by aligning the actual
grid AXIS LINES (not the text labels, which are offset differently in each file).

Method:
  - STR: each GridLine-* block contains 1 LINE entity = the grid axis
  - MECH: the axis lines live on layer 'CEN' as top-level LINE entities
  - For each TP104-* label, pick the closest axis line in each file
  - Use the line's midpoint (or one endpoint) as the alignment anchor
  - Fit scale + translation via least-squares
"""

import ezdxf
import re
import numpy as np

GRID_RE = re.compile(r"^\s*TP104-([A-D1-3])\s*$")
MECH = ROOT / "dxf/TP-104 MECH GA_clean2.dxf"
STR   = ROOT / "dxf/TP-104 STR GA_clean3.dxf"

# ---- STR: get axis midpoint for each grid label ---------------------------

doc_s = ezdxf.readfile(STR)
str_axes = {}  # label -> midpoint of axis line
str_labels = {}  # label -> text position

for block in doc_s.blocks:
    if not block.name.startswith("GridLine-"):
        continue
    label = None
    line_mid = None
    text_pos = None
    for e in block:
        if e.dxftype() == "TEXT":
            t = e.dxf.text.strip()
            m = GRID_RE.match(t)
            if m:
                label = "TP104-" + m.group(1)
                text_pos = (e.dxf.insert[0], e.dxf.insert[1])
                try:
                    if e.dxf.alignment_point:
                        text_pos = (e.dxf.alignment_point[0], e.dxf.alignment_point[1])
                except Exception:
                    pass
        elif e.dxftype() == "LINE":
            sx, sy = e.dxf.start[0], e.dxf.start[1]
            ex, ey = e.dxf.end[0],   e.dxf.end[1]
            line_mid = ((sx + ex) / 2, (sy + ey) / 2)
    if label and line_mid:
        str_axes[label] = line_mid
        str_labels[label] = text_pos

# ---- MECH: get axis midpoint for each grid label ---------------------------

doc_m = ezdxf.readfile(MECH)
ms_m = doc_m.modelspace()

# Build a list of all CEN-layer LINE midpoints
cen_lines = []
for e in ms_m:
    if e.dxftype() == "LINE" and e.dxf.layer == "CEN":
        sx, sy = e.dxf.start[0], e.dxf.start[1]
        ex, ey = e.dxf.end[0],   e.dxf.end[1]
        mid = ((sx + ex) / 2, (sy + ey) / 2)
        cen_lines.append(mid)

# Get all MECH grid label positions
mech_labels = {}
for e in ms_m:
    if e.dxftype() != "TEXT":
        continue
    t = e.dxf.text.strip()
    m = GRID_RE.match(t)
    if not m:
        continue
    pos = (e.dxf.insert[0], e.dxf.insert[1])
    try:
        if e.dxf.alignment_point:
            pos = (e.dxf.alignment_point[0], e.dxf.alignment_point[1])
    except Exception:
        pass
    mech_labels["TP104-" + m.group(1)] = pos

# For each MECH label, pick the nearest CEN-line
mech_axes = {}
for label, (lx, ly) in mech_labels.items():
    # A vertical axis (letter A/B/C/D) has a line at X near label X (constant X, varying Y)
    # A horizontal axis (number 1/2/3) has a line at Y near label Y (varying X, constant Y)
    if label[-1] in "ABCD":
        # vertical axis: filter to lines that are vertical-ish (ΔY >> ΔX), pick by |X - lx|
        candidates = [p for p in cen_lines if abs(p[0] - lx) < 50 and abs(p[1] - ly) < 5e6]
    else:
        # horizontal axis: filter to lines that are horizontal-ish (ΔX >> ΔY), pick by |Y - ly|
        candidates = [p for p in cen_lines if abs(p[1] - ly) < 50 and abs(p[0] - lx) < 5e6]

    if not candidates:
        print(f"  warn: no axis candidate for {label}")
        continue
    # pick closest by the relevant coordinate
    if label[-1] in "ABCD":
        # all candidates have similar X; pick the one with X closest to label X
        best = min(candidates, key=lambda p: abs(p[0] - lx))
    else:
        best = min(candidates, key=lambda p: abs(p[1] - ly))
    mech_axes[label] = best

# ---- Solve transform ------------------------------------------------------

common = sorted(set(str_axes) & set(mech_axes))
print(f"Common grid labels: {common}\n")

print(f"{'Label':<10} {'STR axis mid':<22} {'MECH axis mid':<22} {'distance':<10}")
for label in common:
    s = str_axes[label]
    m = mech_axes[label]
    d = ((s[0]-m[0])**2 + (s[1]-m[1])**2) ** 0.5
    print(f"{label:<10} ({s[0]:>9.1f},{s[1]:>9.1f})    ({m[0]:>9.1f},{m[1]:>9.1f})    {d:>9.1f}")

# Least-squares: x_m = s * x_s + tx ; y_m = s * y_s + ty
A = []
b = []
for label in common:
    xs, ys = str_axes[label]
    xm, ym = mech_axes[label]
    A.append([xs, 1, 0, 0]);  b.append(xm)
    A.append([0, 0, ys, 1]);  b.append(ym)

A = np.array(A, dtype=float)
b = np.array(b, dtype=float)
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
s, tx, _, ty = sol

print(f"\n--- Fitted transform (using AXIS LINES) ---")
print(f"  scale:    {s:.6f}     (STR units → MECH units)")
print(f"  translation X: {tx:.3f}")
print(f"  translation Y: {ty:.3f}")

# residuals
print(f"\n--- Per-axis residuals after transform ---")
print(f"{'Label':<10} {'STR pos':<22} {'predicted MECH':<22} {'actual MECH':<22} {'residual':<12}")
total = 0
for label in common:
    xs, ys = str_axes[label]
    xm_pred = s * xs + tx
    ym_pred = s * ys + ty
    xm_act, ym_act = mech_axes[label]
    dx, dy = xm_pred - xm_act, ym_pred - ym_act
    r = (dx**2 + dy**2) ** 0.5
    total += r*r
    print(f"{label:<10} ({xs:>8.1f},{ys:>8.1f})    ({xm_pred:>9.2f},{ym_pred:>9.2f})    "
          f"({xm_act:>9.1f},{ym_act:>9.1f})    ({dx:>+6.1f},{dy:>+6.1f})  r={r:.1f}")

print(f"\n  RMS residual: {(total / len(common)) ** 0.5:.2f} units")

# Also print the exact 1.25:1 ratio test
print(f"\n--- 1.25:1 ratio test ---")
print(f"  1/scale = {1/s:.6f}  (should be exactly 1.25 if scale is 0.8)")

# Print the formula for use in the overlay step
print(f"\n=== OVERLAY FORMULA ===")
print(f"  For every STR point (x_s, y_s):")
print(f"    x_m = {s:.6f} * x_s + ({tx:.3f})")
print(f"    y_m = {s:.6f} * y_s + ({ty:.3f})")
