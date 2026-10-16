#!/usr/bin/env python3
"""Final overlay transform using TEXT label positions.

Why text positions (not axis lines):
  - In STR, every GridLine-* block contains the axis LINE + the TEXT label + ticks.
    All wrapped in one block → one INSERT. We know text_X = axis_X for letter axes
    and text_Y = axis_Y for number axes (verified).
  - In MECH, the axes are mostly wrapped in INSERTed blocks; the text labels are at
    modelspace level. Text_X for letters = axis_X, text_Y for numbers = axis_Y.

  Even if the text-to-axis offset differs between files (it does), using text
  positions for the anchor gives us:
    1. Consistent anchors across files (no guessing which CEN line is which axis)
    2. The transform maps STR text position → MECH text position directly
    3. After applying, you can pick any other STR coordinate (e.g., a TP104-C-1
       intersection) and find where it lands in MECH.
"""

import ezdxf
import re
import numpy as np

GRID_RE = re.compile(r"^\s*TP104-([A-D1-3])\s*$")
MECH = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 MECH GA_clean2.dxf"
STR  = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 STR GA_clean3.dxf"


def all_label_positions(doc):
    """Walk modelspace + all blocks, return {label: (x, y)} for each TP104-* TEXT."""
    out = {}
    # modelspace
    for e in doc.modelspace():
        if e.dxftype() != "TEXT":
            continue
        m = GRID_RE.match(e.dxf.text.strip())
        if m:
            label = "TP104-" + m.group(1)
            pos = (e.dxf.insert[0], e.dxf.insert[1])
            try:
                if e.dxf.alignment_point:
                    pos = (e.dxf.alignment_point[0], e.dxf.alignment_point[1])
            except Exception:
                pass
            out[label] = pos
    # blocks (for STR)
    for block in doc.blocks:
        for e in block:
            if e.dxftype() != "TEXT":
                continue
            m = GRID_RE.match(e.dxf.text.strip())
            if m:
                label = "TP104-" + m.group(1)
                pos = (e.dxf.insert[0], e.dxf.insert[1])
                try:
                    if e.dxf.alignment_point:
                        pos = (e.dxf.alignment_point[0], e.dxf.alignment_point[1])
                except Exception:
                    pass
                out.setdefault(label, pos)  # modelspace takes priority
    return out


str_pos = all_label_positions(ezdxf.readfile(STR))
mech_pos = all_label_positions(ezdxf.readfile(MECH))

# Show all
print("STR text positions:")
for k in sorted(str_pos):
    print(f"  {k}: {str_pos[k]}")
print("\nMECH text positions:")
for k in sorted(mech_pos):
    print(f"  {k}: {mech_pos[k]}")

# Fit affine with separate X/Y scale and rotation allowed (4-parameter affine:
# x' = a*x + b*y + tx ; y' = c*x + d*y + ty
A, b = [], []
common = sorted(set(str_pos) & set(mech_pos))
print(f"\nCommon labels: {common}")

for label in common:
    xs, ys = str_pos[label]
    xm, ym = mech_pos[label]
    # x' = a*xs + b*ys + tx
    A.append([xs, ys, 1, 0, 0, 0]);  b.append(xm)
    # y' = c*xs + d*ys + ty
    A.append([0, 0, 0, xs, ys, 1]);  b.append(ym)

A = np.array(A, dtype=float); b = np.array(b, dtype=float)
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
a, bb, tx, c, d, ty = sol

print(f"\n--- Full affine transform ---")
print(f"  x_m = {a:.6f} * x_s + {bb:.6f} * y_s + ({tx:.3f})")
print(f"  y_m = {c:.6f} * x_s + {d:.6f} * y_s + ({ty:.3f})")

# Test: if b and c are tiny, the transform is purely scale + translate (no rotation)
print(f"\n  Rotation/scale matrix:")
print(f"    [ {a:.4f}  {bb:.4f} ]")
print(f"    [ {c:.4f}  {d:.4f} ]")
det = a * d - bb * c
print(f"  determinant = {det:.4f}  (should be scale² if pure scale+translate)")

# Verification
print(f"\n--- Per-label verification ---")
print(f"{'Label':<10} {'STR pos':<22} {'predicted':<22} {'MECH actual':<22} {'residual':<14}")
total = 0
for label in common:
    xs, ys = str_pos[label]
    xm_pred = a*xs + bb*ys + tx
    ym_pred = c*xs + d*ys + ty
    xm_act, ym_act = mech_pos[label]
    dx, dy = xm_pred - xm_act, ym_pred - ym_act
    r = (dx*dx + dy*dy) ** 0.5
    total += r*r
    print(f"{label:<10} ({xs:>9.1f},{ys:>9.1f})    "
          f"({xm_pred:>9.2f},{ym_pred:>9.2f})    "
          f"({xm_act:>9.1f},{ym_act:>9.1f})    "
          f"r={r:.2f}")
print(f"\n  RMS residual: {(total/len(common))**0.5:.2f} units")

# Also test pure scale+translation (no rotation): use axis positions, not labels
# STR axis X for letters: STR text_X is at axis_X + offset. We know axis_X for STR.
# Better approach: use the AXIS LINE X for letters (vertical axes) and AXIS LINE Y for numbers (horizontal axes)

# For STR, we have axis line coords from earlier analysis
STR_AXIS = {
    "TP104-A": {"x": 23950.57, "y": (12454.53 + 27661.75) / 2},
    "TP104-B": {"x": 20200.57, "y": (12454.53 + 27661.75) / 2},
    "TP104-C": {"x": 9575.57,  "y": (12454.53 + 27661.75) / 2},
    "TP104-D": {"x": 3325.57,  "y": (12454.53 + 27661.75) / 2},
    "TP104-1": {"x": (2535.36 + 24512.14)/2, "y": 25070.84},
    "TP104-2": {"x": (2535.36 + 24512.14)/2, "y": 21320.84},
    "TP104-3": {"x": (2535.36 + 24512.14)/2, "y": 12570.84},
}

# For MECH, axis positions = text positions (verified by inspection of CEN lines)
# axis A: text_X = 227907.4 (axis at X = text_X)
# axis 1: text_Y = -155851.6, axis at Y = -155263.69 (offset 588)
# Since text-axis offsets differ between letters and numbers in MECH, use axis LINES where we can

# Use the MECH axis LINE positions we identified from the CEN layer
# Plus the assumption: for letter axes, axis_X = text_X; for number axes, axis_Y = text_Y
MECH_AXIS = {
    "TP104-A": {"x": 227907.4, "y": -151650.6},   # axis A is vertical at x=227907.4 (text X)
    "TP104-B": {"x": 224907.7, "y": -151650.6},
    "TP104-C": {"x": 216399.6, "y": -151652.3},
    "TP104-D": {"x": 211399.6, "y": -151681.1},
    "TP104-1": {"x": 210358.5, "y": -155263.69},  # axis 1 is horizontal at y=-155263.69 (CEN line)
    "TP104-2": {"x": 210358.5, "y": -158263.69},  # axis 2 at y=-158263.69 (shorter CEN line at 5008.8)
    "TP104-3": {"x": 210358.4, "y": -165263.69},
}

# Fit scale+translation using axis X for letters and axis Y for numbers
# Use combined "axis X" and "axis Y" coordinates from above
A, b = [], []
for label in common:
    xs_axis = STR_AXIS[label]["x"]
    xm_axis = MECH_AXIS[label]["x"]
    A.append([xs_axis, 1, 0, 0]);  b.append(xm_axis)
    A.append([0, 0, STR_AXIS[label]["y"], 1]);  b.append(MECH_AXIS[label]["y"])
A = np.array(A, dtype=float); b = np.array(b, dtype=float)
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
s_x, tx, _, ty = sol
print(f"\n\n=== PURE SCALE + TRANSLATE USING AXIS LINES ===")
print(f"  x_m = {s_x:.6f} * x_s + ({tx:.3f})")
print(f"  y_m = {s_x:.6f} * y_s + ({ty:.3f})   (assumed same scale)")

# Verify on axis positions
print(f"\n--- Per-axis verification ---")
total = 0
for label in common:
    xs = STR_AXIS[label]["x"]; ys = STR_AXIS[label]["y"]
    xm_pred = s_x * xs + tx
    ym_pred = s_x * ys + ty
    xm_act = MECH_AXIS[label]["x"]; ym_act = MECH_AXIS[label]["y"]
    dx = xm_pred - xm_act; dy = ym_pred - ym_act
    r = (dx*dx + dy*dy) ** 0.5
    total += r*r
    print(f"  {label}: STR=({xs:.2f},{ys:.2f})  →  ({xm_pred:.2f},{ym_pred:.2f})  "
          f"vs MECH=({xm_act:.2f},{ym_act:.2f})  r={r:.2f}")
print(f"\n  RMS residual: {(total/len(common))**0.5:.2f} units")

# Also check the actual 1.25:1 scale hypothesis
print(f"\n=== 1.25:1 scale hypothesis test ===")
ratios_x, ratios_y = [], []
for label in common:
    if label[-1] in "ABCD":  # letter axis — use X
        sx = STR_AXIS[label]["x"]; mx = MECH_AXIS[label]["x"]
        if sx != 0: ratios_x.append((mx, sx))
    else:  # number axis — use Y
        sy = STR_AXIS[label]["y"]; my = MECH_AXIS[label]["y"]
        if sy != 0: ratios_y.append((my, sy))

# Find a common scale using adjacent axis spacings
print(f"\nSTR axis X spacing (D-C, C-B, B-A):")
str_xs = sorted([STR_AXIS[k]["x"] for k in STR_AXIS if k.endswith(("A","B","C","D"))])
for i in range(len(str_xs)-1):
    print(f"  {str_xs[i]:.2f} → {str_xs[i+1]:.2f}  Δ={str_xs[i+1]-str_xs[i]:.2f}")
print(f"MECH axis X spacing (D-C, C-B, B-A):")
mech_xs = sorted([MECH_AXIS[k]["x"] for k in MECH_AXIS if k.endswith(("A","B","C","D"))])
for i in range(len(mech_xs)-1):
    print(f"  {mech_xs[i]:.2f} → {mech_xs[i+1]:.2f}  Δ={mech_xs[i+1]-mech_xs[i]:.2f}")

print(f"\nSTR axis Y spacing (3-2, 2-1):")
str_ys = sorted([STR_AXIS[k]["y"] for k in STR_AXIS if k.endswith(("1","2","3"))])
for i in range(len(str_ys)-1):
    print(f"  {str_ys[i]:.2f} → {str_ys[i+1]:.2f}  Δ={str_ys[i+1]-str_ys[i]:.2f}")
print(f"MECH axis Y spacing (3-2, 2-1):")
mech_ys = sorted([MECH_AXIS[k]["y"] for k in MECH_AXIS if k.endswith(("1","2","3"))])
for i in range(len(mech_ys)-1):
    print(f"  {mech_ys[i]:.2f} → {mech_ys[i+1]:.2f}  Δ={mech_ys[i+1]-mech_ys[i]:.2f}")

# scale = MECH spacing / STR spacing (since MECH units are smaller per STR unit)
spacings_str = [str_xs[i+1]-str_xs[i] for i in range(len(str_xs)-1)]
spacings_mech_x = [mech_xs[i+1]-mech_xs[i] for i in range(len(mech_xs)-1)]
spacings_str_y = [str_ys[i+1]-str_ys[i] for i in range(len(str_ys)-1)]
spacings_mech_y = [mech_ys[i+1]-mech_ys[i] for i in range(len(mech_ys)-1)]

print(f"\n  X scale (MECH / STR) per spacing: {[m/s for m,s in zip(spacings_mech_x, spacings_str)]}")
print(f"  Y scale (MECH / STR) per spacing: {[m/s for m,s in zip(spacings_mech_y, spacings_str_y)]}")
print(f"  X avg scale: {sum(spacings_mech_x)/sum(spacings_str):.6f}")
print(f"  Y avg scale: {sum(spacings_mech_y)/sum(spacings_str_y):.6f}")
