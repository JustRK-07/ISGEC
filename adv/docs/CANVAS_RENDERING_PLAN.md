# Canvas & Superimpose Rendering Plan

**Status:** Draft
**Date:** 2026-07-23
**Owner:** ADV frontend
**Goal:** Render the **superimpose of STR GA + MECH GA** in the workspace viewer so the user can visually identify clashes, read the issue evidence, and see a probable fix — matching what `index.html` does and what the reference PDFs (`TP-104 STR GA.pdf`, `TP-104 MECH GA.pdf`, `superimposed.pdf`) show.

---

## 1. Problem statement

Opening any project at `/dashboard/{id}` shows the workspace viewer, but the canvas is **mostly blank** because:

1. **Seeded projects have very few entities.** The TP-104 seed has 1 STR opening + 1 MECH entity. The reference TP-104 STR PDF has hundreds of beams, columns, braces, grid bubbles, and dimensions.
2. **The canvas does not auto-fit.** It uses a hard-coded scale (`0.08 px/mm`) and zero offset, so even existing entities sit in the top-left corner at ~1 cm².
3. **No superimpose.** STR entities render the same color as MECH entities. There is no layering discipline, no clash highlighting, no "this is the issue" red box.
4. **Issue flags don't appear on the canvas.** The right panel lists issues but the canvas itself shows nothing about them.

The user expects the workspace to look like the superimpose reference: STR beams + columns on a cyan grid, MECH ducts + pipes + AHUs on top, **red clash zones with labels** where they collide, and hover-tooltips showing evidence + a suggested fix.

---

## 2. Options considered

### Option A — Server-side DWG → SVG/PNG render, served as a background image

Use ODA File Converter or `libredwg` to convert the uploaded `.dwg` to `.svg` on the backend, then the frontend loads the SVG as an `<img>` behind the entity overlay.

| Pros | Cons |
|------|------|
| Pixel-accurate to the source drawing | Requires ODA / libredwg (heavy native deps) |
| Works with any DWG, no parser work | Adds 2–5 s per upload |
| Output is small, scalable | Brittle — depends on tooling installed on the host |
| Real text, dimensions, hatching | Real DWGs from AutoCAD often have proxy entities that fail to convert |

### Option B — Browser-side DWG parser (three-dwg, dwg-viewer, etc.)

Load a JS library that parses the binary `.dwg` and renders it to a canvas/SVG in the browser.

| Pros | Cons |
|------|------|
| Zero backend changes | Most libraries are abandoned, unmaintained |
| Live updates if the user uploads again | Cannot reliably parse real-world DWGs |
| | Heavy bundles (megabytes of WASM) |
| | No good free library — Autodesk Forge needs a paid API |

### Option C — Server-side DWG → PDF, client renders PDF page via PDF.js

Convert DWG to PDF on the backend (ODA), then render the PDF page onto our canvas using `pdfjs-dist`.

| Pros | Cons |
|------|------|
| PDF.js is mature and fast | Still needs ODA on the server |
| Works with any DWG | Two layers of tooling to maintain |
| Good text/vector fidelity | Loses the live, entity-level data we already have |

### Option D — Render superimpose from parsed entity data + issue overlay (chosen)

Use the entities + issues that the backend already returns. Auto-fit the viewport to the entity bounding box, color by discipline/kind, render MECH on top of STR with a small alpha, draw issue flags as red dashed boxes with code labels and hover tooltips.

| Pros | Cons |
|------|------|
| **Zero new infra.** Uses API we already have | Not pixel-accurate to the source DWG |
| Scales from 2 entities to 2000+ | Requires the parser to produce enough entities |
| Clash detection + probable solution is already in `issues[]` | Won't show original AutoCAD text formatting |
| Same data path the right panel uses, fully consistent | |
| **Exact match to the goal** — superimpose + clashes + solutions | |

---

## 3. Why Option D wins

The goal is **superimpose with clash detection and probable solutions**, not pixel-accurate DWG rendering. The reference PDFs (`TP-104 STR GA.pdf`, `superimposed.pdf`) themselves are produced by AutoCAD, but the *information the user actually needs* is:

- Where do STR and MECH overlap?
- Which clash is at which grid?
- What is the evidence (mm gap, formula)?
- What is the suggested fix?

All of this is already in the API response (`entities.str`, `entities.mech`, `issues[]`). Drawing rectangles at the right `(x_mm, y_mm)` with the right color and overlay is exactly what the user sees in the superimpose reference, just generalized.

Options A/B/C all chase pixel-accuracy we don't need. They each add heavy dependencies and hours of setup, with the same result the user already has from the reference PDF (which they can open in any viewer).

**Option D** matches the goal exactly:

- Visual superimpose: STR (cyan grid + magenta beams) + MECH (cyan ducts, rust pipes, amber equipment) on one canvas.
- Issue flags: red dashed boxes at clash coordinates with the issue code label inside.
- Probable solution: hover tooltip with `evidence` + `formula` + category-derived suggested fix.
- Works with any uploaded drawing once the parser produces enough entities.

---

## 4. Visual target

Mirrors the references:

| Layer | Source | Color | Reference |
|-------|--------|-------|-----------|
| Grid bubbles (G/C/B/A, 1/2/3) | static frame | cyan outline + label | superimposed.pdf edge labels |
| STR beams | `entities.str[kind=beam]` | magenta rect (`#C84B1F`) | STR GA.pdf TP4BMxxx beams |
| STR columns | `entities.str[kind=column]` | navy filled square (`#0E1B2C`) | STR GA.pdf orange octagons |
| STR braces | `entities.str[kind=brace]` | dashed yellow diagonal | STR GA.pdf BR1 diagonals |
| STR text labels | `entities.str[kind=text]` | dark navy text | STR GA.pdf TP4BM111 tags |
| MECH ducts | `entities.mech[kind=duct]` | cyan rounded rect (`#1E88A8`) at α=0.85 | MECH GA.pdf yellow ductwork |
| MECH pipes | `entities.mech[kind=pipe]` | rust red line (`#C84B1F`) | MECH GA.pdf magenta pipe runs |
| MECH equipment | `entities.mech[kind=equipment]` | dashed rust box (`#C84B1F`) | MECH GA.pdf AHU/FCU boxes |
| MECH sleeves | `entities.mech[kind=sleeve]` | cyan dashed circle | MECH GA.pdf SLV circles |
| Issue flag | `issues[]` | solid red dashed box + code label | superimposed.pdf red filled regions |

---

## 5. Phased implementation

### Phase 1 — Rich seed for TP-104 (immediate visual win)

Pre-populate the seeded TP-104 project with realistic entities + issues so the canvas has something to show.

- **~20 STR entities**: 10 beams (`TP4BM101…110`), 8 columns (`TP4BC01…08`), 2 BR1 braces.
- **~8 MECH entities**: 3 ducts (`DUCT-01`, `DUCT-02`, `DUCT-03`), 2 pipes (`PIPE-DN150`, `PIPE-DN100`), 1 AHU, 1 FCU, 1 sleeve.
- **3 issues**: `WBE-B46-001` (DUCT-01 ↔ STB13 clash, severity high), `WBE-B46-002` (DUCT-02 ↔ STC02, severity medium), `WBE-B46-003` (AHU-01 ↔ STC01, severity medium).
- Sheet = `0001`, grid coords anchored at `TP104-C/2`, `TP104-G/3`, `TP104-A/2`.

### Phase 2 — `DrawingCanvas` rewrite

- **Auto-fit**: compute entity bounding box, set `scale` so the box fills ~85% of the viewport, set `offset` to centre it.
- **Discipline-aware rendering**: STR first (full alpha), MECH second (alpha 0.85), issues last (dashed red, with code label).
- **Color map** matching the visual target table above.
- **Hover**: detect mouse over an issue flag, show tooltip with `code`, `title`, `evidence`, `formula`, **suggested fix** based on category.

### Phase 3 — Issue flag overlay + probable solution

- For each `issues[]` entry with `sheet === activeSheet`, draw a red dashed box centred at the issue's grid coords (lookup from `entities` by `mech_ref` / `str_ref`).
- Tooltip appears on hover, disappears on mouseleave.
- "Suggested fix" computed from `issue.code` / `category`:
  - clearance → "Raise duct 50 mm or reroute around grid"
  - clash → "Offset DUCT-01 by 75 mm to clear STB13"
  - missing → "Add required opening per STR spec"

### Phase 4 — Playwright verification loop

- Open `/dashboard/{tp-104-id}`, screenshot the canvas, sample pixel colours.
- Pass criteria:
  - ≥ 3 distinct colour clusters detected (magenta, cyan, red)
  - ≥ 1 red dashed box visible at a known issue grid
  - Hovering an issue shows a tooltip with text
- Iterate Phase 2 / Phase 3 until pass.

### Phase 5 — Loosen the parser (later)

Once Phase 1–4 look right, broaden `parse.py` filters so real uploaded DWGs produce a similarly rich entity set (every LINE/LWPOLYLINE/CIRCLE on a STR/MECH layer).

---

## 6. Files to touch

| File | Change |
|------|--------|
| `backend/app/seed.py` (or equivalent) | Phase 1: rich TP-104 seed |
| `frontend/components/workspace/DrawingCanvas.tsx` | Phase 2: auto-fit + colors |
| `frontend/components/workspace/IssueInspector.tsx` | Phase 3: surface `suggested_fix` per category |
| `frontend/app/dashboard/[id]/page.tsx` | wire issues into DrawingCanvas |
| `frontend/app/globals.css` | tooltip + flag CSS |

---

## 7. Acceptance criteria

- [ ] Opening TP-104 shows a clearly recognisable superimpose: cyan STR grid lines + magenta STR beams + cyan MECH ducts + rust MECH pipes + amber equipment.
- [ ] At least 3 red dashed issue flags visible on the canvas.
- [ ] Hovering an issue flag shows a tooltip with `evidence`, `formula`, and a category-specific suggested fix.
- [ ] Resizing the browser keeps the superimpose centred and proportional.
- [ ] Tabs (STR / MECH / OVERLAY) toggle which discipline is drawn; OVERLAY is default and shows all.
- [ ] Canvas pixel sample via Playwright confirms ≥ 3 distinct colour clusters and ≥ 1 red-flag region.