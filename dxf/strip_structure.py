#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
"""Strip leftover annotations from TP-104 STR GA_clean.dxf.

REMOVES (top-level INSERTs and their block definitions):
  Mark-*              — callout markers (with WIPEOUT mask rectangles)
  StraightDimension-* — dimension lines + extension lines
  Text-*              — text bounding boxes / underlines
  SectionMark-*       — section cut-plane symbols (labels already stripped)
  Line-*              — short dimension extension lines

KEEPS:
  GridLine-*          — TP104-* axis lines and labels
  Part-*              — structural members
  Bolt-*              — bolts
  Connection-*        — bolt/weld connection symbols
  ReferenceModel-*    — external reference geometry

ALSO REMOVES:
  Any WIPEOUT entity anywhere (background mask = always annotation)
"""

import ezdxf
import re
from collections import Counter

SRC = ROOT / "dxf/TP-104 STR GA_clean.dxf"
DST = ROOT / "dxf/TP-104 STR GA_clean3.dxf"

# Block-name prefixes to remove
REMOVE_PREFIXES = (
    "Mark-",
    "StraightDimension-",
    "Text-",
    "SectionMark-",
    "Line-",
)

# Block-name prefixes to ALWAYS keep
KEEP_PREFIXES = (
    "GridLine-",
    "Part-",
    "Bolt-",
    "Connection-",
    "ReferenceModel-",
    "*Model_Space",
    "*Paper_Space",
)

# Grid label regex — used to confirm preservation, NOT for filtering
GRID_RE = re.compile(r"^\s*TP104-[A-D1-3]\s*$")

doc = ezdxf.readfile(SRC)
msp = doc.modelspace()

# Step 1: identify blocks to remove
all_blocks = {b.name: b for b in doc.blocks}
blocks_to_remove = []
for name in all_blocks:
    if name.startswith("*"):
        continue
    if any(name.startswith(p) for p in KEEP_PREFIXES):
        continue
    if any(name.startswith(p) for p in REMOVE_PREFIXES):
        blocks_to_remove.append(name)

print(f"Block categories — REMOVE prefixes {REMOVE_PREFIXES}")
print(f"Blocks scheduled for removal: {len(blocks_to_remove)}")

# Step 2: remove top-level INSERTs that reference removed blocks
removed_inserts = 0
to_delete = []
for e in msp:
    if e.dxftype() == "INSERT":
        if e.dxf.name in blocks_to_remove:
            to_delete.append(e)
            removed_inserts += 1

for e in to_delete:
    msp.delete_entity(e)

print(f"Top-level INSERTs removed: {removed_inserts}")

# Step 3: delete the blocks themselves
deleted_blocks = 0
for name in blocks_to_remove:
    if name in doc.blocks:
        try:
            doc.blocks.delete_block(name, safe=False)
            deleted_blocks += 1
        except Exception as ex:
            print(f"  warn: could not delete {name}: {ex}")
print(f"Blocks deleted from BLOCKS section: {deleted_blocks}")

# Step 4: scrub any remaining WIPEOUT entities (mask rectangles)
wipeouts_removed = 0
for block in list(doc.blocks):
    if block.name.startswith("*"):
        continue
    for e in list(block):
        if e.dxftype() == "WIPEOUT":
            try:
                block.delete_entity(e)
                wipeouts_removed += 1
            except Exception:
                pass
print(f"WIPEOUT entities scrubbed: {wipeouts_removed}")

# Step 5: audit — confirm grid labels are still there
grid_count = 0
for block in doc.blocks:
    if block.name.startswith("*"):
        continue
    for e in block:
        if e.dxftype() == "TEXT":
            t = e.dxf.text
            if GRID_RE.match(t.strip()):
                grid_count += 1
print(f"Grid labels (TP104-*) remaining: {grid_count}")

# Step 6: audit — entity counts after cleanup
type_counts = Counter()
for e in msp:
    type_counts[e.dxftype()] += 1
print(f"\nModelspace entity types after strip: {dict(type_counts)}")

# Step 7: save
doc.saveas(DST)
print(f"\nSaved: {DST}")

# File size
import os
print(f"  size: {os.path.getsize(SRC) / 1e6:.2f} MB → {os.path.getsize(DST) / 1e6:.2f} MB")
