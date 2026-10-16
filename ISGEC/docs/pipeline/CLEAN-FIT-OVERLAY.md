# The 3-Stage Pipeline — clean → fit → overlay

> **Source:** `ISGEC/A/scripts/`, `ISGEC/B/scripts/`, `ISGEC/C/scripts/`
> **Spec:** `ISGEC/docs/SCRIPTS.md` (in-repo)

Every strategy (`A`, `B`, `C`) runs the same first two stages. Only Stage 3 differs. This document walks through each stage in detail — what each script does, what it produces, and what edge cases it handles.

---

## Stage 1 — Cleaning (`scripts/clean.py`, identical in A/B/C)

**Inputs**:
- Symlink at `input/TP-104 MECH GA.dwg` (resolves to `../../dwg/`)
- Symlink at `input/TP-104 STR GA.dwg` (resolves to `../../dwg/`)

**Behavior**:

1. **DWG → DXF conversion**:
   - Tries `ezdxf.addons.odafc` (ODA File Converter on PATH)
   - If unavailable, falls back to existing cleaned DXFs in this priority:
     - `../../dxf/*_clean3.dxf` (preferred — full strip already applied)
     - `../../dxf/*.dxf` (raw, uncleaned)
   - Re-raises if nothing found

2. **Strips annotations** from the resulting DXF:
   - `DIMENSION`, `MTEXT`, `LEADER`, `MULTILEADER`, `TOLERANCE`
   - `ATTRIB`, `ATTDEF` (block attribute values + templates)
   - `DIMASSOC` (dimension associativity)
   - All `TEXT` entities **except** the 7 grid labels `TP104-A/B/C/D/1/2/3`

3. **Strips marker hexagons**: 6-vertex closed `LWPOLYLINE` on layer `BOX` (MECH only — these are visual markers added by the drafter, not geometry)

4. **Strips orphan marker blocks**: anonymous `A$C*` blocks not referenced by kept geometry. The KEEP/ORPHAN set is computed dynamically by following INSERT references.

5. **Strips orphan `A$C2135de20`** (ACM_FILLED_HALF symbol with 6 SOLID triangles — leftover symbol-library geometry, MECH only)

**Outputs**:
- `work/TP-104 MECH GA.dxf` — DXF conversion output
- `work/TP-104 STR GA.dxf`
- `work/TP-104 MECH GA_clean.dxf` — after annotation strip
- `work/TP-104 STR GA_clean.dxf`
- `work/TP-104 MECH GA_clean3.dxf` ← final, used by fit.py + overlay.py
- `work/TP-104 STR GA_clean3.dxf`

**Run**:
```bash
python3 scripts/clean.py
```

---

## Stage 2 — Fitting (`scripts/fit.py`, identical in A/B/C)

**Inputs**:
- `work/TP-104 MECH GA_clean3.dxf` (must have all 7 grid labels)
- `work/TP-104 STR GA_clean3.dxf`

**Behavior**:

1. **Walks MECH** for `TEXT` entities whose stripped text matches `^TP104-[A-D1-3]$` — finds 7 axis labels.

2. **For each MECH label**, walks nearby `CEN` / `HIDDEN` / `CENTERLINE` centerline LINE entities to determine the actual world-axis position. The naive approach (using the TEXT-label position) is wrong by ~600 DXF units — labels are positioned near their gridline, not on it.

   ```python
   # Centerline layers in MECH (per AUTO CAD Mechanical conventions)
   GRID_LAYERS_MECH = {"CEN", "CENETR LINE", "CENTER", "PHANTOM",
                       "PANTHOM", "HIDDEN", "HIDDDEN"}
   ```

3. **Walks STR `GridLine-*` blocks**: inside each block, finds the **longest axis-aligned LINE** (the real gridline, not the bracket markers around the label).

   ```python
   # Match blocks named "GridLine-*" or " Line-*" (DXF round-trip variants)
   if not (nm.startswith("GridLine-") or nm.startswith(" Line-")):
       continue
   ```

4. **Solves least-squares affine** for `(scale_x, scale_y, tx, ty)` minimizing squared residuals across all 12 grid intersections (4 vertical × 3 horizontal).

5. **Writes `transform.json`** with scale, translation, all 12 intersections with per-intersection residual.

**Output** for TP-104 (actual):
```json
{
  "scale_x": 0.9999999999078191,
  "scale_y": 1.0000000000951985,
  "tx":       208379.86046213657,
  "ty":      -179584.52411355262,
  "x_labels": [{"label": "A", "str": 20131.99, "mech": 228511.86}, ...],
  "y_labels": [{"label": "1", "str": 24320.84, "mech": -155263.69}, ...],
  "intersections": [
    {"label": "A-1", "str": [...], "mech": [...], "predicted_mech": [...], "residual": 1.39e-7},
    ...
  ],
  "rms_residual":  2.336e-7,
  "max_residual":  3.376e-7
}
```

> ⚠️ **The "0.8 scale" bug**: an earlier version of this script worked from text-label positions and produced `scale = 0.8`. This conflated the ~600-unit text-label offset between MECH and STR with a scale. The current implementation works from actual gridline LINE positions and yields scale = 1.0.

**Run**:
```bash
python3 scripts/fit.py
cat transform.json    # see scale_x, scale_y, tx, ty, residuals
```

---

## Stage 3 — Overlay (`scripts/overlay.py`, **differs per strategy**)

This is the only stage that changes between A, B, and C. Each reads the same `work/*_clean3.dxf` + `transform.json` but produces a structurally different DXF.

### A — Per-entity (`A/scripts/overlay.py`)

Imports every STR entity into the MECH document and applies the affine in place. STR geometry is loose in modelspace alongside MECH — **no block wrapper**.

**Structure**:
- Modelspace: **2,242 entities** (1,953 STR INSERTs + 1,953 STR top-level entities + 289 MECH entities; exact counts vary)
- Wrappers: **0**
- Editability: **HIGHEST**

**Key steps**:

1. **Import all STR blocks** via `ezdxf.addons.importer.Importer`:
   ```python
   imp = Importer(str_doc, out_doc)
   for str_block in list(str_doc.blocks):
       if str_block.name.startswith("*"): continue
       target = STR_PREFIX + str_block.name   # _STR_GridLine-A, etc.
       ...
       block_map[str_block.name] = new_name
   ```

2. **Import STR top-level entities** via `imp.import_entity(entity, target_layout=out_msp)`.

3. **Pre-scale each block's contents** to bake `INSERT.pos + xscale` into local coords:
   ```python
   sx = e.dxf.xscale or 1.0
   ip_x, ip_y = e.dxf.insert[0], e.dxf.insert[1]
   for be in list(block):
       prescale_entity(be, sx, sy, ip_x, ip_y)
   e.dxf.insert = (0.0, 0.0, 0.0)
   e.dxf.xscale = 1.0
   ```

4. **Transform everything** in-place — handles LINE, LWPOLYLINE, CIRCLE, ARC, ELLIPSE, POINT, TEXT/MTEXT, SPLINE, HATCH, DIMENSION, SOLID/TRACE/3DFACE:
   ```python
   def transform_entity_inplace(entity, ax, ay, bx, by):
       t = entity.dxftype()
       if t in ("LINE", "RAY", "XLINE"):
           entity.dxf.start = transform_xy(entity.dxf.start[0], entity.dxf.start[1], ax, ay, bx, by)
           entity.dxf.end   = transform_xy(entity.dxf.end[0],   entity.dxf.end[1],   ax, ay, bx, by)
       elif t == "LWPOLYLINE":
           new_pts = [transform_xy(v[0], v[1], ax, ay, bx, by) for v in entity.vertices()]
           entity.clear()
           for p in new_pts:
               entity.append_vertices(p)
       # ... and so on for each entity type
   ```

5. **Rename STR layers** to `_STR_LayerX` (preserves source colors):
   ```python
   # Look up each layer's source color from str_doc.layers
   src_layer = str_doc.layers.get(name=layer)
   layer_color = src_layer.dxf.color if src_layer else 7
   out_doc.layers.add(name=new_name, color=layer_color)
   ```

6. **Save** as `out/TP-104 OVERLAY_A.dxf` (~18 MB).

**Outputs**:
- File: `out/TP-104 OVERLAY_A.dxf` (~18 MB)
- Modelspace: 2,242 entities
- Layer colors: MECH original + STR original (preserved)

### B — 2-block (`B/scripts/overlay.py`)

Wraps each drawing in its own block. Modelspace has **2 INSERTs**.

**Structure**:
- Modelspace: **2 INSERTs**
  - `MECH_DRAWING` at `(0, 0)` (no transform)
  - `STR_DRAWING` at `(tx, ty)` with embedded `(xscale=1.0, yscale=1.0)`
- Wrappers: 2 (`MECH_DRAWING`, `STR_DRAWING`)
- Editability: MEDIUM

**Key steps**:

1. **Wrap MECH into `MECH_DRAWING` block**:
   ```python
   mech_block = out_doc.blocks.new(name="MECH_DRAWING")
   for e in list(out_msp):
       out_msp.unlink_entity(e)
       mech_block.add_entity(e)
   ```

2. **Import STR at original coords**, then **wrap into `STR_DRAWING` block**:
   ```python
   str_block_layout = out_doc.blocks.new(name="STR_DRAWING")
   for e in str_entities:
       out_msp.unlink_entity(e)
       str_block_layout.add_entity(e)
   ```

3. **Recolor MECH layers → red**, STR layers → blue with `_BLUE_` prefix:
   ```python
   for layer in out_doc.layers:
       layer.dxf.color = MECH_COLOR  # 1 = red
   ```
   ```python
   for layer in blue_layers:
       new_name = BLUE_PREFIX + layer  # _BLUE_P11, _BLUE_GRID-A, ...
       out_doc.layers.add(name=new_name, color=STR_COLOR)  # 5 = blue
   ```

4. **Add 2 INSERTs at modelspace**:
   ```python
   out_msp.add_blockref("MECH_DRAWING", insert=(0.0, 0.0, 0.0))
   out_msp.add_blockref("STR_DRAWING", insert=(tx, ty, 0.0),
                        dxfattribs={"xscale": sx, "yscale": sy})
   ```

5. **Save** as `out/TP-104 OVERLAY_B.dxf` (~18 MB).

### C — 1-block (`C/scripts/overlay.py`)

Same per-entity transform as A, wrapped in one `OVERLAY_DRAWING` block. Modelspace has **1 INSERT**.

**Structure**:
- Modelspace: **1 INSERT** at origin
- Wrappers: 1 (`OVERLAY_DRAWING`)
- Editability: LOW (single grab)

**Key difference from A**:

Reuses the `prescale_entity` and `transform_entity_inplace` helpers from `overlay_helper.py` (sibling script in the same dir), then **wraps everything** (MECH + STR) into one block at the end:

```python
overlay_block = out_doc.blocks.new(name="OVERLAY_DRAWING")
for e in list(out_msp):
    out_msp.unlink_entity(e)
    overlay_block.add_entity(e)

out_msp.add_blockref("OVERLAY_DRAWING", insert=(0.0, 0.0, 0.0))
```

**Output**:
- File: `out/TP-104 OVERLAY_C.dxf` (~18 MB)
- Modelspace: 1 INSERT at origin
- Layer colors: MECH red + STR blue (forced)

---

## The driver — `run_to_dxf.py`

Lives in `ISGEC/` root. Drives A/B/C and writes to `dxf/superimposed*.dxf`.

**Behavior**:

1. Symlinks `dxf/TP-104 *_clean3.dxf` into each approach's `work/`.
2. Runs only `scripts/overlay.py` for each approach (skips `clean.py` + `fit.py` because `transform.json` is already there).
3. Copies each result to `dxf/superimposed_{X}.dxf`.
4. Copies approach-A's output to `dxf/superimposed.dxf` (canonical).

**Modes**:

```bash
python3 run_to_dxf.py                  # overlay-only (fast)
python3 run_to_dxf.py --rewrite-clean # full clean + fit + overlay each
```

**Outputs**:

- `dxf/superimposed.dxf` — canonical (approach A; original colors preserved)
- `dxf/superimposed_A.dxf` — per-entity, original colors
- `dxf/superimposed_B.dxf` — 2-block, forced red/blue
- `dxf/superimposed_C.dxf` — 1-block, forced red/blue

---

## Self-locating paths

Every script in this pipeline uses `Path(__file__).resolve().parent` to find siblings. **No hardcoded paths** — works from any clone of `ISGEC/`:

```python
HERE = Path(__file__).resolve().parent
APPROACH_DIR = HERE.parent
WORK = APPROACH_DIR / "work"
INPUT = APPROACH_DIR / "input"
```

This is why each approach (`A/`, `B/`, `C/`) is fully self-contained — the same `clean.py` + `fit.py` work in any of them, and `overlay.py` finds its siblings via `Path(__file__).resolve().parent`.

---

## Reference

- **[OVERVIEW.md](./OVERVIEW.md)** — the bigger picture
- **[STRATEGY-A.md](./STRATEGY-A.md)**, **[STRATEGY-B.md](./STRATEGY-B.md)**, **[STRATEGY-C.md](./STRATEGY-C.md)** — per-strategy details
- **[VERIFICATION.md](./VERIFICATION.md)** — verifying the output
- `ISGEC/A/scripts/clean.py`, `ISGEC/A/scripts/fit.py`, `ISGEC/A/scripts/overlay.py` — the actual scripts (well-commented)