#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
"""Find TP104-* grid label positions and axis line extents in BOTH DXF files.

Goal: compute the translation + scale needed to overlay STR on MECH so their
grid axes line up at TP104-C / TP104-1 etc.
"""

import ezdxf
import re
from collections import defaultdict

FILES = {
    "MECH": str(ROOT / "dxf/TP-104 MECH GA_clean2.dxf"),
    "STR":  str(ROOT / "dxf/TP-104 STR GA_clean3.dxf"),
}

GRID_RE = re.compile(r"^\s*TP104-([A-D1-3])\s*$")


def grid_data(path):
    """Return dict {label: (text_x, text_y, axis_min_x, axis_max_x, axis_min_y, axis_max_y)}."""
    doc = ezdxf.readfile(path)
    out = {}
    # Each GridLine-* block contains the axis line + the label TEXT.
    for block in doc.blocks:
        if not block.name.startswith("GridLine-"):
            continue
        text_x = text_y = None
        axis_xs = []
        axis_ys = []
        for e in block:
            et = e.dxftype()
            if et == "TEXT":
                t = e.dxf.text.strip()
                m = GRID_RE.match(t)
                if m:
                    text_x = e.dxf.insert[0] if hasattr(e.dxf, "insert") else None
                    text_y = e.dxf.insert[1] if hasattr(e.dxf, "insert") else None
                    # TEXT entity has insert + alignment — try align_point too
                    try:
                        if e.dxf.get("alignment_point"):
                            text_x = e.dxf.alignment_point[0]
                            text_y = e.dxf.alignment_point[1]
                    except Exception:
                        pass
            elif et == "LINE":
                s, end = e.dxf.start, e.dxf.end
                axis_xs += [s[0], end[0]]
                axis_ys += [s[1], end[1]]
        if text_x is not None:
            label = "TP104-" + GRID_RE.match(t).group(1) if False else None  # we'll re-set below
        if text_x is not None and axis_xs:
            # we re-extract the label from the text we just found
            for e in block:
                if e.dxftype() == "TEXT" and GRID_RE.match(e.dxf.text.strip()):
                    label = GRID_RE.match(e.dxf.text.strip()).group(0)
                    out[label] = {
                        "text_xy": (text_x, text_y),
                        "axis_min_x": min(axis_xs), "axis_max_x": max(axis_xs),
                        "axis_min_y": min(axis_ys), "axis_max_y": max(axis_ys),
                        "axis_len_x": max(axis_xs) - min(axis_xs),
                        "axis_len_y": max(axis_ys) - min(axis_ys),
                    }
                    break
    return out


def fmt(v, n=2):
    if v is None: return "None"
    if isinstance(v, tuple): return f"({v[0]:.{n}f}, {v[1]:.{n}f})"
    return f"{v:.{n}f}"


for label, path in FILES.items():
    print("=" * 70)
    print(f"{label}  —  {path.split('/')[-1]}")
    print("=" * 70)
    g = grid_data(path)
    if not g:
        print("  (no grid labels found)")
        continue
    print(f"\n{'Label':<10} {'Text XY':<22} {'axis X range':<28} {'axis Y range':<28} {'ΔX':<10} {'ΔY':<10}")
    print("-" * 110)
    for label in sorted(g.keys()):
        d = g[label]
        xr = f"[{d['axis_min_x']:.0f} → {d['axis_max_x']:.0f}]"
        yr = f"[{d['axis_min_y']:.0f} → {d['axis_max_y']:.0f}]"
        print(f"{label:<10} {fmt(d['text_xy']):<22} {xr:<28} {yr:<28} {d['axis_len_x']:<10.0f} {d['axis_len_y']:<10.0f}")

    # Bounding box of all grid axes
    all_xs, all_ys = [], []
    for d in g.values():
        all_xs += [d["axis_min_x"], d["axis_max_x"], d["text_xy"][0]]
        all_ys += [d["axis_min_y"], d["axis_max_y"], d["text_xy"][1]]
    print(f"\n  All-grid bbox: X [{min(all_xs):.1f} → {max(all_xs):.1f}], "
          f"Y [{min(all_ys):.1f} → {max(all_ys):.1f}]")

    # Distance between adjacent grid axes (spacing of letters vs numbers)
    letter_labels = sorted([k for k in g if k.endswith(("A","B","C","D"))],
                           key=lambda s: g[s]["text_xy"][0])
    number_labels = sorted([k for k in g if k.endswith(("1","2","3"))],
                           key=lambda s: g[s]["text_xy"][1])
    print(f"\n  Letter axis X positions (A,B,C,D order): {[round(g[k]['text_xy'][0],1) for k in letter_labels]}")
    print(f"  Number axis Y positions (1,2,3 order): {[round(g[k]['text_xy'][1],1) for k in number_labels]}")
    if len(letter_labels) >= 2:
        spacings = [g[letter_labels[i+1]]["text_xy"][0] - g[letter_labels[i]]["text_xy"][0]
                    for i in range(len(letter_labels)-1)]
        print(f"  Letter spacings: {[round(s,1) for s in spacings]}")
    if len(number_labels) >= 2:
        spacings = [g[number_labels[i+1]]["text_xy"][1] - g[number_labels[i]]["text_xy"][1]
                    for i in range(len(number_labels)-1)]
        print(f"  Number spacings: {[round(s,1) for s in spacings]}")
