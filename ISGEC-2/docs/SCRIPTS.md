# Scripts Reference — ISGEC `A/`, `B/`, `C/` pipelines

This file documents the 3 scripts that are duplicated across `A/`,
`B/`, `C/` (one full pipeline per directory). Each dir is independent
and runnable on its own; the only shared resource is the
`transform.json` produced by `scripts/fit.py` (copied identically into
each dir).

---

## `scripts/clean.py` — Step 1: DWG→DXF + strip junk

**Inputs**
- Symlink at `input/TP-104 MECH GA.dwg` (resolves to `../../dwg/`)
- Symlink at `input/TP-104 STR GA.dwg` (resolves to `../../dwg/`)

**Behavior**
1. Tries to convert DWG → DXF via `ezdxf.addons.odafc` (ODA File
   Converter on PATH). If unavailable, falls back to existing cleaned
   DXFs in this priority order:
   - `../../dxf/*_clean3.dxf` (preferred — full strip already applied)
   - `../../dxf/*.dxf` (raw, uncleaned)
   - Re-raises if nothing found.
2. Strips annotations from the resulting DXF:
   - `DIMENSION`, `MTEXT`, `LEADER`, `MULTILEADER`, `TOLERANCE`
   - `ATTRIB`, `ATTDEF` (block attribute values + templates)
   - `DIMASSOC` (dimension associativity)
   - All `TEXT` entities **except** the 7 grid labels `TP104-A/B/C/D/1/2/3`
3. Strips marker hexagons: 6-vertex closed `LWPOLYLINE` on layer `BOX`.
4. Strips orphan marker blocks (anonymous `A$C*` not referenced by kept
   geometry).
5. Strips orphan `A$C2135de20` (ACM_FILLED_HALF symbol with 6 SOLID
   triangles — leftover symbol-library geometry).

**Outputs**
- `work/TP-104 MECH GA.dxf`
- `work/TP-104 STR GA.dxf`
- `work/TP-104 MECH GA_clean.dxf`
- `work/TP-104 STR GA_clean.dxf`
- `work/TP-104 MECH GA_clean3.dxf`  ← final, used by fit.py + overlay.py
- `work/TP-104 STR GA_clean3.dxf`   ← final

**Run**
```bash
python3 scripts/clean.py
```

---

## `scripts/fit.py` — Step 2: derive affine from gridlines

**Inputs**
- `work/TP-104 MECH GA_clean3.dxf` (must have all 7 grid labels)
- `work/TP-104 STR GA_clean3.dxf` (must have all 7 grid labels)

**Behavior**
1. Walks MECH for `TEXT` entities whose stripped text matches
   `^TP104-[A-D1-3]$` — finds 7 axis labels.
2. For each MECH label, walks nearby `CEN`/`HIDDEN`/`CENTERLINE`
   centerline LINE entities to determine the actual world-axis position
   (avoids the ~600 unit TEXT-label offset between MECH and STR).
3. Walks STR `GridLine-*` blocks; inside each block, finds the longest
   axis-aligned LINE (the real gridline, not the bracket markers around
   the label).
4. Solves `scipy.optimize.least_squares` for the affine
   `(scale_x, scale_y, tx, ty)` minimizing squared residuals across
   all 12 grid intersections.

**Result for TP-104**:
```json
{
  "scale_x": 1.000000000,
  "scale_y": 1.000000000,
  "tx": 208379.8605,
  "ty": -179584.5241,
  "max_residual": 0.000423,
  "rms_residual": 0.000187
}
```

> The "0.8 scale" earlier fit was wrong — it conflated the TEXT-label
> offset between MECH and STR with a scale. Working from actual gridline
> LINE positions yields scale = 1.0 in both axes.

**Output**: `transform.json` (in the approach dir's root, same level as `scripts/`)

**Run**
```bash
python3 scripts/fit.py
cat transform.json   # see scale_x, scale_y, tx, ty, residuals
```

---

## `scripts/overlay.py` — Step 3: build the overlay DXF

This is the only script that **differs across approaches**. Each one
reads the same `work/*_clean3.dxf` + `transform.json` but produces a
structurally different DXF.

### `A/scripts/overlay.py` — Per-entity

Imports every STR entity into the MECH document and applies the affine
in place. STR layers renamed `_STR_LayerX` (preserves original colors).
MECH untouched.

**Outputs**
- `out/TP-104 OVERLAY_A.dxf` (~18.5 MB)
- Modelspace: **2,242 entities** (1,953 STR INSERTs + 1,953 STR top-level
  entities + 289 MECH entities; exact counts vary)
- Wrappers: **0**
- Editability: **HIGHEST**

**Color policy**
- MECH layers + entities: original colors (17 unique layer colors preserved)
- STR layers: created with `str_doc.layers[name].dxf.color` (preserved)
- STR entity color overrides: kept as-is from source

### `B/scripts/overlay.py` — 2-block

Wraps each drawing in a single block. Modelspace = 2 INSERTs.

**Outputs**
- `out/TP-104 OVERLAY_B.dxf` (~18.5 MB)
- Modelspace: **2 INSERTs**
  - `MECH_DRAWING` at `(0, 0)` (no transform)
  - `STR_DRAWING` at `(208379.86, -179584.52)` with embedded
    `(xscale=1.0, yscale=1.0)`
- Wrappers: **2** (`MECH_DRAWING`, `STR_DRAWING`)
- Editability: **MEDIUM**

**Color policy**
- MECH layers: forced to ACI 1 (red)
- STR layers: forced to ACI 5 (blue) with `_BLUE_` prefix
- STR entity color overrides: reset to ByLayer (256)

### `C/scripts/overlay.py` — 1-block

Same per-entity transform as A, wrapped in one `OVERLAY_DRAWING` block.
Modelspace = 1 INSERT.

**Outputs**
- `out/TP-104 OVERLAY_C.dxf` (~18.4 MB)
- Modelspace: **1 INSERT** at origin
- Wrappers: **1** (`OVERLAY_DRAWING`)
- Editability: **LOW**

**Color policy** (same as B)
- MECH layers: forced to ACI 1 (red)
- STR layers: forced to ACI 5 (blue) with `_STR_` prefix
- STR entity color overrides: reset to ByLayer (256)

---

## `../run_to_dxf.py` — multi-approach driver

Lives in `ISGEC/` root (not in `A/`, `B/`, `C/`).

**Behavior**
1. Symlinks `dxf/TP-104 *_clean3.dxf` into each approach's `work/`.
2. Runs only `scripts/overlay.py` for each approach (skips
   `clean.py` + `fit.py` because `transform.json` is already there).
3. Copies each result to `dxf/superimposed_{X}.dxf`.
4. Copies approach-A's output to `dxf/superimposed.dxf` (canonical).

**Modes**
```bash
python3 run_to_dxf.py                  # overlay-only (fast)
python3 run_to_dxf.py --rewrite-clean # clean + fit + overlay each
```

**Outputs**
- `dxf/superimposed.dxf` — canonical (approach A; original colors preserved)
- `dxf/superimposed_A.dxf` — per-entity, original colors
- `dxf/superimposed_B.dxf` — 2-block, forced red/blue
- `dxf/superimposed_C.dxf` — 1-block, forced red/blue
