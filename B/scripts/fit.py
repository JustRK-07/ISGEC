#!/usr/bin/env python3
"""fit.py — Step 2 of the overlay pipeline.

Reads the cleaned MECH and STR DXFs from work/, finds the labeled
gridlines (TP104-A/B/C/D and 1/2/3), solves a least-squares affine fit
that maps STR world coords → MECH world coords, and writes
transform.json with the fit + per-intersection residuals.

Self-locating: works from any clone of ISGEC/.

Usage:
  python3 scripts/fit.py
"""

import ezdxf
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPROACH_DIR = HERE.parent
WORK = APPROACH_DIR / "work"
TRANSFORM = APPROACH_DIR / "transform.json"

MECH = WORK / "TP-104 MECH GA_clean3.dxf"
STR = WORK / "TP-104 STR GA_clean3.dxf"

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
    """For label_suffix in {'A','B','C','D'}: return X coord of the vertical
    gridline LINE whose TEXT label matches.

    For label_suffix in {'1','2','3'}: return Y coord of the horizontal
    gridline LINE."""
    doc = ezdxf.readfile(str(MECH))
    msp = doc.modelspace()

    text_pos = None
    for t in msp:
        if t.dxftype() == "TEXT":
            m = GRID_RE.match(t.dxf.text.strip())
            if m and m.group(1) == label_suffix:
                text_pos = (t.dxf.insert[0], t.dxf.insert[1])
                break
    if text_pos is None:
        return None, None

    best = None
    best_dist = float("inf")
    is_vert = (axis == "X")
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
        mx = (s[0] + end[0]) / 2
        my = (s[1] + end[1]) / 2
        d = ((mx - text_pos[0]) ** 2 + (my - text_pos[1]) ** 2) ** 0.5
        if d < best_dist:
            best_dist = d
            best = e
    if best is None:
        return None, None

    if axis == "X":
        return (best.dxf.start[0] + best.dxf.end[0]) / 2, best_dist
    else:
        return (best.dxf.start[1] + best.dxf.end[1]) / 2, best_dist


def find_str_axis(label_suffix, axis):
    """Find the labeled gridline in STR by walking INSIDE GridLine-* blocks.
    Returns (axis_coord, 0.0) on success."""
    doc = ezdxf.readfile(str(STR))
    msp = doc.modelspace()

    is_vert = (axis == "X")

    for ins in msp:
        if ins.dxftype() != "INSERT":
            continue
        nm = ins.dxf.name
        # Match blocks named "GridLine-*" or " Line-*" (DXF round-trip variants)
        if not (nm.startswith("GridLine-") or nm.startswith(" Line-")):
            continue

        block = None
        for b in doc.blocks:
            if b.name == ins.dxf.name:
                block = b
                break
        if block is None:
            continue

        text_label = None
        best_line = None
        best_length = 0.0
        for e in block:
            if e.dxftype() == "TEXT":
                m = GRID_RE.match(e.dxf.text.strip())
                if m and m.group(1) == label_suffix:
                    text_label = e
            elif e.dxftype() == "LINE":
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

        s, end = best_line.dxf.start, best_line.dxf.end
        px, py = ins.dxf.insert[0], ins.dxf.insert[1]
        sx = ins.dxf.xscale or 1.0
        sy = ins.dxf.yscale if ins.dxf.hasattr("yscale") and ins.dxf.yscale else sx

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
    print("=" * 70)
    print("Step 2: FIT — derive MECH↔STR affine from labeled gridlines")
    print("=" * 70)

    if not MECH.exists() or not STR.exists():
        print(f"  ERROR: cleaned DXFs not found. Run scripts/clean.py first.")
        print(f"    expected: {MECH}")
        print(f"    expected: {STR}")
        sys.exit(1)

    # ---- Collect axis pairs -------------------------------------------------
    x_pairs = []
    y_pairs = []

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

    # ---- Cross-check -------------------------------------------------------
    print(f"\nCross-check: per-intersection residual")
    print(f"  {'Label':>10}  {'STR (x,y)':>26}  {'MECH (x,y)':>26}  "
          f"{'Predicted MECH':>26}  {'residual':>10}")

    residuals = []
    for xlabel, sx, mx in x_pairs:
        for ylabel, sy, my in y_pairs:
            sp = (sx, sy)
            mp = (mx, my)
            pred = (ax * sp[0] + bx, ay * sp[1] + by)
            d = ((pred[0] - mp[0]) ** 2 + (pred[1] - mp[1]) ** 2) ** 0.5
            residuals.append((f"{xlabel}-{ylabel}", sp, mp, pred, d))
            print(f"  {xlabel}-{ylabel:>6}  ({sp[0]:>11.2f}, {sp[1]:>10.2f})  "
                  f"({mp[0]:>11.2f}, {mp[1]:>10.2f})  "
                  f"({pred[0]:>11.2f}, {pred[1]:>10.2f})  {d:>10.2f}")

    rms = (sum(r ** 2 for _, _, _, _, r in residuals) / len(residuals)) ** 0.5
    max_r = max(r for _, _, _, _, r in residuals)
    print(f"\n  RMS residual: {rms:.2f}")
    print(f"  Max residual: {max_r:.2f}")

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
        "max_residual": max_r,
    }
    with open(TRANSFORM, "w") as f:
        json.dump(transform, f, indent=2)

    print(f"\n✓ Wrote {TRANSFORM}")
    print("\nNext: run scripts/overlay.py to build the final DXF")


if __name__ == "__main__":
    main()
