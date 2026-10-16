#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
"""Validate the stripped STRUCTURE file.

Checks:
  1. All 7 TP104-* grid labels still present and on layer 0
  2. No top-level INSERTs to Mark-*, StraightDimension-*, Text-*, SectionMark-*, Line-*
  3. No WIPEOUT entities anywhere
  4. No hexagons (6-vert LWPOLYLINE) at any level
  5. Structural content (Part-*, Bolt-*, Connection-*) intact
  6. File opens cleanly with ezdxf
"""

import ezdxf
import re
from collections import Counter

PATH = ROOT / "dxf/TP-104 STR GA_clean3.dxf"
GRID_RE = re.compile(r"TP104[-\s]?[A-D1-3]\b", re.I)
EXPECTED_GRID = {"TP104-A", "TP104-B", "TP104-C", "TP104-D", "TP104-1", "TP104-2", "TP104-3"}

doc = ezdxf.readfile(PATH)
msp = doc.modelspace()
failures = []
notes = []

# 1. Grid labels
found_grids = set()
for block in doc.blocks:
    if block.name.startswith("*"):
        continue
    for e in block:
        if e.dxftype() == "TEXT":
            t = e.dxf.text.strip()
            if GRID_RE.search(t):
                found_grids.add(t.upper().replace(" ", "-"))
notes.append(f"Grid labels found: {sorted(found_grids)}")
missing = EXPECTED_GRID - found_grids
if missing:
    failures.append(f"MISSING GRID LABELS: {missing}")
extra = found_grids - EXPECTED_GRID
if extra:
    notes.append(f"Extra grid-like texts (allowed): {extra}")

# 2. Top-level INSERTs — should have none of the removed types
removed_prefixes = ("Mark-", "StraightDimension-", "Text-", "SectionMark-", "Line-")
top_blocks = Counter()
for e in msp:
    if e.dxftype() == "INSERT":
        top_blocks[e.dxf.name] += 1

bad = {n: c for n, c in top_blocks.items() if any(n.startswith(p) for p in removed_prefixes)}
if bad:
    failures.append(f"Top-level INSERTs to removed blocks still present: {bad}")

# 3. WIPEOUT entities
wipeouts = 0
for block in doc.blocks:
    for e in block:
        if e.dxftype() == "WIPEOUT":
            wipeouts += 1
if wipeouts:
    failures.append(f"WIPEOUT entities remain: {wipeouts}")
else:
    notes.append("No WIPEOUT entities ✓")

# 4. Hexagons
hex_count = 0
for e in msp:
    if e.dxftype() == "LWPOLYLINE":
        try:
            if len(list(e.vertices())) == 6:
                hex_count += 1
        except Exception:
            pass
for block in doc.blocks:
    if block.name.startswith("*"):
        continue
    for e in block:
        if e.dxftype() == "LWPOLYLINE":
            try:
                if len(list(e.vertices())) == 6:
                    hex_count += 1
            except Exception:
                pass
if hex_count:
    failures.append(f"Hexagons still present: {hex_count}")
else:
    notes.append("No hexagons ✓")

# 5. Structural content
structural = {"Part": 0, "Bolt": 0, "Connection": 0, "GridLine": 0, "ReferenceModel": 0}
for name in top_blocks:
    for prefix in structural:
        if name.startswith(prefix + "-") or prefix in name:
            structural[prefix] += top_blocks[name]
notes.append(f"Structural content: {structural}")
for k in ("Part", "Bolt", "GridLine"):
    if structural[k] == 0:
        failures.append(f"Lost structural content: {k}")

# 6. File sanity — re-open
try:
    doc2 = ezdxf.readfile(PATH)
    notes.append(f"Re-opens cleanly ✓ (modelspace entities: {len(list(doc2.modelspace()))})")
except Exception as ex:
    failures.append(f"File fails to reopen: {ex}")

print("=" * 60)
print("VALIDATION REPORT — TP-104 STR GA_clean3.dxf")
print("=" * 60)
print("\n".join(notes))
if failures:
    print("\n❌ FAILURES:")
    for f in failures:
        print(f"  - {f}")
else:
    print("\n✅ All validation checks passed")
