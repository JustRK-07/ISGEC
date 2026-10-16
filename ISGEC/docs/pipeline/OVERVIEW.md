# Pipeline Overview

> **What it does, source drawings, output sizes, choosing A/B/C.**

The ISGEC pipeline aligns a Mechanical General Arrangement (MECH) drawing with a Structural General Arrangement (STR) drawing using labeled grid bubbles as anchors. The output is a **superimposed DXF** — one drawing containing both MECH and STR geometry, registered to a shared coordinate frame.

This is the **geometry core** of the project. The FastAPI backend (`ISGEC/backend/`) wraps it with the agentic AI layer (LLM normalization, 8 deterministic checks, click-to-locate UI).

---

## 1. The TP-104 Conveyor project (context)

**TP-104** is a conveyor project for **ISGEC / Adani Infra / Dhamra Port** — a real-world engineering deliverable.

### Source drawings

| File | Format | Size | Content |
|---|---|---:|---|
| `TP-104 MECH GA` | `.dwg` | 2.8 MB | Mechanical GA (equipment, walls, foundations) |
| `TP-104 MECH GA` | `.dxf` | 16 MB | DXF export of the same drawing |
| `TP-104 STR GA` | `.dwg` | 1.1 MB | Structural GA (beams, columns, connections) |
| `TP-104 STR GA` | `.dxf` | 8.4 MB | DXF export |

Both drawings share the **same labeled gridlines**:

- **Vertical**: `TP104-A`, `TP104-B`, `TP104-C`, `TP104-D`
- **Horizontal**: `TP104-1`, `TP104-2`, `TP104-3`

This is the key insight: **labeled grids give us 12 anchor points** (4 × 3 intersections) to solve an affine transform. The gridline-derived fit yields sub-unit residual:

```
scale_x = 0.9999999999078191
scale_y = 1.0000000000951985
tx      = 208379.86046213657
ty      = -179584.52411355262
RMS residual  = 2.34e-7 DXF units
MAX residual  = 3.38e-7 DXF units
```

That's precision at the limit of DXF float representation.

### Why this matters

> "The 0.8 scale earlier fit was wrong — it conflated the TEXT-label offset between MECH and STR with a scale. Working from actual gridline LINE positions yields scale = 1.0 in both axes." — `docs/SCRIPTS.md`

The naive approach (matching text-label positions) confuses translation with scale and gives ~20% error. Working from **gridline LINE positions** (the actual geometry) yields scale = 1.0 and sub-unit residual.

---

## 2. Three overlay strategies

Each strategy (`A`, `B`, `C`) is a self-contained pipeline that produces a structurally different DXF. The choice depends on what the downstream user wants:

| If you need… | Use |
|---|---|
| Edit any individual structural member after overlay | **A** |
| Toggle the entire STR layer on/off with one click | **B** or **C** |
| Re-align STR later by moving a single INSERT | **B** (move `STR_DRAWING`) |
| A single atomic overlay object (embed in another drawing) | **C** |
| Faithful overlay colors (no red/blue rebrand) | **A** |
| Standard red-MECH / blue-STR high-contrast overlay | **B** or **C** |
| Smallest modelspace (1 entity) | **C** |

### A — Per-entity overlay

- **Modelspace**: 2,242 entities (MECH + STR baked to MECH coords)
- **Wrappers**: none
- **Editability**: HIGHEST (click any member to edit)
- **Color policy**: original colors preserved (steel stays steel-gray, pipes keep process color)

### B — 2-block overlay

- **Modelspace**: 2 INSERTs (`MECH_DRAWING` + `STR_DRAWING`)
- **Wrappers**: 2
- **Editability**: MEDIUM (click `STR_DRAWING` to grab whole layer)
- **Color policy**: forced 2-color (MECH = red ACI 1, STR = blue ACI 5)

### C — 1-block overlay

- **Modelspace**: 1 INSERT (`OVERLAY_DRAWING`)
- **Wrappers**: 1
- **Editability**: LOW (single grab, the whole overlay moves as one)
- **Color policy**: forced 2-color (same as B)

See **[STRATEGY-A.md](./STRATEGY-A.md)**, **[STRATEGY-B.md](./STRATEGY-B.md)**, **[STRATEGY-C.md](./STRATEGY-C.md)** for per-approach details.

---

## 3. The 3-stage pipeline (clean → fit → overlay)

Every strategy uses the same first two stages; only Stage 3 differs.

```
raw DWG/DXF
   │
   ▼
scripts/clean.py     strip annotations, markers, orphan symbols
                     → work/*_clean3.dxf
   │
   ▼
scripts/fit.py       find labeled TP104-* axes, solve least-squares affine
                     → transform.json
                     (x_m = sx·x_s + tx; y_m = sy·y_s + ty)
   │
   ▼
scripts/overlay.py   apply affine to STR geometry
                     → out/TP-104 OVERLAY_<X>.dxf
```

**Stage 1 — Cleaning** (`scripts/clean.py`)

- DWG → DXF via `ezdxf.addons.odafc` (or fall back to existing `dxf/*_clean3.dxf` if ODA File Converter is unavailable)
- Strip annotations: `DIMENSION`, `MTEXT`, `LEADER`, `WIPEOUT` (except grid labels)
- Strip marker hexagons on layer `BOX`
- Strip orphan `A$C*` blocks (e.g., `A$C2135de20` ACM_FILLED_HALF symbol)
- Output: `work/TP-104 MECH GA_clean3.dxf` + `work/TP-104 STR GA_clean3.dxf`

**Stage 2 — Fitting** (`scripts/fit.py`)

- Walks labeled `TP104-A/B/C/D/1/2/3` TEXT entities on both drawings
- For MECH: walks CEN/HIDDEN centerlines near each label
- For STR: walks inside `GridLine-*` blocks to find the longest axis-aligned LINE (avoiding label-bracket markers)
- Solves `least_squares` for `(scale_x, scale_y, tx, ty)`
- Output: `transform.json`

**Stage 3 — Overlay** (`scripts/overlay.py`, differs per strategy)

- Reads `work/*_clean3.dxf` + `transform.json`
- **A**: Imports STR blocks/entities; pre-scales INSERTs to bake `(pos, xscale)` into block-local coords; affine-transforms each entity in-place. STR layers renamed `_STR_*` with original colors preserved.
- **B**: Wraps MECH in `MECH_DRAWING` block (no transform); wraps STR in `STR_DRAWING` block with the affine baked into the wrapper INSERT's `(insert, xscale, yscale)`. All MECH layers forced red, all STR layers forced blue (with `_BLUE_*` prefix).
- **C**: Same per-entity transform as A; everything wrapped in a single `OVERLAY_DRAWING` block; 1 INSERT at origin. All MECH layers forced red, all STR layers forced blue (with `_STR_*` prefix).

Full details: **[CLEAN-FIT-OVERLAY.md](./CLEAN-FIT-OVERLAY.md)**.

---

## 4. Output files

After `python3 run_to_dxf.py`:

| File | Size | Strategy | Color policy |
|---|---:|---|---|
| `dxf/superimposed.dxf` | 19 MB | Per-entity (A) — canonical | Original colors |
| `dxf/superimposed_A.dxf` | 19 MB | Per-entity | Original colors |
| `dxf/superimposed_B.dxf` | 18 MB | 2-block | Forced red/blue |
| `dxf/superimposed_C.dxf` | 18 MB | 1-block | Forced red/blue |

`superimposed.dxf` is canonical = approach A's output (most editable — 2,242 entities, no block wrapper).

---

## 5. Cleaning iterations (preserved for reference)

The `dxf/` folder contains intermediate cleaning outputs that you don't need to recreate:

| File | Size | What |
|---|---:|---|
| `TP-104 MECH GA_clean.dxf` | 14 MB | Cleaning v1 |
| `TP-104 MECH GA_clean2.dxf` | 14 MB | Cleaning v2 |
| `TP-104 MECH GA_clean3.dxf` | 14 MB | Cleaning v3 — final, used by fit.py + overlay.py |
| `TP-104 MECH GA_clean_R12.dxf` | 14 MB | Round-12 cleaning |
| `superimposed_clean.dxf` | 7.3 MB | Cleaned superimposed output |
| `superimposed_strip_report.json` | 2.5 KB | Strip report (what was removed) |

Same pattern for STR: `_clean`, `_clean2`, `_clean3`, `_clean_R12`. The pipeline always uses `_clean3.dxf` as the final input.

---

## 6. Why three strategies?

The same problem (overlaying two drawings) admits multiple correct answers depending on what the user wants:

- **A** preserves the ability to edit each member → better for downstream design work
- **B** lets you toggle the entire STR layer with one click → better for review and annotation
- **C** packages everything as one atomic object → better for embedding in another drawing

The implementation difference is **how STR geometry is wrapped** — or not wrapped — in the output DXF. The affine transform itself is identical.

This is the "shape vs. substance" tradeoff in DXF authoring: **shape** (block structure) controls editability, **substance** (geometry) is the same across all three.

---

## 7. Reference

- **[CLEAN-FIT-OVERLAY.md](./CLEAN-FIT-OVERLAY.md)** — every step in detail
- **[STRATEGY-A.md](./STRATEGY-A.md)**, **[STRATEGY-B.md](./STRATEGY-B.md)**, **[STRATEGY-C.md](./STRATEGY-C.md)** — per-strategy details
- **[VERIFICATION.md](./VERIFICATION.md)** — verifying the output
- `ISGEC/A/README.md`, `ISGEC/B/README.md`, `ISGEC/C/README.md` — the in-folder READMEs that ship with each approach