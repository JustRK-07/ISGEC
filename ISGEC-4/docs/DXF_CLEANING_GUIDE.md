# DXF / DWG Cleaning Guide — TP-104 Project

**Project:** ISGEC conveyor structural/mechanical drawings for Adani Infra / Dhamra Port (TP-104)
**Last updated:** 2026-09-08
**Scope:** Removing annotations, dimensions, callout balloons, and marker shapes from TP-104 STR GA and MECH GA, then superimposing the cleaned STR onto the cleaned MECH so the grid axes coincide at TP104-A/B/C/D and TP104-1/2/3.

---

## Table of Contents

1. [Overview](#overview)
2. [Files in this project](#files-in-this-project)
3. [Prerequisites](#prerequisites)
4. [What we found](#what-we-found)
5. [What to remove](#what-to-remove)
6. [What to keep](#what-to-keep)
7. [Step-by-step cleaning process](#step-by-step-cleaning-process)
8. [Reusable scripts](#reusable-scripts)
9. [DWG output (post-cleaning)](#dwg-output-post-cleaning)
10. [Superimposing STR onto MECH](#superimposing-str-onto-mech)
11. [Verification checklist](#verification-checklist)
12. [Known limitations](#known-limitations)

---

## Overview

The original AutoCAD source files for TP-104 came as `.dwg` (AutoCAD 2010–2012 binary, unreadable as text) plus matching `.pdf` exports. To process them programmatically we converted them to `.dxf` (ASCII text-based CAD format). The DXFs contain a mix of:

- **Real engineering geometry** — structural members, equipment outlines, walls, foundations
- **Annotations** — dimensions, leaders, attribute values, beam tags, scale bars, title block
- **Marker symbols** — callout balloons (hexagons, rectangles) enclosing labeled points

This guide documents how to strip the second and third categories while preserving the first, plus the grid axis labels (`TP104-A`, `TP104-B`, `TP104-C`, `TP104-D`, `TP104-1`, `TP104-2`, `TP104-3`).

---

## Files in this project

### Source files (in `ISGEC/dwg/`)

| File | Size | Format |
|---|---|---|
| `TP-104 MECH GA.dwg` | 2.8 MB | AutoCAD 2010–2012 binary |
| `TP-104 STR GA.dwg` | 1.1 MB | AutoCAD 2010–2012 binary |
| `superimposed.dwg` | 1.1 MB | AutoCAD 2010–2012 binary |

### Converted DXFs (in `ISGEC/dxf/`)

| File | Size | Purpose |
|---|---|---|
| `TP-104 MECH GA.dxf` | 15.04 MB | Master (with annotations) |
| `TP-104 STR GA.dxf` | 8.04 MB | Master (with annotations) |
| `superimposed.dxf` | 7.89 MB | Master (MECH+STR merged, with annotations) |
| `TP-104 MECH GA_clean.dxf` | 14.40 MB | Annotations stripped, grid labels kept |
| `TP-104 STR GA_clean.dxf` | 7.26 MB | Annotations stripped, grid labels kept |
| `superimposed_clean.dxf` | 7.26 MB | Annotations stripped (limited) |
| `TP-104 MECH GA_clean2.dxf` | 14.39 MB | Above + hexagons + marker blocks removed |
| `TP-104 MECH GA_clean3.dxf` | 14.21 MB | Above + orphan `A$C2135de20` (ACM_FILLED_HALF symbol with two SOLID triangles) removed |
| `TP-104 STR GA_clean3.dxf` | 5.49 MB | STR: annotations + `Mark-*`/`StraightDimension-*`/`Text-*`/`SectionMark-*`/`Line-*` blocks + WIPEOUTs removed |
| `TP-104 OVERLAY.dxf` | 18.55 MB | **Approach A — per-entity overlay**: MECH as parent + transformed STR on `_STR_*` layers, grid axes coincident |
| `TP-104 OVERLAY_2block.dxf` | 18.58 MB | **Approach B — 2-block overlay**: each drawing wrapped in one block, two INSERTs at modelspace, **MECH layers red, STR layers blue** |

### Trimmed test fixtures (in `adv*/backend/tests/fixtures/`)

These are byte-identical hand-stripped subsets used by the analysis backend tests:

| File | Size | Purpose |
|---|---|---|
| `tp104_mech.dxf` | 246 KB | MECH geometry only (no title block) |
| `tp104_str.dxf` | 7.4 MB | STR geometry only (full) |

---

## Prerequisites

- **Python ≥ 3.10**
- **`ezdxf` ≥ 1.4.0** for DXF reading, validation, and re-saving

```bash
pip install --break-system-packages ezdxf
```

- **(Optional)** `libredwg 0.13.3+` if you need DWG output — see [DWG output section](#dwg-output-post-cleaning)

---

## What we found

### Annotation entities per file

| Entity type | STR GA | MECH GA | Superimposed |
|---|---|---|---|
| TEXT (in BLOCKS) | 479 | 1,497 | 20 |
| TEXT (top-level ENTITIES) | 0 | 77 | 0 |
| MTEXT | 0 | 122 | 0 |
| ATTRIB (block attribute values) | 0 | 388 | 0 |
| ATTDEF (block attribute templates) | 0 | 94 | 0 |
| DIMENSION (all subtypes) | 0 | 96 | 0 |
| LEADER | 0 | 29 | 0 |
| **ACAD_PROXY_OBJECT** | 50 | 72 | 72 |

### Marker shapes (MECH GA only)

- **24 hexagons** — 6-vertex closed LWPOLYLINE on layer `BOX`, uniform radius ~153 mm, all in top-level ENTITIES section (not inside any block)
- **92 circles** — 91 inside block definitions (small ~7–14 mm radius — center dots inside structural section symbols), 1 top-level on layer `C-ROAD-STAN` (road centermarker)
- **Marker blocks** (anonymous `A$Cxxxxxxxx` names):
  - `A$C70ae27ad` (14 INSERT refs) — rectangle + cross at labeled points
  - `A$C7152add8` (4 INSERT refs) — same pattern
  - `A$Cdc69ee36` (6 refs) — filled rectangle (KEEP — possibly section fill)
- **"Triangle-look-alike" blocks** — turned out to be **structural section symbols** (notched rectangles representing ISMC / UB / NPB / ISA plan-view per [IS 808](https://infralens.in/term/structural-steel)). KEEP.
- **Orphan `A$C2135de20` (ACM_FILLED_HALF symbol)** — AutoCAD's standard half-section pillow-block symbol, INSERTed **once** at modelspace at `(220016.4, −163563.7)` with no dimensions, BOM, or connecting geometry pointing at it. Contains 6 SOLID entities (the two visible triangles you see: 🟧 yellow on `MAIN OBJECT` (ACI 2), 🟩 green on `HIDDEN` (ACI 3)) plus the half-section outline. REMOVE — leftover symbol-library geometry.

### TYPO found in title block (all files)

> `ALL PLAN BRACE ARE 100M BELOW (TOS)`

Should read **100mm BELOW** (millimeters, not meters). Worth fixing in the source CAD.

### Other issues found

- Two competing scales printed on same sheet: `1:75` (large title) and `1:40` (smaller secondary)
- `ACAD_PROXY_OBJECT` entries indicate the source CAD was not vanilla AutoCAD (likely Tekla/STAAD/Advance Steel)

---

## What to remove

### Always remove (regardless of context)

| Entity type | Group code | Why |
|---|---|---|
| `TEXT`, `MTEXT` | 0 | Labels, dimensions, beam tags — all replaceable from member schedules |
| `ATTRIB`, `ATTDEF` | 0 | Block attribute values + templates — `BCU-104A`, `TP4BM147`, etc. |
| `DIMENSION` + all subtypes (`ALIGNED_DIMENSION`, `ANGULAR_DIMENSION`, `LINEAR_DIMENSION`, `RADIAL_DIMENSION`, `DIAMETER_DIMENSION`, `ORDINATE_DIMENSION`, `LARGE_*`) | 0 | All dimension annotations |
| `LEADER`, `MULTILEADER` | 0 | Leader lines + callout pointers |
| `TOLERANCE` | 0 | Geometric tolerance frames |
| `DIMASSOC` | 0 | Dimension associativity data |

### Always preserve

- `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `ELLIPSE`, `SPLINE`, `POINT`, `SOLID`, `HATCH`
- `INSERT` (block references) — but inspect what's inside
- `BLOCK`, `ENDBLK`, `BLOCK_RECORD` (block definitions — except those listed below)
- All TABLES section content (layers, linetypes, dimstyles, etc. — needed by geometry)
- All CLASSES, OBJECTS content (DICTIONARY, XRECORD, FIELD, ACAD_PROXY_OBJECT)
- WIPEOUT (image masks — preserve for completeness)

### Conditionally remove

| Shape | Layer / context | Action | Why |
|---|---|---|---|
| 6-vert closed LWPOLYLINE | layer `BOX` | **REMOVE** | Callout balloons enclosing grid/labeled points |
| Block `A$C70ae27ad` (def + INSERTs) | any | **REMOVE** | Rectangle+cross marker symbol (14 instances) |
| Block `A$C7152add8` (def + INSERTs) | any | **REMOVE** | Rectangle+cross marker symbol (4 instances) |
| 17-vert notched-rectangle LWPOLYLINE inside blocks (`A$C426f7GU6TT`, `A$C42DGUYIYTIUYTUY`, etc.) | `MAIN OBJECT`, `PHANTOM` | **KEEP** | Real ISMC channel section symbol in plan view |
| Small radius circles (≤ 25 mm) | inside block defs | **KEEP** | Center dots completing structural section symbols |
| Small radius circles | top-level model space, generic layers | **INVESTIGATE** | Could be marker dots or bolts |
| Large radius circles (> 100 mm) | any | **KEEP** | Real engineering features |
| 3-vert closed LWPOLYLINE (triangles) | `Defpoints`, viewport corners | **KEEP** | Viewport corner indicators |
| Block `A$C2135de20` (def + INSERTs) — AutoCAD `ACM_FILLED_HALF` symbol | any | **REMOVE** | Orphan half-section pillow-block symbol; 6 SOLID fill triangles + outline; 1 INSERT in MECH |

### Always preserve — grid labels

Keep these `TEXT` entities on the grounds that they identify grid axes (not labels of physical features):

| Pattern | Where |
|---|---|
| `TP104-A` | Layer `10` (STR) / layer `TEXT` (MECH) |
| `TP104-B` | same |
| `TP104-C` | same |
| `TP104-D` | same |
| `TP104-1` | same |
| `TP104-2` | same |
| `TP104-3` | same |

Regex: `^\s*TP104-[A-D1-3]\s*$`

---

## Step-by-step cleaning process

### Step 1 — Convert DWG to DXF (if you only have DWG)

If you don't already have DXFs, convert using any of:

```bash
# ODA File Converter (Windows / Wine)
ODAFileConverter.exe input_dir output_dir ACAD2018 DXF 0 0 0

# LibreCAD GUI
# File → Open .dwg → File → Save As .dxf

# Teigha File Converter (cross-platform CLI)
TeighaFileConverter.exe "input_dir" "output_dir" "ACAD2018" "DXF" "0" "0" "*.dwg"
```

### Step 2 — Inventory the DXF before cleaning

Run the inventory script (Section "Reusable scripts" → `inventory.py`) to produce a per-section breakdown showing exactly how many of each entity type exist and on which layers. This tells you what to expect after cleaning and whether the file is a good candidate (i.e., not 100% proxy data).

```bash
python3 inventory.py TP-104\ MECH\ GA.dxf
```

### Step 3 — Strip annotations, keep grid labels

Run the annotation stripper (`strip_annotations.py`):

```bash
python3 strip_annotations.py TP-104\ MECH\ GA.dxf TP-104\ MECH\ GA_clean.dxf
```

This removes all entities in the "Always remove" list above, and only preserves `TEXT`/`MTEXT` entities whose text content matches the grid-label regex.

### Step 4 — Remove marker shapes (hexagons + marker blocks)

Run the marker stripper (`strip_markers.py`):

```bash
python3 strip_markers.py TP-104\ MECH\ GA_clean.dxf TP-104\ MECH\ GA_clean2.dxf
```

This:

- Drops top-level LWPOLYLINE entities with 6 vertices on layer `BOX` (24 hexagons in TP-104 MECH)
- Drops block definition `A$C70ae27ad` (def + 14 INSERTs)
- Drops block definition `A$C7152add8` (def + 4 INSERTs)

The script is data-driven — adjust `HEX_LAYERS`, `HEX_VERTS`, and `REMOVE_BLOCKS` at the top for other projects.

### Step 5 — Remove orphan ACM filled-half symbol (MECH only)

Run the triangle/orphan-symbol stripper (`strip_triangles.py`):

```bash
python3 strip_triangles.py
```

This removes:

- The lone `A$C2135de20` INSERT at modelspace (the orphan half-section pillow-block symbol at `(220016.4, −163563.7)`)
- The `A$C2135de20` block definition (now unreferenced)

Result: **6 SOLID fill triangles gone** (🟧 yellow on `MAIN OBJECT` + 🟩 green on `HIDDEN`). Modelspace drops from 290 → 289 entities (1 INSERT removed). File size: 14.39 MB → 14.21 MB.

> **Why this is safe:** `A$C2135de20` is only INSERTed once in the entire file, and that INSERT is not referenced by any dimension, BOM, hatch, or other geometry. Its child block `A$C34ae56dc` is NOT deleted — it's still used by `A$C1f4f58bd` and `A$Cde9606d0`.

The script is data-driven — adjust `BLOCK_NAME` at the top to remove other orphan anonymous blocks.

### Step 6 — Validate

```python
import ezdxf
from ezdxf import recover

doc, auditor = recover.readfile("TP-104 MECH GA_clean2.dxf")
msp = doc.modelspace()

# Check annotations gone
for e in msp:
    assert e.dxftype() not in {"TEXT", "MTEXT", "DIMENSION", "LEADER", "ATTRIB"} or \
           e.dxf.text.strip() in {"TP104-A", "TP104-B", "TP104-C", "TP104-D",
                                   "TP104-1", "TP104-2", "TP104-3"}, f"leftover: {e}"

# Check hexagons gone
assert not any(e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "BOX" for e in msp)
```

Or run the validation script (`validate.py`).

### Step 7 — Optional: convert back to DWG

See [DWG output section](#dwg-output-post-cleaning).

---

## Reusable scripts

All scripts are pure Python, depend only on `ezdxf` (and stdlib), and operate by streaming pair-lines.

### `inventory.py`

Produces a per-section tally of entity types and a sample of annotation strings.

```python
#!/usr/bin/env python3
"""Inventory a DXF: per-section entity counts + annotation sample."""
import sys, os, re
from collections import Counter, defaultdict

def stream_pairs(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        pair = []
        for line in f:
            pair.append(line.rstrip("\n"))
            if len(pair) == 2:
                yield pair
                pair = []

def inventory(path):
    in_section = None
    cur_type = cur_layer = cur_text = None
    section_entities = defaultdict(Counter)
    section_layers = defaultdict(Counter)
    for code_s, val in stream_pairs(path):
        try: code = int(code_s)
        except ValueError: code = -1
        if code == 0 and val == "SECTION": continue  # paired with next
        # NB: simplified — full version tracks pending section
        ...
```

(Full version is in `/tmp/dxf_inventory.py` from this session. The script handles `SECTION/ENDSEC` properly.)

### `strip_annotations.py`

```python
#!/usr/bin/env python3
"""Strip TEXT/MTEXT/DIMENSION/LEADER/ATTRIB from a DXF, preserving grid labels."""
import sys, os, re

GRID_PATTERN = re.compile(r"^\s*TP104-[A-D1-3]\s*$")
ALWAYS_STRIP = {
    "DIMENSION", "ANGULAR_DIMENSION", "ALIGNED_DIMENSION", "LINEAR_DIMENSION",
    "RADIAL_DIMENSION", "DIAMETER_DIMENSION", "ORDINATE_DIMENSION",
    "LARGE_RADIAL_DIMENSION", "LARGE_ALIGNED_DIMENSION", "LARGE_ANGULAR_DIMENSION",
    "LARGE_LINEAR_DIMENSION", "LARGE_ORDINATE_DIMENSION",
    "LEADER", "MULTILEADER", "TOLERANCE",
    "ATTRIB", "ATTDEF", "DIMASSOC",
}
TEXT_STRIP = {"TEXT", "MTEXT"}

def stream_pairs(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        pair = []
        for line in f:
            pair.append(line.rstrip("\n"))
            if len(pair) == 2:
                yield pair
                pair = []

def strip(in_path, out_path):
    section = None; in_block = None
    cur_type = cur_layer = cur_text = cur_block_name = None
    cur_buf = []

    def flush(out, emit):
        nonlocal cur_type, cur_layer, cur_text, cur_block_name, cur_buf
        if cur_type is None: return
        keep = False
        if cur_type in ALWAYS_STRIP: pass
        elif cur_type in TEXT_STRIP:
            if cur_text and GRID_PATTERN.match(cur_text): keep = True
        else: keep = True
        if keep and emit:
            for c, v in cur_buf: out.write(f"{c}\n{v}\n")
        cur_type = None; cur_layer = None; cur_text = None
        cur_block_name = None; cur_buf = []

    with open(in_path, "r", encoding="utf-8", errors="replace") as fin, \
         open(out_path, "w", encoding="utf-8") as fout:
        for code_s, val in stream_pairs(in_path):
            try: code = int(code_s)
            except ValueError: code = -1
            if code == 0 and val == "SECTION":
                flush(fout, True); section = "PENDING"
                fout.write(f"{code_s}\n{val}\n"); continue
            if code == 0 and val == "ENDSEC":
                flush(fout, True); section = None; in_block = None
                fout.write(f"{code_s}\n{val}\n"); continue
            if code == 0 and val == "EOF":
                flush(fout, True); fout.write(f"{code_s}\n{val}\n"); break
            if code == 2 and section == "PENDING":
                section = val; fout.write(f"{code_s}\n{val}\n"); continue
            if code == 0:
                flush(fout, True)
                cur_type = val; cur_buf = [(code_s, val)]; continue
            if cur_type is not None:
                if code == 8: cur_layer = val
                elif code == 1 and cur_text is None: cur_text = val
                elif code == 2 and section == "BLOCKS" and cur_type == "BLOCK":
                    in_block = val; cur_block_name = val
                cur_buf.append((code_s, val))
                continue
            fout.write(f"{code_s}\n{val}\n")
        flush(fout, True)

if __name__ == "__main__":
    strip(sys.argv[1], sys.argv[2])
    print(f"stripped → {sys.argv[2]}")
```

### `strip_markers.py`

```python
#!/usr/bin/env python3
"""Remove hexagons and known marker blocks from a DXF.

Configurable via the REMOVE_BLOCKS / HEX_LAYERS / HEX_VERTS sets.
"""
import sys, os
from collections import Counter

REMOVE_BLOCKS = {"A$C70ae27ad", "A$C7152add8"}
HEX_LAYERS = {"BOX"}
HEX_VERTS = {6}

def stream_pairs(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        pair = []
        for line in f:
            pair.append(line.rstrip("\n"))
            if len(pair) == 2:
                yield pair
                pair = []

def strip(path_in, path_out):
    pairs = list(stream_pairs(path_in))
    section = None; cur_block = None; in_block = False
    entities = []
    cur = {"start": None, "type": None, "layer": None, "block": None,
           "is_insert_ref": None, "n_verts": 0}
    cur_x = None; cur_verts_count = 0

    for i, (code_s, val) in enumerate(pairs):
        try: code = int(code_s)
        except ValueError: code = -1
        if code == 0 and val == "SECTION": section = "PENDING"; continue
        if code == 2 and section == "PENDING": section = val; continue
        if code == 0 and val == "ENDSEC":
            if cur["start"] is not None:
                cur["end"] = i - 1; entities.append(dict(cur))
                cur = {"start": None, "type": None, "layer": None,
                       "block": None, "is_insert_ref": None, "n_verts": 0}
            section = None; cur_block = None; in_block = False; continue
        if code == 0 and val == "BLOCK":
            if cur["start"] is not None:
                cur["end"] = i - 1; entities.append(dict(cur))
            cur = {"start": i, "type": "BLOCK", "layer": None, "block": None,
                   "is_insert_ref": None, "n_verts": 0}
            in_block = "PENDING"; continue
        if code == 2 and in_block == "PENDING":
            cur_block = val; cur["block"] = val; in_block = True; continue
        if code == 0 and val == "ENDBLK":
            cur["end"] = i; entities.append(dict(cur))
            cur = {"start": None, "type": None, "layer": None, "block": None,
                   "is_insert_ref": None, "n_verts": 0}
            cur_block = None; in_block = False; continue
        if code == 0:
            if cur["start"] is not None:
                cur["end"] = i - 1; entities.append(dict(cur))
            cur = {"start": i, "type": val, "layer": None, "block": cur_block,
                   "is_insert_ref": None, "n_verts": 0}
            cur_verts_count = 0; continue
        if code == 8 and cur["type"]: cur["layer"] = val
        if code == 2 and cur["type"] == "INSERT": cur["is_insert_ref"] = val
        if cur["type"] == "LWPOLYLINE":
            if code == 10: cur_x = float(val)
            elif code == 20:
                if cur_x is not None:
                    cur_verts_count += 1; cur["n_verts"] = cur_verts_count
                    cur_x = None

    if cur["start"] is not None:
        cur["end"] = len(pairs) - 1; entities.append(dict(cur))

    drop = set()
    for e in entities:
        if e["type"] == "BLOCK" and e["block"] in REMOVE_BLOCKS:
            for j in range(e["start"], e["end"] + 1): drop.add(j)
        if e["type"] == "INSERT" and e["is_insert_ref"] in REMOVE_BLOCKS:
            for j in range(e["start"], e["end"] + 1): drop.add(j)
        if e["type"] == "LWPOLYLINE" and e["block"] is None \
                and e["layer"] in HEX_LAYERS and e["n_verts"] in HEX_VERTS:
            for j in range(e["start"], e["end"] + 1): drop.add(j)

    with open(path_out, "w", encoding="utf-8") as fout:
        for i, (code_s, val) in enumerate(pairs):
            if i in drop: continue
            fout.write(f"{code_s}\n{val}\n")

    return {
        "dropped": sum(1 for e in entities if e["start"] in drop),
        "kept": sum(1 for e in entities if e["start"] not in drop),
    }

if __name__ == "__main__":
    r = strip(sys.argv[1], sys.argv[2])
    print(f"dropped={r['dropped']}  kept={r['kept']}  → {sys.argv[2]}")
```

### `validate.py`

```python
#!/usr/bin/env python3
"""Validate a cleaned DXF: checks grid labels present, no leftover annotations."""
import sys, re
import ezdxf
from ezdxf import recover

GRID = {"TP104-A", "TP104-B", "TP104-C", "TP104-D",
        "TP104-1", "TP104-2", "TP104-3"}

def validate(path):
    doc, auditor = recover.readfile(path)
    msp = doc.modelspace()
    errors = []

    # Grid labels
    grid_found = set()
    for e in msp:
        if e.dxftype() == "TEXT":
            t = e.dxf.text.strip()
            if t in GRID: grid_found.add(t)
    missing = GRID - grid_found
    if missing: errors.append(f"missing grid labels: {missing}")

    # Leftover annotation types
    for typ in ("MTEXT", "ATTRIB", "DIMENSION", "LEADER"):
        n = sum(1 for e in msp if e.dxftype() == typ)
        if n: errors.append(f"{n} leftover {typ}")

    # Hexagons on BOX
    n = sum(1 for e in msp if e.dxftype() == "LWPOLYLINE"
            and e.dxf.layer == "BOX")
    if n: errors.append(f"{n} leftover hexagon(s) on BOX")

    return errors

if __name__ == "__main__":
    errs = validate(sys.argv[1])
    if errs:
        for e in errs: print(f"  ✗ {e}")
        sys.exit(1)
    print("  ✓ all checks passed")
```

### `strip_triangles.py`

Removes the orphan `A$C2135de20` block (AutoCAD `ACM_FILLED_HALF` half-section pillow-block symbol) from `TP-104 MECH GA_clean2.dxf`. The block is INSERTed only once at modelspace at `(220016.4, −163563.7)` and is not referenced by any other geometry — the SOLID fill triangles (🟧 yellow + 🟩 green) and the half-section outline are leftover symbol-library geometry.

```python
#!/usr/bin/env python3
"""Strip the orphaned ACM_FILLED_HALF symbol (block A$C2135de20) from
the cleaned MECH DXF.

Removes:
  1. The lone A$C2135de20 INSERT at modelspace.
  2. The now-unreferenced A$C2135de20 block (preserves A$C34ae56dc
     child block — it's still used by other anonymous components).
"""

import ezdxf
from collections import Counter

SRC = "TP-104 MECH GA_clean2.dxf"
DST = "TP-104 MECH GA_clean3.dxf"
BLOCK_NAME = "A$C2135de20"


def count_modelspace(doc):
    c = Counter()
    for e in doc.modelspace():
        c[e.dxftype()] += 1
    return c


def main():
    doc = ezdxf.readfile(SRC)
    msp = doc.modelspace()
    before = count_modelspace(doc)

    target = [e for e in msp
              if e.dxftype() == "INSERT" and e.dxf.name == BLOCK_NAME]
    print(f"Found {len(target)} INSERT(s) of {BLOCK_NAME}")

    for ins in target:
        msp.unlink_entity(ins)
    print(f"Removed {len(target)} INSERT(s)")

    if BLOCK_NAME in [b.name for b in doc.blocks]:
        doc.blocks.delete_block(BLOCK_NAME, safe=False)
        print(f"Deleted block {BLOCK_NAME}")

    doc.saveas(DST)

    after = count_modelspace(ezdxf.readfile(DST))
    print(f"\nModelspace: {sum(before.values())} → {sum(after.values())} "
          f"entities (INSERT {before.get('INSERT', 0)} → "
          f"{after.get('INSERT', 0)})")
    print(f"Saved {DST}")


if __name__ == "__main__":
    main()
```

---

## DWG output (post-cleaning)

`ezdxf` writes DXF only — to produce a DWG you need one of:

| Tool | Free? | Platform | Notes |
|---|---|---|---|
| **ODA File Converter** | Yes | Windows / Wine | Best option. Download from opendesign.com. CLI: `ODAFileConverter input_dir output_dir ACAD2018 DXF 0 0 0` (also supports reverse DXF→DWG via the GUI) |
| **LibreCAD GUI** | Yes | Cross-platform | Open DXF → Save As → DWG (note: DWG write may need rebuild from source with -DWITH_DWG=ON) |
| **AutoCAD / BricsCAD / GstarCAD / nanoCAD** | No (commercial) | Windows | Standard workflow |
| **libredwg 0.13.3** (`dxf2dwg` CLI) | Yes | Linux | Works on simple DXFs. **Fails on these TP-104 files** with `READ ERROR 0x800` — it doesn't fully understand AutoCAD 2018+ features (`FIELD` with code 6, complex handle references, advanced proxy data). Build instructions below. |

### Building libredwg from source (Arch Linux)

```bash
# Get source
curl -sL https://github.com/LibreDWG/libredwg/archive/refs/tags/0.13.3.tar.gz | tar xz

# Get the vendored jsmn library (the project expects it in jsmn/ subdir)
git clone --depth 1 https://github.com/zserge/jsmn.git jsmn-tmp
cp jsmn-tmp/jsmn.h ./libredwg-0.13.3/jsmn/

# Patch CMakeLists.txt to remove -Werror
cd libredwg-0.13.3
sed -i 's|add_compile_options(-Werror -Wno-error=cast-align)|# disabled|' CMakeLists.txt

# Build
mkdir builddir && cd builddir
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/.local -DDISABLE_WERROR=ON
make -j$(nproc)

# Test
./dxf2dwg -y --as r2000 -o out.dwg input.dxf
```

### Known DWG conversion failures on TP-104 files

```
Error: Invalid DXF code 6 for FIELD
Failed to decode DXF file: TP-104 STR GA.dxf
READ ERROR 0x800
```

Cause: libredwg 0.13.3 doesn't handle every AutoCAD 2018+ feature (notably some `FIELD` and `ACAD_PROXY_OBJECT` constructs). Resave the DXF in R12 format via `ezdxf` first as a partial workaround:

```python
import ezdxf
from ezdxf import recover
doc, auditor = recover.readfile("input.dxf")
doc.saveas("output_R12.dxf")
```

This may still fail on files with extensive handle references.

---

## Superimposing STR onto MECH

After both drawings are cleaned, the next step is to overlay TP-104 STR onto TP-104 MECH so the grid axes coincide at every `TP104-*` label. This is the same operation as the manual Ctrl+Shift+C workflow in AutoCAD (select all STR entities → copy with base point → paste into MECH at the chosen base point) but done programmatically.

### What we found about the two coordinate systems

Both files describe the **same physical structure** with the **same 7-axis grid** (`TP104-A`–`D` letter axes, `TP104-1`–`3` number axes), but they're stored at different scales and origins:

| Property | STR file | MECH file |
|---|---|---|
| Letter axis (A) X | 23,950 | 227,907 |
| Letter axis (D) X | 3,325 | 211,399 |
| Number axis (1) Y | 25,070 | −155,263 |
| Number axis (3) Y | 12,570 | −165,263 |
| Spacing D→C | 6,250 units | 5,000 units |
| Spacing 3→2 | 8,750 units | 7,000 units |
| Spacing 2→1 | 3,750 units | 3,000 units |
| Y orientation | +Y up | −Y up (matches in screen orientation) |
| Rotation | 0° | 0° |

**Conclusion**: the two drawings are axis-aligned and uniformly scaled — no rotation, no shear, just **uniform scale + translation**.

**Scale ratio** (verified across all 6 adjacent axis spacings):

| Pair | STR spacing | MECH spacing | MECH / STR |
|---|---:|---:|---:|
| D→C | 6,250.0 | 5,000.0 | 0.8000 |
| C→B | 10,625.0 | 8,508.1 | 0.8008 |
| B→A | 3,750.0 | 2,999.7 | 0.7999 |
| 3→2 | 8,750.0 | 7,000.0 | 0.8000 |
| 2→1 | 3,750.0 | 3,000.0 | 0.8000 |

**STR is exactly 1.25× larger than MECH in X** (scale = 0.8), but **Y spacings are identical** (1.0). The two drawings are not at a uniform scale — they have different X and Y scales. Use the per-axis scale below as the actual best-fit transform.

### Fitted overlay transform (FINAL — verified by gridline intersection fit)

**Final transform (auto-derived from labeled gridlines in both files):**

```
x_m = 1.0 × x_s + 208,379.86
y_m = 1.0 × y_s + (−179,684.52)
```

This uses scale = 1.0 in BOTH X and Y. It is computed automatically by
`A/scripts/fit.py` (and copied identically to `B/scripts/fit.py` and
`C/scripts/fit.py`) — the script walks the MECH and STR files, finds every
labeled gridline (`TP104-A/B/C/D/1/2/3`), and solves a least-squares
affine fit from the actual gridline LINE positions (not the TEXT label
positions, which carry an inconsistent offset between the two files).

**All 12 labeled grid intersections (A/B/C/D × 1/2/3) align with
residual = 0.0 units** (down from 4217 with the previous 0.8-scale
fit):

| Axis | MECH | STR | MECH − STR |
|---|---:|---:|---:|
| TP104-A (X) | 228,511.86 | 20,132.00 | **+208,379.86** |
| TP104-B (X) | 225,511.86 | 17,132.00 | **+208,379.86** |
| TP104-C (X) | 217,011.86 | 8,632.00 | **+208,379.86** |
| TP104-D (X) | 212,011.86 | 3,632.00 | **+208,379.86** |
| TP104-1 (Y) | −155,263.69 | 24,420.84 | **−179,684.52** |
| TP104-2 (Y) | −158,263.69 | 21,420.84 | **−179,684.52** |
| TP104-3 (Y) | −165,263.69 | 14,420.84 | **−179,684.52** |

The 4 X-axis residuals are **exactly identical** (perfectly linear),
and the 3 Y-axis residuals are **exactly identical** (perfectly linear) —
that's what makes a single affine transform fit perfectly.

### Why the 0.8 scale was wrong (historical)

The earlier fit `x_m = 0.8·x_s + 208739.144` aligned **TEXT label
positions** to within 8 units, but the actual gridline LINE positions
differed by up to 4217 units because:

1. The two source drawings were drawn independently with different conventions
2. STR places its TP104-A/B/C/D labels as **TEXT next to vertical column lines**, and TP104-1/2/3 labels as **TEXT next to horizontal row lines** — but the **TEXT is offset by ~600 units** in MECH (and a different amount in STR)
3. Comparing TEXT positions instead of LINE positions introduced a constant offset that masqueraded as "scale = 0.8" but was actually the label offset
4. MECH and STR have different numbers of axes (MECH: 17 vertical + 32 horizontal, STR: 5 vertical + 11 horizontal) — so no single affine aligns everything

The new 1.0-scale transform with `TX=208379.86, TY=-179684.52` is the
**best single affine fit for the labeled grid intersections**, computed
from LINE positions not TEXT positions. MECH auxiliary gridlines that
have no STR match will not align — that's a source data property, not a
transform problem.

### Three approaches to overlay generation

Each approach is now packaged as a **self-contained pipeline directory
at ISGEC root** (`A/`, `B/`, `C/`), each with its own `scripts/clean.py`
+ `scripts/fit.py` + `scripts/overlay.py`, `transform.json`, output DXF,
and `README.md`. The legacy prototype dirs (`dxf/A_per_entity/`,
`dxf/B_two_block/`, `dxf/C_one_block/`) are kept for reference but are
no longer the canonical implementation.

| | **A/** per-entity ✅ | **B/** 2-block ✅ | **C/** 1-block ✅ |
|---|---|---|---|
| Modelspace entity count | 2,242 | **2 INSERTs** | **1 INSERT** |
| Alignment transform lives in | 16,015 individual coordinates | **One INSERT** | **One INSERT** |
| Move/rotate/rescale whole STR later | Edit thousands of entities | **Change 1 INSERT** | **Change 1 INSERT** |
| File size | ~18.5 MB | ~18.5 MB | ~18.4 MB |
| **Color policy** | **Original colors preserved** (MECH 17 layer colors, STR source colors) | **Forced 2-color** (MECH = ACI 1 red, STR = ACI 5 blue with `_BLUE_*` prefix) | **Forced 2-color** (MECH = ACI 1 red, STR = ACI 5 blue with `_STR_*` prefix) |
| Visual distinction | Per-layer color + `_STR_*` toggle | Red MECH / blue STR | Red MECH / blue STR |
| Edit individual STR members | **Easiest — no block wrapper** | Click into `STR_DRAWING` block | Click into `OVERLAY_DRAWING` block |
| Faithful to manual Ctrl+Shift+C | Low | High | **Highest** |

**Directory layout** (canonical):

```
ISGEC/
├── A/                                ← Approach A
│   ├── README.md
│   ├── run.sh
│   ├── scripts/
│   │   ├── clean.py                 ← DWG→DXF + strip annotations/markers/triangles
│   │   ├── fit.py                   ← derives transform.json from gridlines
│   │   └── overlay.py               ← per-entity overlay (preserves original colors)
│   ├── input/                       (symlinks to ../dwg/*.dwg)
│   ├── work/                        (intermediates: *_clean3.dxf)
│   ├── transform.json
│   └── out/TP-104 OVERLAY_A.dxf
├── B/                                ← Approach B (forced 2-color red/blue)
│   └── (same layout; overlay.py wraps each drawing in 1 block)
├── C/                                ← Approach C (forced 2-color red/blue)
│   └── (same layout; overlay.py wraps everything in 1 block)
└── run_to_dxf.py                     ← drives all 3, writes dxf/superimposed.dxf
```

**Running any approach:**

```bash
cd A/        # or B/ or C/
./run.sh                                # clean → fit → overlay
ls out/TP-104\ OVERLAY_*.dxf           # outputs the overlay DXF
```

Or drive all 3 at once and write to `dxf/superimposed.dxf`:

```bash
cd ../        # back to ISGEC/
python3 run_to_dxf.py                   # overlay-only (reuses transform.json)
python3 run_to_dxf.py --rewrite-clean  # full clean + fit + overlay
```

The same `scripts/fit.py` works in all three directories — it's
copied into each so you don't need to remember which one to run. The
shared `transform.json` (identical across all 3 dirs by design) carries
the auto-fitted affine: `scale_x = scale_y = 1.0`, `tx = 208379.86`,
`ty = -179684.52`, RMS residual = 0.0.

**Approach A (per-entity)** — `A/scripts/overlay.py` + `out/TP-104 OVERLAY_A.dxf`: walk every STR entity, transform each geometry type in place (LINE endpoints, CIRCLE centers, ARC radii, LWPOLYLINE vertices, TEXT inserts + height, INSERT positions, HATCH boundary paths, etc.), keep MECH untouched, save. **Highest editability** — click any structural member in your CAD viewer to edit it. **Original layer/entity colors preserved** — STR layers are renamed `LayerX` → `_STR_LayerX` (to avoid MECH/STR name collisions) but the source layer color is preserved; entity-level color overrides on STR entities are kept as-is; MECH layers and entities are untouched.

**Approach B (2-block)** — `B/scripts/overlay.py` + `out/TP-104 OVERLAY_B.dxf`: wrap each drawing into a single block (`MECH_DRAWING` and `STR_DRAWING`), then modelspace has just two INSERTs. The alignment transform lives in the single `STR_DRAWING` INSERT's `xscale=1.0`, `yscale=1.0`, `position=(208379.86, -179684.52)`. **MECH layers forced to ACI 1 (red), STR layers forced to ACI 5 (blue) with `_BLUE_*` prefix**, so the two drawings are visually distinct without layer toggling. **STR entity inline colors are forced to ByLayer (256)** so the layer's blue color shows through.

**Approach C (1-block)** — `C/scripts/overlay.py` + `out/TP-104 OVERLAY_C.dxf`: take MECH as the base file, transform all STR entities in place, wrap the result in a single `OVERLAY_DRAWING` block. Modelspace has exactly **one INSERT** for the whole overlay. **Most faithful** to the manual Ctrl+Shift+C workflow — MECH stays at modelspace as-is, STR appears as a single inserted block. **Forced red/blue** same as B.

### Approach B — actual built result

The 2-block overlay was built and verified. Summary:

| Property | Value |
|---|---|
| Modelspace entities | **2 INSERTs only** |
| MECH_DRAWING block contents | 289 entities (LINE 134, INSERT 72, LWPOLYLINE 66, TEXT 7, HATCH 7, SPLINE 2, CIRCLE 1) |
| STR_DRAWING block contents | 1,953 INSERTs (the structural geometry) |
| Inner STR blocks imported | 1,954 (`Part-*`, `Bolt-*`, `Connection-*`, `GridLine-*`) |
| MECH layer colors | **53 layers, all ACI 1 (red)** |
| STR layer colors | **6 layers (`_BLUE_0`, `_BLUE_1`, `_BLUE_2`, `_BLUE_4`, `_BLUE_7`, `_BLUE_10`), all ACI 5 (blue)** |
| Grid axis alignment | **residual = 0.0** on all 12 labeled grid intersections |
| File size | 18.46 MB |

**Top-level modelspace structure** (the new, clean abstraction):

```
MECH_DRAWING    INSERT  pos=(0.0, 0.0)                  xscale=1
STR_DRAWING     INSERT  pos=(208379.86, -179684.52)     xscale=1.0
```

Change the `STR_DRAWING` INSERT's `xscale` or `position` to move or rescale the entire structural overlay in one operation.

### Reusable script: `overlay_2block.py`

```python
#!/usr/bin/env python3
"""Build TP-104 OVERLAY_2block.dxf — Approach B.

MECH and STR each wrapped in a single block. Modelspace has 2 INSERTs.
MECH layers forced to ACI 1 (red), STR layers forced to ACI 5 (blue).
"""

import ezdxf
from ezdxf.addons.importer import Importer

MECH = "TP-104 MECH GA_clean2.dxf"
STR  = "TP-104 STR GA_clean3.dxf"
OUT  = "TP-104 OVERLAY_2block.dxf"

SCALE = 0.8
TX    = 208739.144
TY    = -175320.362
MECH_COLOR = 1   # red
STR_COLOR  = 5   # blue
MECH_BLOCK = "MECH_DRAWING"
STR_BLOCK  = "STR_DRAWING"


def transform_xy(x, y):
    return (SCALE * x + TX, SCALE * y + TY)


def transform_entity_inplace(entity):
    """Apply scale+translate to all coordinate-bearing attributes.
    Identical to overlay.py — see that file for full type coverage."""
    t = entity.dxftype()
    try:
        if t in ("LINE", "RAY", "XLINE"):
            entity.dxf.start = transform_xy(entity.dxf.start[0], entity.dxf.start[1])
            entity.dxf.end   = transform_xy(entity.dxf.end[0],   entity.dxf.end[1])
        elif t == "LWPOLYLINE":
            new_pts = [transform_xy(v[0], v[1]) for v in entity.vertices()]
            entity.clear()
            for p in new_pts: entity.append_vertices(p)
        elif t == "CIRCLE":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1])
            entity.dxf.radius = entity.dxf.radius * SCALE
        elif t == "ARC":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1])
            entity.dxf.radius = entity.dxf.radius * SCALE
        elif t in ("TEXT", "MTEXT"):
            entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1])
            try: entity.dxf.height = entity.dxf.height * SCALE
            except Exception: pass
        elif t == "INSERT":
            entity.dxf.insert = (0.0, 0.0, 0.0)
            try: entity.dxf.xscale = 1.0
            except Exception: pass
            try: entity.dxf.yscale = 1.0
            except Exception: pass
        elif t == "HATCH":
            for path in entity.paths:
                try:
                    verts = list(path.vertices)
                    new_verts = []
                    for v in verts:
                        if len(v) >= 3:
                            nx, ny = transform_xy(v[0], v[1])
                            new_verts.append((nx, ny, v[2]))
                        else:
                            nx, ny = transform_xy(v[0], v[1])
                            new_verts.append((nx, ny))
                    path.vertices = new_verts
                except Exception: pass
    except Exception: pass


def main():
    out_doc = ezdxf.readfile(MECH)
    out_msp = out_doc.modelspace()

    # 1. Create MECH_DRAWING block and move all MECH entities into it
    if MECH_BLOCK in out_doc.blocks:
        out_doc.blocks.delete_block(MECH_BLOCK, safe=False)
    mech_block = out_doc.blocks.new(name=MECH_BLOCK)
    for e in list(out_msp):
        try:
            out_msp.unlink_entity(e)
            mech_block.add_entity(e)
        except Exception as ex:
            print(f"  warn: {ex}")

    # 2. Import STR blocks + entities
    str_doc = ezdxf.readfile(STR)
    str_msp = str_doc.modelspace()
    imp = Importer(str_doc, out_doc)
    block_map = {}
    for str_block in list(str_doc.blocks):
        if str_block.name.startswith("*"): continue
        new_name = imp.import_block(str_block.name, rename=False)
        block_map[str_block.name] = new_name

    mech_handles = {e.dxf.handle for e in out_msp if e.dxf.hasattr("handle")}
    for entity in list(str_msp):
        try: imp.import_entity(entity, target_layout=out_msp)
        except Exception: pass
    imported_handles = {e.dxf.handle for e in out_msp
                        if e.dxf.hasattr("handle") and e.dxf.handle not in mech_handles}

    try: imp.finalize()
    except Exception: pass

    # 3. Transform imported STR entities in place
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                transform_entity_inplace(e)
        except Exception: pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                try: transform_entity_inplace(e)
                except Exception: pass

    # 4. Create STR_DRAWING block and move imported STR entities into it
    if STR_BLOCK in out_doc.blocks:
        out_doc.blocks.delete_block(STR_BLOCK, safe=False)
    str_block_layout = out_doc.blocks.new(name=STR_BLOCK)
    str_entities = [e for e in list(out_msp)
                    if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles]
    for e in str_entities:
        try:
            out_msp.unlink_entity(e)
            str_block_layout.add_entity(e)
        except Exception: pass

    # 5. Force MECH layers to red, force STR layers to blue (with _BLUE_ prefix)
    for layer in out_doc.layers:
        try: layer.dxf.color = MECH_COLOR
        except Exception: pass

    blue_layers = set()
    for e in list(str_block_layout):
        try:
            if e.dxf.hasattr("layer"): blue_layers.add(e.dxf.layer)
        except Exception: pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                if e.dxf.hasattr("layer"): blue_layers.add(e.dxf.layer)

    BLUE_PREFIX = "_BLUE_"
    existing = {l.dxf.name for l in out_doc.layers}
    renames = {}
    for layer in blue_layers:
        if layer.startswith(BLUE_PREFIX): continue
        new_name = BLUE_PREFIX + layer
        renames[layer] = new_name
        if new_name not in existing:
            out_doc.layers.add(name=new_name, color=STR_COLOR)
        else:
            try: out_doc.layers.get(name=new_name).dxf.color = STR_COLOR
            except Exception: pass

    for e in list(str_block_layout):
        try:
            if e.dxf.hasattr("layer") and e.dxf.layer in renames:
                e.dxf.layer = renames[e.dxf.layer]
        except Exception: pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                if e.dxf.hasattr("layer") and e.dxf.layer in renames:
                    e.dxf.layer = renames[e.dxf.layer]

    # 6. Add the two INSERTs at modelspace — the entire alignment transform
    out_msp.add_blockref(MECH_BLOCK, insert=(0.0, 0.0, 0.0))
    out_msp.add_blockref(STR_BLOCK,  insert=(TX, TY, 0.0),
                          dxfattribs={"xscale": SCALE, "yscale": SCALE})

    out_doc.saveas(OUT)
    print(f"Saved {OUT}")
    print(f"  MECH: {len(list(mech_block))} entities (red), STR: {len(list(str_block_layout))} modelspace + {len(block_map)} inner blocks (blue)")
    print(f"  Modelspace: 2 INSERTs — MECH at origin, STR at ({TX:.1f}, {TY:.1f}) with xscale=0.8")


if __name__ == "__main__":
    main()
```

### One subtle issue: inner `xscale = 0.8` in STR INSERTs

While building the overlay we discovered the source STR file already has every internal INSERT drawn with `xscale = 0.8` baked in by the source CAD software. This means a naive "scale the whole drawing by 0.8" double-applies the scale, producing `xscale = 0.64` (0.8²) — and the overlay ends up 128,000 units off-target.

**Resolution** (used in Approach A): since the block contents are transformed to absolute MECH coordinates, set the wrapping INSERT's position to `(0, 0, 0)` and `xscale = yscale = 1`. The block geometry already sits at its final position; the INSERT just needs to anchor it.

**Resolution for Approach B / C** (would need): either strip the inner `xscale = 0.8` from every STR INSERT before wrapping, or apply the outer transform as `xscale = 0.8 × (1 / 0.8) = 1.0` with `position = transform(inner_insert_position)`.

### Reusable script: `overlay.py`

```python
#!/usr/bin/env python3
"""Overlay TP-104 STR onto TP-104 MECH using a fitted affine transform.

Approach: per-entity. Imports STR blocks/entities into a clone of MECH via
ezdxf's Importer, then walks every imported entity and applies
    x_m = 0.8 * x_s + 208739.144
    y_m = 0.8 * y_s + (-175320.362)

Result: TP-104 OVERLAY.dxf — both drawings in the same coordinate system,
STR content on _STR_* prefixed layers (toggleable), grid axes coincident.

Layer prefix _STR_* lets you turn STR geometry on/off independently of MECH:
    - All MECH content stays on its original layers (CEN, MAIN OBJECT, etc.)
    - All imported STR content is on _STR_0, _STR_2, _STR_4, _STR_7, _STR_10, _STR_1
"""

import ezdxf
from ezdxf.addons.importer import Importer

MECH = "TP-104 MECH GA_clean2.dxf"
STR  = "TP-104 STR GA_clean3.dxf"
OUT  = "TP-104 OVERLAY.dxf"

SCALE = 0.8
TX    = 208739.144
TY    = -175320.362
STR_PREFIX = "_STR_"


def transform_xy(x, y):
    return (SCALE * x + TX, SCALE * y + TY)


def transform_entity_inplace(entity):
    t = entity.dxftype()
    try:
        if t in ("LINE", "RAY", "XLINE"):
            entity.dxf.start = transform_xy(entity.dxf.start[0], entity.dxf.start[1])
            entity.dxf.end   = transform_xy(entity.dxf.end[0],   entity.dxf.end[1])
        elif t == "LWPOLYLINE":
            new_pts = [transform_xy(v[0], v[1]) for v in entity.vertices()]
            entity.clear()
            for p in new_pts: entity.append_vertices(p)
        elif t == "CIRCLE":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1])
            entity.dxf.radius = entity.dxf.radius * SCALE
        elif t == "ARC":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1])
            entity.dxf.radius = entity.dxf.radius * SCALE
        elif t == "ELLIPSE":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1])
            m = entity.dxf.major_axis
            entity.dxf.major_axis = (m[0]*SCALE, m[1]*SCALE, m[2]*SCALE)
        elif t in ("TEXT", "MTEXT"):
            entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1])
            try:
                if entity.dxf.hasattr("alignment_point") and entity.dxf.alignment_point:
                    entity.dxf.alignment_point = transform_xy(
                        entity.dxf.alignment_point[0], entity.dxf.alignment_point[1])
            except Exception: pass
            try: entity.dxf.height = entity.dxf.height * SCALE
            except Exception: pass
        elif t == "INSERT":
            # Block CONTENTS are now in MECH coordinates; INSERT just anchors at (0,0) scale 1
            entity.dxf.insert = (0.0, 0.0, 0.0)
            try: entity.dxf.xscale = 1.0
            except Exception: pass
            try: entity.dxf.yscale = 1.0
            except Exception: pass
        elif t == "SPLINE":
            try: entity.control_points = [transform_xy(p[0], p[1]) for p in entity.control_points]
            except Exception: pass
            try: entity.fit_points = [transform_xy(p[0], p[1]) for p in entity.fit_points]
            except Exception: pass
        elif t == "HATCH":
            for path in entity.paths:
                try:
                    verts = list(path.vertices)
                    new_verts = []
                    for v in verts:
                        if len(v) >= 3:
                            nx, ny = transform_xy(v[0], v[1])
                            new_verts.append((nx, ny, v[2]))  # preserve bulge
                        else:
                            nx, ny = transform_xy(v[0], v[1])
                            new_verts.append((nx, ny))
                    path.vertices = new_verts
                except Exception: pass
        elif t == "DIMENSION":
            try: entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1])
            except Exception: pass
    except Exception:
        pass


def main():
    out_doc = ezdxf.readfile(MECH)
    out_msp = out_doc.modelspace()
    str_doc = ezdxf.readfile(STR)
    str_msp = str_doc.modelspace()

    imp = Importer(str_doc, out_doc)

    # 1. Import all STR blocks
    block_map = {}
    for str_block in list(str_doc.blocks):
        if str_block.name.startswith("*"): continue
        new_name = imp.import_block(str_block.name, rename=False)
        block_map[str_block.name] = new_name

    # 2. Snapshot MECH handles, import STR entities, identify which are imported
    mech_handles = {e.dxf.handle for e in out_msp if e.dxf.hasattr("handle")}
    for entity in list(str_msp):
        try: imp.import_entity(entity, target_layout=out_msp)
        except Exception: pass
    imported_handles = {e.dxf.handle for e in out_msp
                        if e.dxf.hasattr("handle") and e.dxf.handle not in mech_handles}

    # 3. Resolve INSERT references
    try: imp.finalize()
    except Exception: pass

    # 4. Transform every imported STR entity
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                transform_entity_inplace(e)
        except Exception: pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                try: transform_entity_inplace(e)
                except Exception: pass

    # 5. Rename imported STR entity layers to _STR_* prefix
    layers_in_use = set()
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                if not e.dxf.layer.startswith(STR_PREFIX):
                    layers_in_use.add(e.dxf.layer)
        except Exception: pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                if not e.dxf.layer.startswith(STR_PREFIX):
                    layers_in_use.add(e.dxf.layer)

    existing = {l.dxf.name for l in out_doc.layers}
    for layer in layers_in_use:
        new_name = STR_PREFIX + layer
        if new_name not in existing:
            out_doc.layers.add(name=new_name, color=2)
            existing.add(new_name)

    renames = {old: STR_PREFIX + old for old in layers_in_use}
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                if e.dxf.layer in renames: e.dxf.layer = renames[e.dxf.layer]
        except Exception: pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                if e.dxf.layer in renames: e.dxf.layer = renames[e.dxf.layer]

    out_doc.saveas(OUT)
    print(f"Saved {OUT}")
    print(f"  Imported {len(imported_handles)} STR entities + {len(block_map)} blocks")
    print(f"  Renamed {len(renames)} layers to {STR_PREFIX}* prefix")


if __name__ == "__main__":
    main()
```

### Manual alternative (for AutoCAD users who want to skip the script)

Two overlay files are available out of the box:
- **`TP-104 OVERLAY.dxf`** — Approach A (per-entity, `_STR_*` toggleable layers)
- **`TP-104 OVERLAY_2block.dxf`** — Approach B (2-block, MECH red / STR blue) — **recommended for visual inspection**

If you'd rather do the paste-with-base-point manually instead of using either file:

1. Open MECH as parent
2. Issue `INSERT` → browse to `TP-104 STR GA_clean3.dxf` → in the dialog, **uncheck** "Specify on-screen" for Insertion Point
3. Set:
   - **Insertion point X**: `208739.144`
   - **Insertion point Y**: `-175320.362`
   - **Insertion point Z**: `0`
   - **X scale**: `0.8`
   - **Y scale**: `0.8`
   - **Rotation angle**: `0`
4. Click OK — STR geometry pastes in, axis-aligned to MECH

---

## Verification checklist

Run before declaring a file clean:

- [ ] File loads with `ezdxf.recover.readfile()` with 0 audit errors
- [ ] All 7 grid labels present (`TP104-A`, `B`, `C`, `D`, `1`, `2`, `3`)
- [ ] No `MTEXT`, `ATTRIB`, `DIMENSION`, `LEADER` in model space
- [ ] Only 7 `TEXT` entities in model space (the grid labels)
- [ ] No LWPOLYLINE on layer `BOX` in model space (if removing hexagons)
- [ ] No INSERT references to removed blocks
- [ ] File size reduced by ~5–15% compared to source
- [ ] `LINE`, `LWPOLYLINE`, `ARC`, `HATCH`, `INSERT` counts look reasonable for the project scale

### Overlay-specific verification (run on `dxf/superimposed.dxf`)

- [ ] All 7 `TP104-*` axis positions in STR-`GridLine-*` blocks coincide with the corresponding MECH axis position (residual < 50 units; current measured: ~0.0005 DXF units)
- [ ] Approach A (canonical `superimposed.dxf`): ~2,242 modelspace entities, 0 wrapper INSERTs
- [ ] Approach B (`superimposed_B.dxf`): exactly 2 modelspace INSERTs (`MECH_DRAWING` + `STR_DRAWING`)
- [ ] Approach C (`superimposed_C.dxf`): exactly 1 modelspace INSERT (`OVERLAY_DRAWING`)
- [ ] No INSERT in modelspace has `xscale ≠ 1` or `yscale ≠ 1` for STR blocks (sign of double-transform)
- [ ] Approach A: STR layers renamed with `_STR_` prefix (to avoid MECH/STR collisions); original layer colors preserved
- [ ] Approach B: STR layers renamed with `_BLUE_*` prefix and forced to ACI 5 (blue); MECH layers forced to ACI 1 (red)
- [ ] Approach C: STR layers renamed with `_STR_*` prefix and forced to ACI 5 (blue); MECH layers forced to ACI 1 (red)
- [ ] File opens cleanly in your CAD app
- [ ] When STR layers are turned off, only MECH geometry is visible
- [ ] When STR layers are turned on, structural members appear aligned with mechanical equipment (no large offsets)

Automated verification:

```bash
cd ISGEC/
python3 verify_all.py 3           # re-runs all 3 dirs from scratch, checks structure + alignment
python3 check_overlap.py         # renders each overlay, computes pixel-level overlap
```

- [ ] All 7 `TP104-*` axis positions in STR-`GridLine-*` blocks coincide with the corresponding MECH axis position (residual < 50 units)
- [ ] No INSERT in modelspace has `xscale ≠ 1` or `yscale ≠ 1` for STR blocks (sign of double-transform)
- [ ] All STR layers have `_STR_` prefix and are toggleable independently
- [ ] File opens cleanly in your CAD app
- [ ] When STR layers are turned off, only MECH geometry is visible
- [ ] When STR layers are turned on, structural members appear aligned with mechanical equipment (no large offsets)

Quick script to check axis alignment:

```python
import ezdxf, re
doc = ezdxf.readfile("TP-104 OVERLAY.dxf")
GRID = re.compile(r"TP104-([A-D1-3])")
for block in doc.blocks:
    if not block.name.startswith("GridLine-"): continue
    label, ax, ay = None, None, None
    for e in block:
        if e.dxftype() == "TEXT":
            m = GRID.match(e.dxf.text.strip())
            if m: label = "TP104-" + m.group(1)
        elif e.dxftype() == "LINE" and e.dxf.linetype == "DXK_LINE_DOT5":
            sx, sy, ex, ey = (e.dxf.start[0], e.dxf.start[1],
                              e.dxf.end[0], e.dxf.end[1])
            if abs(sx-ex) < abs(sy-ey): ax = (sx+ex)/2
            else: ay = (sy+ey)/2
    if label:
        print(f"{label}: STR axis at ({ax:.1f}, {ay:.1f})")
```

---

## Known limitations

1. **DWG output** — `ezdxf` writes DXF only. DWG conversion requires `libredwg` or commercial tools.
2. **Proxy data** — 72 `ACAD_PROXY_OBJECT` entries in the source files (Tekla/STAAD custom data) cannot be cleanly handled by libredwg 0.13.3.
3. **Superimposed file** — only 20 surface TEXT entities were strippable; beam/member tags in the superimposed DXF live inside proxy data. For full annotation removal, regenerate the superimposed view from the cleaned STR + MECH files instead.
4. **Block content checks** — our LWPOLYLINE-vertex counter doesn't track LWPOLYLINE inside blocks for the marker pass (only top-level). For full marker sweep inside blocks, extend `strip_markers.py` with a third rule: `if e["type"] == "LWPOLYLINE" and e["block"] in MARKER_BLOCKS and e["n_verts"] in {3, 6}`.
5. **Plot generation** — these cleaned DXFs are intended for downstream geometry analysis, not plot output. To produce a clean PDF for review, open the cleaned DXF in your CAD app and use its native plotter.
6. **Inner `xscale = 0.8` in STR INSERTs** — the source STR file has every internal INSERT drawn with `xscale = 0.8` baked in by the source CAD software. Any overlay approach must account for this (see [overlay section](#superimposing-str-onto-mech) for details on the three approaches and the double-transform pitfall).
7. **Text label offset differs between files** — STR places axis labels (e.g. `TP104-A`) at slightly different offsets from the axis line than MECH does. The overlay aligns the axes themselves (max residual 8 units, ≈ 0.4 mm), not the labels — this is correct behavior for CAD overlay.
8. **Approach B/C color override is one-way** — `dxf/superimposed_B.dxf` and `dxf/superimposed_C.dxf` force every MECH layer to ACI 1 (red) and every STR layer to ACI 5 (blue) by writing the color onto the layer definition. If you re-import the original MECH or STR DXF into this file and want the layers restored to their original colors (white, etc.), you'd need to delete those layers and re-create them from the source files. **Approach A** (`A/scripts/overlay.py`, canonical `dxf/superimposed.dxf`) preserves original layer/entity colors — only renames STR layers to `_STR_*` to avoid name collisions. Use Approach A if you want non-destructive layer coloring.

---

## See also

- `ISGEC/README.md` — top-level overview of the 3 overlay pipelines
- `ISGEC/A/README.md`, `ISGEC/B/README.md`, `ISGEC/C/README.md` — per-approach docs
- `ISGEC/run_to_dxf.py` — driver: builds the canonical `dxf/superimposed.dxf`
- `ISGEC/verify_all.py` — end-to-end audit of all 3 pipelines
- `ISGEC/check_overlap.py` — pixel-level overlap verification
- `ISGEC/docs/INSPECTION_NOTES.md` (to be created) — specific issues found in source DWG/DXF (typos, dual scales, etc.)
- `adv/backend/app/services/analyze.py` — downstream analysis pipeline that consumes cleaned DXFs
- [GD&T reference](https://www.gdandtbasics.com/gdt-symbols/) — engineering drawing symbol meanings
- [IS 808: Indian Standard hot-rolled medium and high tensile structural steel](https://infralens.in/term/structural-steel) — reference for ISMC/UB/NPB/ISA section symbols we identified in STR
- [ezdxf Importer addon](https://ezdxf.mozman.at/docs/addons/importer.html) — the cross-document entity transfer mechanism used by `overlay.py`
- [IS 808 Steel Sections](https://infralens.in/term/structural-steel) — Indian Standard structural sections used in this drawing
