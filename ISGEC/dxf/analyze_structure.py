#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
"""Analyze the STRUCTURE DXF for annotation leftovers, hexagons, dimension lines,
and any non-essential shapes — same audit we did for MECH."""

import ezdxf
from collections import Counter, defaultdict
import json
import re

PATH = ROOT / "dxf/TP-104 STR GA_clean.dxf"

doc = ezdxf.readfile(PATH)
msp = doc.modelspace()

# Per-layer entity counts
layer_counts = defaultdict(Counter)
all_entities = Counter()
grid_label_count = 0
text_samples = []

GRID_RE = re.compile(r"TP104[-\s]?[A-D1-3]\b", re.I)

def walk(entity, layer, ctx="modelspace"):
    """Recursive walk into INSERTs and POLYLINE vertices."""
    global grid_label_count
    et = entity.dxftype()
    layer_counts[ctx][(layer, et)] += 1
    all_entities[(ctx, et)] += 1
    if et in ("TEXT", "MTEXT"):
        text = entity.dxf.text if et == "TEXT" else entity.text
        if GRID_RE.search(text):
            grid_label_count += 1
            text_samples.append((ctx, layer, et, text[:80]))
    if et == "INSERT":
        try:
            for sub in entity.virtual_entities():
                walk(sub, layer, ctx=f"block:{entity.dxf.name}")
        except Exception:
            pass

# Walk modelspace
for e in msp:
    walk(e, e.dxf.layer if hasattr(e.dxf, "layer") else "?")

# Also iterate all blocks to find entity types stored in BLOCKS but referenced by INSERTs
block_entity_types = Counter()
for block in doc.blocks:
    if block.name.startswith("*Model_Space") or block.name.startswith("*Paper_Space"):
        continue
    for e in block:
        try:
            et = e.dxftype()
            block_entity_types[(block.name, et)] += 1
        except Exception:
            pass

# Color distribution (key for finding green dimension lines)
color_layer = Counter()
for e in msp:
    layer = e.dxf.layer if hasattr(e.dxf, "layer") else "?"
    color = getattr(e.dxf, "color", 256)
    color_layer[(color, layer)] += 1

# Detect LWPOLYLINE vertex counts (for hexagons etc.)
hex_locations = []
for e in msp:
    if e.dxftype() == "LWPOLYLINE":
        try:
            n = len(list(e.vertices()))
            if n == 6:
                layer = e.dxf.layer
                center = (sum(v[0] for v in e.vertices()) / n,
                          sum(v[1] for v in e.vertices()) / n)
                hex_locations.append((layer, center))
        except Exception:
            pass

print("=" * 70)
print(f"FILE: {PATH}")
print("=" * 70)

print("\n--- Modelspace top entity types ---")
ms_types = Counter()
for e in msp:
    try:
        ms_types[e.dxftype()] += 1
    except Exception:
        pass
for et, c in sorted(ms_types.items(), key=lambda x: -x[1])[:30]:
    print(f"  {et:<25} {c}")

print(f"\n--- Hexagons (6-vert LWPOLYLINE) in modelspace: {len(hex_locations)} ---")
layers = Counter(l for l, _ in hex_locations)
for layer, c in layers.most_common():
    print(f"  layer={layer!r}: {c}")

print(f"\n--- Grid label texts preserved: {grid_label_count} ---")
for ctx, layer, et, t in text_samples[:10]:
    print(f"  [{ctx}] layer={layer!r}: {t!r}")

print("\n--- Color distribution (top 20) ---")
for (color, layer), c in color_layer.most_common(20):
    color_name = {1:"red",2:"yellow",3:"green",4:"cyan",5:"blue",6:"magenta",
                  7:"white/black",8:"gray",9:"lightgray"}.get(color, f"ACI{color}")
    print(f"  color={color:>3} ({color_name:<11}) layer={layer!r:<30} {c}")

print("\n--- Block inventory (BLOCKS section entities) ---")
be_types = Counter()
for block in doc.blocks:
    for e in block:
        try:
            be_types[e.dxftype()] += 1
        except Exception:
            pass
for et, c in sorted(be_types.items(), key=lambda x: -x[1])[:15]:
    print(f"  {et:<25} {c}")

print("\n--- Block names containing geometry ---")
for block in doc.blocks:
    if block.name.startswith("*"):
        continue
    n_ents = len(list(block))
    if n_ents > 0:
        print(f"  {block.name:<40} {n_ents} entities")
