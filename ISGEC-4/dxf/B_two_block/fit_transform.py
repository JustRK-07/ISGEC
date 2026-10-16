#!/usr/bin/env python3
"""fit_transform.py — derive the MECH→STR overlay affine transform from
labeled gridlines in both DXFs.

Strategy
--------
1. In each DXF, find every entity carrying a TP104-* label (TEXT at modelspace
   for MECH, TEXT inside GridLine-* blocks for STR).
2. For each label, locate the actual gridline LINE that the label refers to:
     - For TP104-A/B/C/D (vertical column labels): find a near-vertical LINE
     - For TP104-1/2/3 (horizontal row labels): find a near-horizontal LINE
   The LINE's X (vertical) or Y (horizontal) coordinate is the axis position.
3. Match labels between MECH and STR by label string.
4. Solve two independent least-squares fits:
     X_m = a * X_s + b   (from A/B/C/D labels)
     Y_m = c * Y_s + d   (from 1/2/3 labels)
5. Cross-check by constructing all (X, Y) intersection points in both files
   and reporting per-point residuals.
6. Write transform.json.

This is reusable across the 3 overlay approaches — A, B, C all read the
same transform.json. Copy this script into A/, B/, C/ and run it once in
any one of them.
"""

import ezdxf
import json
import re
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MECH = str(HERE.parent / "TP-104 MECH GA_clean3.dxf")
STR = str(HERE.parent / "TP-104 STR GA_clean3.dxf")
OUT = HERE / "transform.json"

# AutoCAD Mechanical centerline layers in MECH
GRID_LAYERS_MECH = {"CEN", "CENETR LINE", "CENTER", "PHANTOM", "PANTHOM",
                    "HIDDEN", "HIDDDEN"}

GRID_RE = re.compile(r"^TP104-([A-Z]|\d+)\s*$")


def _is_vertical(e):
    s, end = e.dxf.start, e.dxf.end
    return abs(s[0] - end[0]) < 1.0 and abs(s[1] - end[1]) > 100.0


def _is_horizontal(e):
    s, end = e.dxf.start, e.dxf.end
    return abs(s[1] - end[1]) < 1.0 and abs(s[0] - end[0]) > 100.0


def find_mech_axis(label_suffix, axis):
    """Return the X (for vertical labels) or Y (for horizontal labels) of the
    gridline that the TEXT label refers to. axis='X' for column labels
    (A/B/C/D), axis='Y' for row labels (1/2/3)."""
    doc = ezdxf.readfile(MECH)
    msp = doc.modelspace()

    # Find the TEXT with the matching label
    text_pos = None
    for t in msp:
        if t.dxftype() == "TEXT":
            m = GRID_RE.match(t.dxf.text.strip())
            if m and m.group(1) == label_suffix:
                text_pos = (t.dxf.insert[0], t.dxf.insert[1])
                break
    if text_pos is None:
        return None, None

    # Find the nearest long axis-aligned LINE on a gridline layer
    best = None
    best_dist = float("inf")
    is_vert = (axis == "X")  # X-axis labels (A/B/C/D) are above VERTICAL lines
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        if e.dxf.layer not in GRID_LAYERS_MECH:
            continue
        if is_vert and not _is_vertical(e):
            continue
        if not is_vert and not _is_horizontal(e):
            continue
        s, end = e.dxf.start, e.dxf.end
        # Midpoint of the line
        mx = (s[0] + end[0]) / 2
        my = (s[1] + end[1]) / 2
        # Distance from TEXT to mid-point of LINE
        d = ((mx - text_pos[0]) ** 2 + (my - text_pos[1]) ** 2) ** 0.5
        if d < best_dist:
            best_dist = d
            best = e
    if best is None:
        return None, None

    if axis == "X":
        # Vertical line: average X of endpoints
        return (best.dxf.start[0] + best.dxf.end[0]) / 2, best_dist
    else:
        # Horizontal line: average Y of endpoints
        return (best.dxf.start[1] + best.dxf.end[1]) / 2, best_dist


def find_str_axis(label_suffix, axis):
    """Same as find_mech_axis but for STR — looks inside GridLine-* blocks."""
    doc = ezdxf.readfile(STR)
    msp = doc.modelspace()

    is_vert = (axis == "X")

    for ins in msp:
        if ins.dxftype() != "INSERT":
            continue
        # Match blocks named "GridLine-*" or " Line-*" (DXF round-trip variants)
        nm = ins.dxf.name
        if not (nm.startswith("GridLine-") or nm.startswith(" Line-")):
            continue
        block = None
        for b in doc.blocks:
            if b.name == ins.dxf.name:
                block = b
                break
        if block is None:
            continue
        # Find TEXT with matching label and the LONGEST axis-aligned LINE
        text_label = None
        best_line = None
        best_length = 0.0
        for e in block:
            if e.dxftype() == "TEXT":
                m = GRID_RE.match(e.dxf.text.strip())
                if m and m.group(1) == label_suffix:
                    text_label = e
            elif e.dxftype() == "LINE":
                # Keep only the longest axis-aligned line (the actual gridline,
                # not the small label-bracket markers at the line's end).
                s, end = e.dxf.start, e.dxf.end
                length = ((end[0] - s[0]) ** 2 + (end[1] - s[1]) ** 2) ** 0.5
                if is_vert and _is_vertical(e) and length > best_length:
                    best_length = length
                    best_line = e
                elif not is_vert and _is_horizontal(e) and length > best_length:
                    best_length = length
                    best_line = e
        if text_label is None or best_line is None:
            continue
        main_line = best_line

        # World coords
        px, py = ins.dxf.insert[0], ins.dxf.insert[1]
        sx = ins.dxf.xscale
        sy = ins.dxf.yscale

        if axis == "X":
            wx1 = px + sx * s[0]
            wx2 = px + sx * end[0]
            return (wx1 + wx2) / 2, 0.0
        else:
            wy1 = py + sy * s[1]
            wy2 = py + sy * end[1]
            return (wy1 + wy2) / 2, 0.0

    return None, None


def fit_axis(str_vals, mech_vals):
    """Least-squares fit: mech = a*str + b. Returns (a, b)."""
    n = len(str_vals)
    sx = sum(str_vals)
    sy = sum(mech_vals)
    sxx = sum(v * v for v in str_vals)
    sxy = sum(s * m for s, m in zip(str_vals, mech_vals))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        return 1.0, (sy - sx) / n
    a = (n * sxy - sx * sy) / denom
    b = (sy - a * sx) / n
    return a, b


def main():
    print("=" * 72)
    print("fit_transform.py — MECH ↔ STR affine fit from labeled gridlines")
    print("=" * 72)

    # ---- Collect axis pairs -------------------------------------------------
    x_pairs = []  # (label, str_x, mech_x)  for A/B/C/D
    y_pairs = []  # (label, str_y, mech_y)  for 1/2/3

    for label in ["A", "B", "C", "D"]:
        sx, _ = find_str_axis(label, "X")
        mx, _ = find_mech_axis(label, "X")
        if sx is None or mx is None:
            print(f"  WARN: could not find TP104-{label} axis in both files")
            continue
        x_pairs.append((label, sx, mx))
        print(f"  TP104-{label}: STR x={sx:>12.2f}   MECH x={mx:>12.2f}   "
              f"Δ={mx - sx:>+10.2f}")

    for label in ["1", "2", "3"]:
        sy, _ = find_str_axis(label, "Y")
        my, _ = find_mech_axis(label, "Y")
        if sy is None or my is None:
            print(f"  WARN: could not find TP104-{label} axis in both files")
            continue
        y_pairs.append((label, sy, my))
        print(f"  TP104-{label}: STR y={sy:>12.2f}   MECH y={my:>12.2f}   "
              f"Δ={my - sy:>+10.2f}")

    if not x_pairs or not y_pairs:
        print("\nFATAL: not enough axis pairs to fit — aborting")
        sys.exit(1)

    # ---- Solve the affine ---------------------------------------------------
    ax, bx = fit_axis([s for _, s, _ in x_pairs], [m for _, _, m in x_pairs])
    ay, by = fit_axis([s for _, s, _ in y_pairs], [m for _, _, m in y_pairs])

    print(f"\nFitted transform:")
    print(f"  x_m = {ax:.6f} · x_s + {bx:.4f}")
    print(f"  y_m = {ay:.6f} · y_s + {by:.4f}")

    # ---- Cross-check: build intersection points and report residual --------
    print(f"\nCross-check: per-intersection residual")
    str_pts = []
    mech_pts = []
    for xlabel, sx, mx in x_pairs:
        for ylabel, sy, my in y_pairs:
            sp = (sx, sy)
            mp = (mx, my)
            str_pts.append((f"{xlabel}-{ylabel}", sp))
            mech_pts.append((f"{xlabel}-{ylabel}", mp))
    residuals = []
    print(f"  {'Label':>10}  {'STR (x,y)':>26}  {'MECH (x,y)':>26}  "
          f"{'Predicted MECH':>26}  {'residual':>10}")
    for (lbl, sp), (_, mp) in zip(str_pts, mech_pts):
        pred = (ax * sp[0] + bx, ay * sp[1] + by)
        d = ((pred[0] - mp[0]) ** 2 + (pred[1] - mp[1]) ** 2) ** 0.5
        residuals.append((lbl, sp, mp, pred, d))
        print(f"  {lbl:>10}  ({sp[0]:>11.2f}, {sp[1]:>10.2f})  "
              f"({mp[0]:>11.2f}, {mp[1]:>10.2f})  "
              f"({pred[0]:>11.2f}, {pred[1]:>10.2f})  {d:>10.2f}")
    rms = (sum(r ** 2 for _, _, _, _, r in residuals) / len(residuals)) ** 0.5
    print(f"\n  RMS residual: {rms:.2f}")
    print(f"  Max residual: {max(r for _, _, _, _, r in residuals):.2f}")

    # ---- Write transform.json ----------------------------------------------
    transform = {
        "scale_x": ax,
        "scale_y": ay,
        "tx": bx,
        "ty": by,
        "x_labels": [{"label": l, "str": s, "mech": m}
                     for l, s, m in x_pairs],
        "y_labels": [{"label": l, "str": s, "mech": m}
                     for l, s, m in y_pairs],
        "intersections": [
            {"label": l, "str": list(sp), "mech": list(mp),
             "predicted_mech": list(pred), "residual": d}
            for l, sp, mp, pred, d in residuals
        ],
        "rms_residual": rms,
        "max_residual": max(r for _, _, _, _, r in residuals),
    }
    with open(OUT, "w") as f:
        json.dump(transform, f, indent=2)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
