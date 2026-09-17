#!/usr/bin/env python3
"""Verify that TP-104 OVERLAY.dxf has STR and MECH geometry coincident at every
TP104-* grid intersection.

For each grid label (A/B/C/D and 1/2/3) we expect to see TWO axes in the
overlay — one from MECH, one from transformed STR — both at the same coordinate.
We find them by walking all LINE entities and grouping by orientation
(vertical = letter axis, horizontal = number axis), then picking the
unique long lines that line up with each label position.
"""

import ezdxf
import re
import numpy as np
from collections import defaultdict
from pathlib import Path

OVERLAY = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 OVERLAY.dxf"

doc = ezdxf.readfile(OVERLAY)
ms = doc.modelspace()

# Collect all LINE entities (modelspace + inside blocks via INSERTs)
lines = []  # (start, end, is_horiz, layer, source)

def walk_modelspace():
    for e in ms:
        if e.dxftype() == "LINE":
            s, t = e.dxf.start, e.dxf.end
            layer = e.dxf.layer
            is_horiz = abs(t[0] - s[0]) > abs(t[1] - s[1])
            lines.append((s, t, is_horiz, layer, "modelspace"))
        elif e.dxftype() == "INSERT":
            try:
                for sub in e.virtual_entities():
                    if sub.dxftype() == "LINE":
                        s, t = sub.dxf.start, sub.dxf.end
                        layer = sub.dxf.layer
                        is_horiz = abs(t[0] - s[0]) > abs(t[1] - s[1])
                        # Identify source block by name prefix
                        source = "MECH" if not e.dxf.name.startswith("_STR_") else "STR"
                        lines.append((s, t, is_horiz, layer, source))
            except Exception:
                pass

walk_modelspace()
print(f"Total LINE entities (incl. via INSERTs): {len(lines)}\n")

# Also collect TEXT positions (the labels themselves)
texts = []  # (text, x, y, source)
def walk_texts():
    for e in ms:
        if e.dxftype() == "TEXT":
            x, y = e.dxf.insert[0], e.dxf.insert[1]
            try:
                if e.dxf.alignment_point:
                    x, y = e.dxf.alignment_point[0], e.dxf.alignment_point[1]
            except Exception:
                pass
            layer = e.dxf.layer
            source = "MECH" if not layer.startswith("_STR_") else "STR"
            texts.append((e.dxf.text.strip(), x, y, source))
    for block in doc.blocks:
        if block.name.startswith("*"):
            continue
        for e in block:
            if e.dxftype() == "TEXT":
                x, y = e.dxf.insert[0], e.dxf.insert[1]
                try:
                    if e.dxf.alignment_point:
                        x, y = e.dxf.alignment_point[0], e.dxf.alignment_point[1]
                except Exception:
                    pass
                source = "MECH" if not block.name.startswith("_STR_") else "STR"
                texts.append((e.dxf.text.strip(), x, y, source))

walk_texts()
GRID_RE = re.compile(r"^\s*TP104-([A-D1-3])\s*$")
grid_texts = [(m.group(1), x, y, src) for t, x, y, src in texts
              for m in [GRID_RE.match(t)] if m]

print(f"Grid label TEXT entities: {len(grid_texts)}")
# We expect 7 from MECH (at known positions) + 7 from STR (transformed to same positions)
# → 14 total, but at the SAME coordinates
from collections import Counter
src_counts = Counter(src for _, _, _, src in grid_texts)
print(f"  by source: {dict(src_counts)}")

# Cluster grid label positions to find how many unique positions exist
# (MECH and STR labels should collapse to the same 7 positions)
positions = sorted({(round(x, 0), round(y, 0)) for _, x, y, _ in grid_texts})
print(f"  unique positions: {len(positions)}")
if len(positions) == 7:
    print("  ✓ Perfect — 14 labels collapse to 7 unique positions (MECH+STR aligned)")
elif len(positions) > 7 and len(positions) <= 14:
    print(f"  ⚠ Near-perfect — {len(positions)} positions (some sub-unit drift)")
else:
    print(f"  ✗ Misalignment — {len(positions)} distinct positions, expected 7")

# ---- Compare actual axis LINE positions from each source ------------------
# Group axis lines by source (MECH vs STR) and find their grid axis X/Y
str_vert = []  # vertical STR axis X
mech_vert = []  # vertical MECH axis X
str_horiz = []  # horizontal STR axis Y
mech_horiz = []  # horizontal MECH axis Y

for s, t, horiz, layer, source in lines:
    L = ((t[0]-s[0])**2 + (t[1]-s[1])**2) ** 0.5
    if L < 5000:  # only the long axes
        continue
    if horiz:
        y = (s[1] + t[1]) / 2
        (str_horiz if source == "STR" else mech_horiz).append((y, L, layer))
    else:
        x = (s[0] + t[0]) / 2
        (str_vert if source == "STR" else mech_vert).append((x, L, layer))

print(f"\nLong vertical axis lines (X is constant):")
print(f"  MECH vertical axes: {len(mech_vert)}")
for x, L, layer in sorted(mech_vert):
    print(f"    X={x:>10.1f}  len={L:>9.1f}  layer={layer!r}")
print(f"  STR  vertical axes: {len(str_vert)}")
for x, L, layer in sorted(str_vert):
    print(f"    X={x:>10.1f}  len={L:>9.1f}  layer={layer!r}")

print(f"\nLong horizontal axis lines (Y is constant):")
print(f"  MECH horizontal axes: {len(mech_horiz)}")
for y, L, layer in sorted(mech_horiz, key=lambda v: v[0]):
    print(f"    Y={y:>10.1f}  len={L:>9.1f}  layer={layer!r}")
print(f"  STR  horizontal axes: {len(str_horiz)}")
for y, L, layer in sorted(str_horiz, key=lambda v: v[0]):
    print(f"    Y={y:>10.1f}  len={L:>9.1f}  layer={layer!r}")

# ---- Pair MECH/STR axes by nearest matching coordinate ---------------------
print("\n" + "=" * 70)
print("PAIRING — match each MECH axis with nearest STR axis")
print("=" * 70)

def pair_axes(mech_list, str_list, label, coord_name):
    """For each axis on coord_name, find closest match in the other list."""
    print(f"\n  --- {coord_name} axes ---")
    pairs = []
    for m_coord, m_L, m_layer in sorted(mech_list):
        if not str_list:
            break
        nearest = min(str_list, key=lambda v: abs(v[0] - m_coord))
        s_coord, s_L, s_layer = nearest
        residual = s_coord - m_coord
        pairs.append((m_coord, s_coord, residual, m_L, s_L))
        status = "✓" if abs(residual) < 50 else ("⚠" if abs(residual) < 500 else "✗")
        print(f"    MECH {coord_name}={m_coord:>10.1f} (L={m_L:>7.0f})  vs  "
              f"STR {coord_name}={s_coord:>10.1f} (L={s_L:>7.0f})  "
              f"residual={residual:>+7.2f}  {status}")
    return pairs

vert_pairs = pair_axes(mech_vert, str_vert, "vertical", "X")
horiz_pairs = pair_axes(mech_horiz, str_horiz, "horizontal", "Y")

# ---- Summary ---------------------------------------------------------------
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
all_residuals = [abs(r) for _, _, r, _, _ in vert_pairs] + [abs(r) for _, _, r, _, _ in horiz_pairs]
if not all_residuals:
    print("  No axis pairs to compare.")
elif max(all_residuals) < 50:
    print(f"  ✓ EXCELLENT — max axis residual: {max(all_residuals):.2f} units (< 50)")
    print(f"    RMS: {(sum(r*r for r in all_residuals)/len(all_residuals))**0.5:.2f}")
elif max(all_residuals) < 500:
    print(f"  ⚠ GOOD — max axis residual: {max(all_residuals):.2f} units (< 500)")
else:
    print(f"  ✗ MISALIGNED — max axis residual: {max(all_residuals):.2f} units")

# Grid intersection check: pick C-1 in both sources
# MECH C: text x=216399.6 → find axis x
# MECH 1: text y=-155851.6 → find axis y
# STR C: text x=9175.5 → after transform → ?
# STR 1: text y=24995.8 → after transform → ?
print("\nGrid intersection C-1 check:")
print(f"  MECH C-1 expected: ({216399.6:.1f}, {-155263.69:.1f}) [axis coordinates]")
print(f"  MECH C-1 text at:  ({216399.6:.1f}, {-151652.3:.1f}) [label position]")

# Find STR C axis: take nearest str_vert to 216399.6
if str_vert:
    str_c_x = min(str_vert, key=lambda v: abs(v[0] - 216399.6))
    str_1_y = min(str_horiz, key=lambda v: abs(v[0] - (-155263.69)))
    print(f"  STR  C-1 actual:   ({str_c_x[0]:.1f}, {str_1_y[0]:.1f})")
    dx = str_c_x[0] - 216399.6
    dy = str_1_y[0] - (-155263.69)
    print(f"  delta: ({dx:+.2f}, {dy:+.2f})")
