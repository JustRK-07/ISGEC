#!/usr/bin/env python3
"""Deep-dive: find WIPEOUTs (masking rectangles), check layer colors (for green dim
lines), and locate any LINE entities outside GridLine-* blocks that look like
annotation/dimension residue."""

import ezdxf
from collections import Counter, defaultdict

PATH = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 STR GA_clean.dxf"
doc = ezdxf.readfile(PATH)

# 1. Layer table: which layers exist and what ACI color
print("=" * 70)
print("LAYER TABLE — color, linetype, on/off")
print("=" * 70)
green_layers = []
for layer in doc.layers:
    name = layer.dxf.name
    color = layer.dxf.color
    on = layer.is_on()
    lt = layer.dxf.linetype
    if 2 <= color <= 5 or color == 3:  # green = ACI 3
        green_layers.append((name, color))
    print(f"  layer={name!r:<30}  color=ACI{color:<3}  on={on}  linetype={lt}")

print(f"\nGreen-tinted layers: {green_layers}")

# 2. WIPEOUT entities — these are masking rectangles, ALWAYS annotation
print("\n" + "=" * 70)
print("WIPEOUT entities — masking rectangles behind labels")
print("=" * 70)
wipeout_locs = []
for block in doc.blocks:
    for e in block:
        if e.dxftype() == "WIPEOUT":
            try:
                # WIPEOUT has vertices like LWPOLYLINE
                n_verts = len(list(e.vertices())) if hasattr(e, "vertices") else 0
                wipeout_locs.append((block.name, n_verts, e.dxf.layer if hasattr(e.dxf, "layer") else "?"))
            except Exception:
                wipeout_locs.append((block.name, "?", "?"))

print(f"Total WIPEOUT: {len(wipeout_locs)}")
print("\nBy block (which blocks contain masking rectangles):")
by_block = Counter(b for b, _, _ in wipeout_locs)
for block, c in by_block.most_common(20):
    print(f"  {block!r:<50} {c}")

# Vertex distribution
vert_counts = Counter(v for _, v, _ in wipeout_locs)
print(f"\nVertex counts: {dict(vert_counts)}")

# 3. LINE entities OUTSIDE GridLine-* / Part-* / Bolt-* blocks — likely annotation residue
print("\n" + "=" * 70)
print("LINE entities per block (excluding GridLine/Part/Bolt)")
print("=" * 70)
unknown_line_blocks = []
for block in doc.blocks:
    if block.name.startswith("*"):
        continue
    if "GridLine" in block.name or "Part-" in block.name or "Bolt-" in block.name:
        continue
    line_count = sum(1 for e in block if e.dxftype() == "LINE")
    if line_count > 0:
        unknown_line_blocks.append((block.name, line_count))

print(f"Non-standard blocks with LINE entities: {len(unknown_line_blocks)}")
for name, c in sorted(unknown_line_blocks, key=lambda x: -x[1])[:20]:
    print(f"  {name!r:<50} {c} LINEs")

# 4. Are there any LINE entities in modelspace directly? (Already 0 from prior script)
# But check INSERT blocks at modelspace level
print("\n" + "=" * 70)
print("MODELSpace INSERTs — block names referenced at top level")
print("=" * 70)
top_blocks = Counter()
for e in doc.modelspace():
    if e.dxftype() == "INSERT":
        top_blocks[e.dxf.name] += 1
for name, c in top_blocks.most_common(30):
    print(f"  {name!r:<50} {c}")
