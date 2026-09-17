#!/usr/bin/env python3
"""Compute the affine transform (scale + translation) needed to overlay
TP-104 STR onto TP-104 MECH so the grid axes align.

Method:
  - Use the TEXT label positions of TP104-* in both files as grid intersections.
  - Fit a least-squares affine: (x_m, y_m) = scale * (x_s, y_s) + (tx, ty)
  - Report scale, translation, residuals, and the formula to apply.

Then verify the formula by transforming every STR grid label and printing the
predicted vs actual MECH positions.
"""

import ezdxf
import re
import numpy as np

GRID_RE = re.compile(r"^\s*TP104-([A-D1-3])\s*$")

# ---- helpers --------------------------------------------------------------

def mech_label_positions(path):
    """MECH stores labels as top-level TEXT on layer TEXT."""
    doc = ezdxf.readfile(path)
    out = {}
    for e in doc.modelspace():
        if e.dxftype() != "TEXT":
            continue
        t = e.dxf.text.strip()
        m = GRID_RE.match(t)
        if not m:
            continue
        # TEXT insert = bottom-left of text by default
        x, y = e.dxf.insert[0], e.dxf.insert[1]
        # If alignment is set, prefer alignment_point
        try:
            if e.dxf.alignment_point:
                x, y = e.dxf.alignment_point[0], e.dxf.alignment_point[1]
        except Exception:
            pass
        out["TP104-" + m.group(1)] = (x, y)
    return out


def str_label_positions(path):
    """STR stores labels inside GridLine-* blocks."""
    doc = ezdxf.readfile(path)
    out = {}
    for block in doc.blocks:
        if not block.name.startswith("GridLine-"):
            continue
        for e in block:
            if e.dxftype() != "TEXT":
                continue
            t = e.dxf.text.strip()
            m = GRID_RE.match(t)
            if not m:
                continue
            x, y = e.dxf.insert[0], e.dxf.insert[1]
            try:
                if e.dxf.alignment_point:
                    x, y = e.dxf.alignment_point[0], e.dxf.alignment_point[1]
            except Exception:
                pass
            out["TP104-" + m.group(1)] = (x, y)
            break
    return out


# ---- collect --------------------------------------------------------------

MECH = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 MECH GA_clean2.dxf"
STR  = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 STR GA_clean3.dxf"

mech = mech_label_positions(MECH)
str_ = str_label_positions(STR)
common = sorted(set(mech) & set(str_))
print(f"Common grid labels: {common}\n")

# ---- solve scale+translation (no rotation, both axes share scale) --------

# Variables: x_m = s * x_s + tx ;  y_m = s * y_s + ty
# Linear system: [x_s 1 0 0] [s, tx, s, ty]ᵀ = x_m  (one row per axis pair)
A = []
b = []
for label in common:
    xs, ys = str_[label]
    xm, ym = mech[label]
    A.append([xs, 1, 0, 0]);  b.append(xm)
    A.append([0, 0, ys, 1]);  b.append(ym)

A = np.array(A, dtype=float)
b = np.array(b, dtype=float)
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
s, tx, _, ty = sol

print(f"--- Fitted transform ---")
print(f"  scale (MECH per STR unit): {s:.6f}   (1 / {1/s:.4f})")
print(f"  translation X:             {tx:.3f}")
print(f"  translation Y:             {ty:.3f}")
print(f"  formula: x_m = {s:.4f} * x_s + ({tx:.2f})")
print(f"           y_m = {s:.4f} * y_s + ({ty:.2f})")

# residuals
print(f"\n--- Per-label residuals ---")
print(f"{'Label':<10} {'STR pos':<22} {'predicted MECH':<22} {'actual MECH':<22} {'residual':<10}")
for label in common:
    xs, ys = str_[label]
    xm_pred = s * xs + tx
    ym_pred = s * ys + ty
    xm_act, ym_act = mech[label]
    dx, dy = xm_pred - xm_act, ym_pred - ym_act
    print(f"{label:<10} ({xs:>8.1f},{ys:>8.1f})    ({xm_pred:>9.1f},{ym_pred:>9.1f})    "
          f"({xm_act:>9.1f},{ym_act:>9.1f})    ({dx:>+7.1f},{dy:>+7.1f})")

# Test: STR bbox when transformed to MECH space
print(f"\n--- Bounding boxes ---")
sx_vals = [p[0] for p in str_.values()]
sy_vals = [p[1] for p in str_.values()]
print(f"STR  bbox X [{min(sx_vals):.1f} → {max(sx_vals):.1f}], "
      f"Y [{min(sy_vals):.1f} → {max(sy_vals):.1f}]")

mx_vals = [p[0] for p in mech.values()]
my_vals = [p[1] for p in mech.values()]
print(f"MECH bbox X [{min(mx_vals):.1f} → {max(mx_vals):.1f}], "
      f"Y [{min(my_vals):.1f} → {max(my_vals):.1f}]")
