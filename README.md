# ISGEC — TP-104 Conveyor Overlay Pipeline

## Web UI

This repository also includes the standalone upload and review application:

- `frontend/` — Next.js web UI
- `backend/` — FastAPI upload, parsing, and analysis API
- `docker-compose.yml` — starts both services together

With Docker installed, run from the repository root:

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:3001>. Uploaded drawings and the SQLite database are
stored in Docker-managed volumes and are independent of any parent directory.

For local development without Docker:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev -- --hostname 0.0.0.0 --port 3001
```

The frontend automatically uses the backend at port `8001`; set
`NEXT_PUBLIC_API_BASE` if the API is hosted elsewhere.

This directory contains 3 self-contained overlay pipelines for the
**TP-104 conveyor** project (ISGEC / Adani Infra / Dhamra Port). Each
takes the same two source drawings and produces a structurally different
superimposed DXF.

**Source drawings**

| File | Size | Content |
|---|---:|---|
| `dxf/TP-104 MECH GA.dxf` | 16 MB | Mechanical GA — equipment, walls, foundations |
| `dxf/TP-104 STR GA.dxf` | 8.4 MB | Structural GA — beams, columns, connections |

Both share the same labeled gridlines: **TP104-A, TP104-B, TP104-C,
TP104-D** (vertical) and **TP104-1, TP104-2, TP104-3** (horizontal).
Gridline-derived affine aligns STR onto MECH with sub-unit residual
(TP104-A residuals ≲ 0.0005 DXF units).

---

## Three overlay strategies

```
ISGEC/
├── A/    Per-entity overlay       (2,242 modelspace ents, 0 wrappers)
├── B/    2-block overlay          (2 INSERTs: MECH_DRAWING + STR_DRAWING)
└── C/    1-block overlay          (1 INSERT:  OVERLAY_DRAWING)
```

| Approach | Structure | Editability | Color policy |
|---|---|---|---|
| **A** `A/` | Every STR entity copied + transformed into MECH's modelspace | **HIGHEST** (click any member to edit) | **Original colors preserved** (steel stays steel-gray, pipes keep process color, etc.) |
| **B** `B/` | Both drawings wrapped in 2 blocks; 2 INSERTs at modelspace | MEDIUM (click wrapper to move both as one) | **Forced 2-color** (MECH = red ACI 1, STR = blue ACI 5) for high-contrast overlay |
| **C** `C/` | Both drawings merged into 1 block; 1 INSERT at origin | LOW (single grab, the whole overlay moves as one) | **Forced 2-color** (MECH = red, STR = blue) |

A and B/C differ in **color policy**: A keeps each entity's source color
so the overlay looks faithful to the original drawings; B and C force the
traditional red-MECH / blue-STR convention for at-a-glance readability.

All three use the **same affine** derived from labeled gridlines:

```
x_m = 1.000000 · x_s + 208379.8605
y_m = 1.000000 · y_s + -179584.5241
```

---

## Quick start — produce the canonical superimposed.dxf

```bash
cd ISGEC/
python3 run_to_dxf.py        # overlay-only (fast, reuses transform.json)
# → writes dxf/superimposed.dxf, _A.dxf, _B.dxf, _C.dxf
```

| File | Size | Strategy | Color policy |
|---|---:|---|---|
| `dxf/superimposed.dxf` | 18.5 MB | Per-entity (A) | Original colors |
| `dxf/superimposed_A.dxf` | 18.5 MB | Per-entity | Original colors |
| `dxf/superimposed_B.dxf` | 18.5 MB | 2-block | Red/blue forced |
| `dxf/superimposed_C.dxf` | 18.4 MB | 1-block | Red/blue forced |

For a full pipeline (re-clean + re-fit + re-overlay):

```bash
python3 run_to_dxf.py --rewrite-clean
```

Or run any single approach independently:

```bash
cd A/   && ./run.sh    # → out/TP-104 OVERLAY_A.dxf
cd B/   && ./run.sh    # → out/TP-104 OVERLAY_B.dxf
cd C/   && ./run.sh    # → out/TP-104 OVERLAY_C.dxf
```

---

## Pipeline stages

Each approach dir (`A/`, `B/`, `C/`) follows the same 3-stage pipeline:

```
raw DWG/DXF
   │
   ▼
scripts/clean.py     strip annotations, markers, orphan symbols
                     → work/*_clean3.dxf
                     (smart fallback: uses dxf/*_clean3.dxf if DWG
                      conversion unavailable)
   │
   ▼
scripts/fit.py       find labeled TP104-* axes, solve least-squares affine
                     → transform.json
                     (x_m = sx·x_s + tx; y_m = sy·y_s + ty)
   │
   ▼
scripts/overlay.py   apply affine to STR geometry
                     → out/TP-104 OVERLAY_<X>.dxxf
```

### Stage 1 — Cleaning (`scripts/clean.py`)
- DWG → DXF via `ezdxf.addons.odafc` (or fall back to existing
  `dxf/*_clean3.dxf` if ODA File Converter is unavailable)
- Strip annotations: `DIMENSION`, `MTEXT`, `LEADER`, `WIPEOUT` (except
  grid labels)
- Strip marker hexagons on layer `BOX`
- Strip orphan `A$C*` blocks (e.g., `A$C2135de20` ACM_FILLED_HALF symbol)
- Output: `work/TP-104 MECH GA_clean3.dxf` + `work/TP-104 STR GA_clean3.dxf`

### Stage 2 — Fitting (`scripts/fit.py`)
- Walks labeled `TP104-A/B/C/D/1/2/3` TEXT entities on both drawings
- For MECH: walks CEN/HIDDEN centerlines near each label
- For STR: walks inside `GridLine-*` blocks to find the longest
  axis-aligned LINE (avoiding label-bracket markers)
- Solves `least_squares` for `(scale_x, scale_y, tx, ty)`
- Output: `transform.json`

### Stage 3 — Overlay (`scripts/overlay.py`)
- Reads `work/*_clean3.dxf` + `transform.json`
- **A**: Imports STR blocks/entities; pre-scales INSERTs to bake
  `(pos, xscale)` into block-local coords; affine-transforms each entity
  in-place. STR layers renamed `_STR_*` with original colors preserved.
- **B**: Wraps MECH in `MECH_DRAWING` block (no transform); wraps STR in
  `STR_DRAWING` block with the affine baked into the wrapper INSERT's
  `(insert, xscale, yscale)`. All MECH layers forced red, all STR
  layers forced blue (with `_BLUE_*` prefix to avoid collisions).
- **C**: Same per-entity transform as A; everything wrapped in a single
  `OVERLAY_DRAWING` block; 1 INSERT at origin. All MECH layers forced
  red, all STR layers forced blue (with `_STR_*` prefix).

---

## Directory layout

```
ISGEC/
├── A/
│   ├── README.md         ← per-approach docs
│   ├── run.sh
│   ├── scripts/
│   │   ├── clean.py
│   │   ├── fit.py
│   │   └── overlay.py
│   ├── input/            symlinks to ../dwg/*.dwg
│   ├── work/             generated intermediates (gitignored)
│   ├── transform.json    generated by fit.py
│   └── out/
│       └── TP-104 OVERLAY_A.dxf      ← final output (~18 MB)
│
├── B/   (same layout, overlay.py implements 2-block strategy)
├── C/   (same layout, overlay.py implements 1-block strategy)
│
├── docs/
│   └── DXF_CLEANING_GUIDE.md       detailed stripper doc
│
├── dwg/                  source DWG files (read-only)
├── dxf/                  source DXF + _clean3 versions + superimposed outputs
│
├── run_to_dxf.py         driver: drives A/B/C, writes to dxf/
├── verify_all.py         end-to-end audit (3 iterations max)
├── check_overlap.py      pixel-level overlap verification
├── render_structure.py   renders overlays with wrapper markers
└── render_all.py         renders + composites
```

---

## Verification

```bash
# Full pipeline audit (wipes A/B/C/work, A/B/C/out, transform.json, re-runs)
python3 verify_all.py 3

# Pixel-level overlap check (renders each overlay, computes red/blue bboxes)
python3 check_overlap.py
```

Expected results (from latest run):

| Approach | Modelspace | Wrappers | TP104-A residual | Centroid Δ |
|---|---:|---|---:|---:|
| A | 2,242 entities | none | < 0.001 DXF units | ~0 |
| B | 2 INSERTs | MECH_DRAWING + STR_DRAWING | < 0.001 DXF units | ~0 |
| C | 1 INSERT | OVERLAY_DRAWING | < 0.001 DXF units | ~0 |

---

## Rendering

```bash
python3 render_structure.py    # shows wrapper INSERTs as green X — proves A/B/C differ
python3 render_all.py          # side-by-side composite
```

---

## Choosing among A / B / C

| If you need… | Use |
|---|---|
| Edit any individual structural member after overlay | **A** |
| Toggle the entire STR layer on/off with one click | **B** or **C** |
| Re-align STR later by moving a single INSERT | **B** (move `STR_DRAWING`) |
| A single atomic overlay object (embed in another drawing) | **C** |
| Faithful overlay colors (no red/blue rebrand) | **A** |
| Standard red-MECH / blue-STR high-contrast overlay | **B** or **C** |
| Smallest modelspace (1 entity) | **C** |

See `A/README.md`, `B/README.md`, `C/README.md` for per-approach details.
