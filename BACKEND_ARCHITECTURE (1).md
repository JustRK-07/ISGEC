# ADV — Backend Architecture & Algorithms

> **Scope:** Detailed technical specification of every layer in the ADV
> pipeline, derived from `WEBSITE_CONTENT_BRIEF.md` and `index.html`.
> **Audience:** Backend engineers, ML engineers, QA leads.
> **Status:** Design specification — code not yet implemented.

> **Rev 2 changelog:** Added file validation & malware scan (§1.5),
> XREF / nested block resolution (§2.6), grid-detection fallback (§3.5),
> cross-drawing coordinate alignment (§3.6), LLM chunking strategy at
> scale (§4.7), superimposed model file generation (§6.5), and a new
> Test & Validation Strategy section (§15). These close gaps identified
> in review: prior draft under-specified what happens when grid
> detection fails, when drawings don't share a common origin/rotation,
> when entities live in external references, and what file — not just
> a viewer payload — "superimposed model" actually refers to.

---

## 0. What ADV does, in one paragraph

ADV reads a **Mechanical General Arrangement (GA)** DWG and a
**Structural GA** DWG of the same floor and validates that every
support, opening, and penetration required by Mech is actually
provided by Str — with the correct size, at the correct position,
at the correct elevation, with the correct clearance, and without
colliding with a structural member. Every finding is grounded to a
**sheet**, a **grid intersection**, an **element**, and an **exact
formula**. The pipeline runs **100 % on-prem** behind a
**self-hosted local LLM** — no third-party API is ever called.

```
   L0            L1            L2            L3              L4
INGESTION →   DWG → DXF   →  GRID / COORD → NORMALISATION →  RULES    →  L5 REPORT
+ REVISION   ENTITY         REGISTRATION    (LOCAL LLM)    (DETERMINISTIC)
LEDGER        EXTRACT
```

**Core principle:** *reading* (L3) is probabilistic. *Checking* (L4)
is exact. Findings are deterministic, not confidence-scored.

---

## 1. Layer 0 — Ingestion & Revision Lock

**Source spec:** `WEBSITE_CONTENT_BRIEF.md §3` (Layer 0 block, lines 107–110).

### 1.1 Purpose

Stop validating against a stale baseline. Engineers routinely review
against Rev A when Rev C has already been issued; the ledger makes
the revision chain explicit.

### 1.2 Algorithm

```
input:  uploaded DWG file (binary blob)
output: revision ledger entry

Step 1. Compute SHA-256 of the raw bytes
        digest = sha256(file_bytes).hexdigest()   # 64 hex chars

Step 2. Lookup digest in revision ledger
        if digest known:
            → reject upload (409 Conflict: "file already ingested")
        else:
            → proceed

Step 3. Detect supersession
        if a sibling file with the same `family_id` exists and the new
        file differs from it:
            → increment revision_letter (A → B → C)
            → set supersedes = previous_revision_id

Step 4. Persist
        INSERT INTO revisions (
            id, family_id, revision_letter, sha256, filename,
            size_bytes, uploaded_by, uploaded_at, project_id
        )
```

### 1.3 Data contract

```json
{
  "revision_id":     "uuid-v4",
  "family_id":       "TP104-STR-GA",
  "revision_letter": "C",
  "supersedes":      "<prev_revision_id or null>",
  "sha256":          "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "filename":        "TP-104 STR GA.dwg",
  "size_bytes":      3131396,
  "uploaded_by":     "user-uuid",
  "uploaded_at":     "2026-07-14T16:42:00Z",
  "project_id":      "project-uuid"
}
```

### 1.4 Tech

- **SHA-256**: Python stdlib `hashlib`.
- **Revision ledger**: PostgreSQL.
- **Why Git-like**: revisions form a DAG via `supersedes` → enables
  `git log`-style diff between any two revisions in later layers.

### 1.5 File validation & malware scan

**Gap closed:** the original spec hashed and stored the file but never
validated it before handing it to the DWG parser. DWG/DXF files can
carry embedded macros (VBA, LISP autoload scripts) and malformed files
can crash or hang a parser.

```
input:  uploaded file bytes, declared extension
output: pass | reject(reason)

Step 1. Extension / magic-byte check
        DWG files start with a version tag, e.g. "AC1032" (2018+).
        Reject if magic bytes don't match a known AutoCAD version
        table, regardless of the uploaded filename's extension.

Step 2. Size & entity-count guard
        reject if size_bytes > project_max (default 500 MB)
        reject if a quick header scan reports an entity count that
        would exceed the L1 parser's practical ceiling — surface a
        clear "drawing too large, split by discipline/floor" error
        instead of a silent timeout downstream.

Step 3. Antivirus / macro scan
        run ClamAV (or house AV) against the raw bytes
        flag (do not silently strip) any embedded VBA/LISP payload —
        AEC firms sometimes ship legitimate LISP routines with a
        drawing, so the action is "quarantine + notify", not delete.

Step 4. Sandboxed conversion
        Step 2 of §2.2 (ODA File Converter invocation) runs inside a
        resource-limited container (CPU/mem/time caps, no outbound
        network) so a malformed or hostile file can't affect other
        tenants' jobs.

Step 5. Record scan result alongside the revision ledger entry
        UPDATE revisions SET scan_status, scan_engine, scanned_at
```

---

## 2. Layer 1 — DWG → DXF & Entity Extraction

**Source spec:** `WEBSITE_CONTENT_BRIEF.md §3` (Layer 1 block, lines 112–115) and §8 (Supported Formats table, lines 303–308).

### 2.1 Purpose

Read what the engineer actually drafted — not a flattened raster. DWG
already stores real-world mm, layer names, block definitions, and line
types. All of this is **lost** when the drawing is exported to PDF.

### 2.2 Algorithm

```
input:  file.dwg  (AutoCAD binary)  | file.dxf  (text)
output: entities[]  (JSON list of every primitive)

Step 1. Convert if needed
        if extension == ".dwg":
            invoke ODAFileConverter file.dwg out_dir ACAD2018 DXF
            (free CLI; LibreDWG `dwg2dxf` as fallback)
        if extension == ".dxf":
            skip conversion

Step 2. Parse DXF with ezdxf
        doc = ezdxf.readfile("file.dxf")
        msp = doc.modelspace()

Step 3. Read $INSUNITS header
        header_units = doc.header["$INSUNITS"]
        # 6 = millimetres, 4 = millimetres too, 1 = inches, …
        # Most AEC DWGs are 6.

Step 4. Walk every entity, classify, capture
        for e in msp:
            rec = {
                "handle":   e.dxf.handle,           # unique DXF handle
                "type":     e.dxftype(),             # LINE, LWPOLYLINE,
                                                     # TEXT, MTEXT, INSERT,
                                                     # HATCH, DIMENSION, …
                "layer":    e.dxf.layer,             # "TP4BM-DIMS",
                                                     # "GRID-A", "OPENINGS"
                "color":    e.dxf.color,
                "ltype":    e.dxf.linetype,
                "coords":   to_xy(e),                # flat (x,y) list
                "text":     e.dxf.text if TEXT else None,
                "block":    e.dxf.name if INSERT else None,
                "rotation": e.dxf.rotation if INSERT else None
            }
            entities.append(rec)

Step 5. Extract block definitions
        for b in doc.blocks:
            blocks[b.name] = block_to_polygon(b)

Step 6. Emit
        write entities.json
```

### 2.3 Entity record schema

```json
{
  "handle":   "1A2B",
  "type":     "LWPOLYLINE",
  "layer":    "P11",
  "color":    7,
  "ltype":    "ByLayer",
  "coords":   [[12000, 6500], [12300, 6500], [12300, 6700], [12000, 6700]],
  "text":     null,
  "block":    null,
  "rotation": 0.0
}
```

### 2.4 Tech

- **ezdxf** — pure-Python DXF parser.
- **ODA File Converter** — free CLI for DWG → DXF (newer ACAD versions).
- **LibreDWG** — open-source fallback `dwg2dxf`.

### 2.5 Format-handling matrix (per §8)

| Input | Path | Notes |
|---|---|---|
| `.dwg` | ODA File Converter + ezdxf | Primary format; layers, blocks, line types preserved |
| `.dxf` | ezdxf direct | Text-readable, no conversion |
| `.ifc` | ifcopenshell | BIM model export for 3D validation |
| `.rvt` | Autodesk Forge / Revit API | Direct Revit model query |
| `.pdf` (DWG-exported) | PyMuPDF | Reference only — falls through to vision path |
| Scanned legacy sheets | Local multimodal LLM + Tesseract OCR fallback | Runs entirely on-prem |

### 2.6 XREF & nested block resolution

**Gap closed:** the original entity walk (Step 4, §2.2) only reads
what's physically inside the uploaded file. Real GA drawings very
often `INSERT` an **external reference (XREF)** — a title block, a
grid template, sometimes the whole floor plan — that lives in a
separate `.dwg` on someone's server. Walking `msp` alone silently
misses anything drawn in an unresolved XREF, which is exactly the kind
of support/opening geometry this tool exists to check.

```
input:  file.dxf, list of XREF paths declared in the DWG header
output: entities[] with XREF content inlined (bound), or an explicit
        "unresolved reference" warning

Step 1. Enumerate external references
        for xref in doc.entitydb.xref_definitions():
            record(xref.path, xref.name, xref.is_resolved)

Step 2. Attempt local resolution
        if xref.path exists in the same upload batch or project
        drawing library:
            bind it (ezdxf's `xref.bind()` or equivalent) so its
            entities merge into modelspace before Step 4 of §2.2 runs

Step 3. Surface unresolved references instead of skipping them
        if xref.path cannot be found:
            do NOT proceed silently
            → emit a UI warning: "Drawing references '<name>.dwg'
              which was not uploaded — entities inside it were not
              checked. Upload it or confirm it contains no supports/
              openings."
        This turns a silent blind spot into an explicit, reviewable
        gap the reviewer must acknowledge before sign-off.

Step 4. Nested block depth
        block_to_polygon() (Step 5, §2.2) recurses into block
        definitions that themselves INSERT other blocks (common for
        parametric duct/beam symbols). Cap recursion depth (default 8)
        and log a warning rather than infinite-looping on a
        self-referential block — which does occasionally happen in
        legacy drawings.
```

---

## 3. Layer 2 — Grid & Coordinate Registration

**Source spec:** `WEBSITE_CONTENT_BRIEF.md §3` (Layer 2 block, lines 117–120) and §5 Step 2 (line 242).

### 3.1 Purpose

Put every entity on a **shared coordinate frame** so distance formulas
between Mech and Str drawings are meaningful. Without grid
registration, "the Mech opening at grid B/2" and "the Str opening at
grid B/2" are just two unrelated points.

### 3.2 Algorithm

```
input:  entities[]  (Layer 1 output), header_units
output: grid_map { grid_id → (x_mm, y_mm) } + entities_with_grid[]

Step 1. Detect grid-bubble labels in TEXT / MTEXT entities
        letter_grids  = regex  ^[A-Z]\d{3}-[A-Z]$   → "TP104-A"
        numeric_grids = regex  ^\d{1,2}$            → "1", "2", "3"
        confidence raised when text is inside a circle/hex bubble block

Step 2. Group bubbles into grid lines
        bubbles_with_prefix("TP104") form one grid system
        for each label, compute centroid (x, y) of nearby LINE entities
        on the matching GRID layer

Step 3. Build grid_map
        grid_map["TP104-B"]     = (xb, y1)        # along grid line 1
        grid_map["TP104-B/2"]   = (xb, y_of_2)
        grid_map["TP104-C/2"]   = (xc, y_of_2)
        …

Step 4. Annotate entities with nearest grid
        for e in entities:
            e.nearest_grid = argmin_distance(e.centroid, grid_map)
            e.grid_x = e.nearest_grid.x_grid
            e.grid_y = e.nearest_grid.y_grid

Step 5. Convert all coordinates to mm
        if header_units != 6:
            scale factor = mm_per_unit(header_units)
            e.coords = scale(e.coords, factor)
```

### 3.3 The "Ingestion Agent" role

Per §5 Step 2: the Ingestion Agent *also* auto-detects vector vs
raster and dispatches to the right extraction path (L1 vector
pipeline or L1 vision/OCR fallback for scanned sheets).

### 3.4 Why "no scale detection"

DWG's `$INSUNITS` header already declares real-world units (typically
6 = mm for AEC). Unlike PDF/image input, we never have to guess
"this line is 5 px long, so it's X mm at this scale". This is the
central technical reason DWG-native is preferred over raster.

### 3.5 Fallback when grid detection fails

**Gap closed:** Step 1 of §3.2 depends entirely on regex matches
against TEXT/MTEXT and a nearby bubble block. The original spec never
said what happens when a firm labels grids non-standardly, grids sit
on an unexpected layer, or bubbles are exploded (plain lines + text,
no block reference) — all common in older or non-conforming drawings.
Silently mis-registering here corrupts every downstream distance
check, so failure must be loud, not silent.

```
Step 1. Confidence-score every candidate grid label
        score = f(regex_match, inside_bubble_block, on_GRID*_layer,
                   collinear_with_other_same-letter/number labels)

Step 2. Threshold
        if grid_map coverage ≥ 90% of expected grids (from project
        metadata, e.g. "8 lettered x 6 numbered grids expected"):
            → proceed automatically
        elif 50–90% coverage:
            → proceed, but flag "partial grid registration" and list
              which grid lines are missing; reviewer confirms before
              L4 runs
        else (< 50%):
            → do NOT proceed to L3/L4 automatically
            → route to manual grid-pick UI: reviewer clicks 2+ known
              grid intersections directly on the rendered drawing;
              those clicks seed grid_map and the rest is interpolated

Step 3. Log which path was taken
        every finding downstream carries a `grid_registration_method`
        tag (`auto` | `auto+reviewer-confirmed` | `manual`) so an
        auditor can see how much of the coordinate frame was
        human-assisted.
```

### 3.6 Cross-drawing coordinate alignment

**Gap closed:** §3.2 registers each drawing's *own* grid, but never
addresses that Mech GA and Structural GA are usually drawn as separate
files with independent insertion points and sometimes a rotation
offset (true north vs. plan north conventions differ by discipline).
Two files can each have a perfectly good internal grid_map and still
disagree in world space.

```
input:  grid_map_mech, grid_map_str  (shared grid IDs, e.g. "B/2")
output: transform_str_to_mech  (rotation θ, translation tx/ty, and a
        residual-error report)

Step 1. Find shared grid labels
        shared = grid_map_mech.keys() ∩ grid_map_str.keys()
        require ≥ 3 shared, non-collinear points to solve for
        rotation + translation (2 points can't distinguish a mirror
        flip from a rotation)

Step 2. Solve rigid-body transform (Procrustes / least squares)
        minimize Σ ‖ R·p_str[i] + t − p_mech[i] ‖²  over rotation R,
        translation t, for each shared grid point i

Step 3. Reject if residual is too large
        if max residual > registration_tolerance_mm (default 25mm):
            → do not silently apply the transform
            → flag "Mech/Str grids do not align within tolerance —
              possible wrong revision, wrong floor, or drafting error"
        else:
            → apply transform to every Str entity before L3 so both
              drawings' coordinates are directly comparable

Step 4. Persist the transform with the finding set
        so every downstream Position/Elevation check formula (§5.3
        Check 2, 6) can be traced back to exactly which registration
        was used — this becomes part of the audit trail, not a
        hidden preprocessing step.
```

---

## 4. Layer 3 — Semantic Normalization (Agent Layer)

**Source spec:** `WEBSITE_CONTENT_BRIEF.md §3` (Layer 3 block, lines 122–131), §4 Capability 1, §15 FAQ #8, and §10 (Zero-API callout).

### 4.1 Purpose

Collapse firm-specific naming chaos into **one canonical schema**.
Different firms call the same physical beam different things
(`F11WE`, `TP4BM101`, `BM-203-ISMC150`, `M-OP-203`); downstream rules
must not have to learn every firm's convention.

### 4.2 Canonical schema (output of this layer)

```
Support    { id, type: restraint|anchor|guide, grid, x_mm, y_mm, load_kg, fluid }
Opening    { id, service: duct|pipe|cable, grid, x, y, w, h, elevation }
Member     { id, type: beam|column|brace, section, grid_start, grid_end, profile }
Tolerance  { project_default, opening_size, position, elevation }
```

### 4.3 Taxonomies enforced by the schema (per §4 Capability 1)

| Element | Allowed values |
|---|---|
| Support `type` | `restraint` \| `anchor` \| `guide` \| `saddle` |
| Opening `service` | `duct` \| `pipe` \| `cable-tray` \| `sleeve` \| `trench` |
| Member `type` | `beam` \| `column` \| `brace` \| `truss` \| `joist` |
| Auto-detected tag patterns | `F11WE`, `TP4BM101`, `M-OP-203`, … |

### 4.4 Algorithm

```
input:  entities[] (Layer 2 output), project metadata, firm convention hints
output: normalized.json (canonical schema)

Step 1. Chunk entities into element-sized groups
        group by layer convention + spatial proximity + entity type
        one chunk ≈ one physical element
        (e.g. 4 lines + 1 text label on layer "P11" → one opening chunk)

Step 2. Build LLM prompt
        system: "You are an AEC drawing normalizer. Read raw DWG entities
                and emit canonical JSON matching this schema. Output only
                valid JSON, no prose."
        user:   chunk_entities (JSON), project_meta, firm_convention_hint
        constraint: JSON-schema / GBNF grammar baked into the inference
                    call → physically masks non-conforming tokens at
                    sampling time

Step 3. Local LLM inference
        server = Ollama / vLLM / llama.cpp serving an open-weight model
        candidates (swappable):
            - Qwen   (text + vision)
            - Llama  (3.3 70B / 4 Scout)
            - DeepSeek (V3 / R1)
            - Mistral (Large / Mixtral)
            - IBM Granite (enterprise-tuned)
        call returns a JSON object conformant to the canonical schema

Step 4. Validate
        JSON-Schema validator on every output
        required fields present, types correct, units in mm/m
        reject + re-prompt if validation fails (max 2 retries)

Step 5. Persist
        INSERT INTO elements (project_id, discipline, source_sha,
                              raw_chunk_json, normalized_json)
```

### 4.5 Why a local LLM (not a hosted API)

Per §10 Zero-API callout and §15 FAQ #8:

> **No drawing data ever leaves your infrastructure.** All LLM
> inference runs locally on your hardware — Ollama, vLLM, or
> llama.cpp serving an open-weight model. No tokens, no rate
> limits, no API keys, no telemetry to third parties. Models are
> swappable (Qwen, Llama, DeepSeek, Mistral, Granite).

**Consequences:**

| Property | How it's achieved |
|---|---|
| **Zero third-party API calls** | Inference runs on local GPU/CPU only |
| **No API key, no quota, no telemetry** | No outbound HTTP to OpenAI/Anthropic/Google |
| **Swappable model** | Orchestration layer is model-agnostic; only the prompt + grammar change |
| **Structured output is enforced, not hoped for** | GBNF grammar / JSON-schema masks non-conforming tokens at sampling time |
| **Model can be fine-tuned later without code changes** | Same client interface |

### 4.6 Tool-calling

The agent uses tool-calling for two side tasks (per §3 Layer 3 tech):

- "Look up section library for ISMC150" → returns `depth=150, flange_w=75, mass_kgm=14.9` from a local YAML/JSON library.
- "Resolve elevation string `+13.150m`" → returns `13.150` as float metres.

### 4.7 Chunking strategy at scale

**Gap closed:** §4.4 Step 1 says "chunk entities into element-sized
groups" but a single GA sheet can carry several thousand entities, and
the original spec never defines chunk size limits, overlap handling,
or what happens when one physical element's entities span a chunk
boundary — all of which affect context-window budget and correctness.

```
Step 1. Spatial tiling first, semantic chunking second
        overlay a coarse grid (e.g. 5m x 5m tiles) aligned to the
        drawing's own grid lines (§3) — not an arbitrary pixel grid
        for each tile: gather entities whose bounding box centroid
        falls inside it, PLUS a small overlap margin (e.g. 500mm)
        so an element straddling a tile edge isn't split

Step 2. Cap chunk token budget
        estimate tokens ≈ entity_count * avg_tokens_per_entity
        if a tile still exceeds the model's practical context budget
        (leave headroom for system prompt + schema + output):
            subdivide the tile further (quadtree-style) rather than
            truncating entities, since truncation silently drops
            geometry from a compliance check

Step 3. De-duplicate elements seen in the overlap margin
        an element whose entities appear in two adjacent chunks
        (because of the overlap) is normalized twice; de-dupe by
        matching centroid + tag before persisting to `elements` (§4.4
        Step 5) so it isn't double-counted as two supports/openings

Step 4. Track chunk provenance
        each normalized element keeps `source_tile_id` so a reviewer
        can trace an odd normalization back to the exact spatial
        region and raw entity chunk that produced it
```

---

## 5. Layer 4 — Rule Engine (Deterministic)

**Source spec:** `WEBSITE_CONTENT_BRIEF.md §3` (Layer 4 block, lines 132–145), §4 Capability 2 + 3 + 4.

### 5.1 Purpose

Run **exact math** against the canonical schema. This is where
findings are born. Eight checks.

### 5.2 Tech stack

- **Python** (orchestration)
- **Shapely** — 2D geometry (intersection, distance, polygons)
- **NumPy** — linear algebra, vectorisation
- **RapidFuzz** — Levenshtein / fuzzy string distance
- **sentence-transformers** — semantic embeddings for tag similarity

### 5.3 The 8 checks

---

#### Check 1 — Fuzzy ID Match (cross-discipline)

> *"Mechanical and Structural drawings rarely share the same tag for
> the same physical item. The matching engine combines Levenshtein
> distance, semantic embeddings, and grid proximity to pair items
> correctly — even when one side says `F11WE` and the other says
> `TP4BM101`."* — §4 Capability 3

```python
def match(mech_list, str_list) -> list[(mech_id, str_id, score)]:
    pairs = []
    for m in mech_list:
        for s in str_list:
            lev = rapidfuzz.fuzz.ratio(m.tag, s.tag) / 100          # Levenshtein
            cos = util.cos_sim(embed(m.tag), embed(s.tag)).item()   # sentence-transformer
            grid_dist = euclid(m.grid_xy, s.grid_xy)
            prox = 1.0 / (1.0 + grid_dist / 1000)                    # grid-bubble proximity
            score = 0.45*lev + 0.40*cos + 0.15*prox
            if score > 0.55:
                pairs.append((m.id, s.id, score))
    return best_one_to_one(pairs)      # Hungarian assignment
```

Confidence bands (per §4 Capability 3):

| Band | Score | Action |
|---|---|---|
| Pass | ≥ 0.80 | Auto-accepted |
| Verify | 0.55–0.80 | Flagged for reviewer confirmation |
| Manual | < 0.55 | Not matched; reviewer pairs manually |

---

#### Check 2 — Position Tolerance (Euclidean)

```python
def position_check(m, s, tol_mm) -> Finding | None:
    dx = m.x_mm - s.x_mm
    dy = m.y_mm - s.y_mm
    dist = math.hypot(dx, dy)
    if dist > tol_mm:
        return Finding(
            type="POSITION",
            delta_mm=dist,
            rule=f"Euclidean distance > ±{tol_mm} mm",
            formula=f"√((Δx={dx})² + (Δy={dy})²) = {dist:.0f} mm"
        )
```

---

#### Check 3 — Size Tolerance (per-axis)

```python
def size_check(m, s, w_tol_mm, h_tol_mm) -> Finding | None:
    dw = s.w_mm - m.w_mm            # positive = opening bigger
    dh = s.h_mm - m.h_mm
    if abs(dw) > w_tol_mm or abs(dh) > h_tol_mm:
        return Finding(
            type="SIZE",
            delta={"w_mm": dw, "h_mm": dh},
            rule=f"per-axis > ±{w_tol_mm}/{h_tol_mm} mm"
        )
```

---

#### Check 4 — Polygon-level Clash Detection

> *"Bounding boxes are too coarse. The clash engine converts every
> footprint and member into polygons … then computes true geometric
> intersection and clearance distance using Shapely."* — §4 Capability 4

```python
def clash_check(mech_polys, str_polys) -> list[Finding]:
    findings = []
    sindex = STRtree(str_polys)                    # Shapely R-tree
    for mp in mech_polys:
        for sp in sindex.query(mp):                # candidate Str polys
            if mp.intersects(sp):
                inter = mp.intersection(sp)
                findings.append(Finding(
                    type="HARD_CLASH",
                    area_mm2=inter.area,
                    mech_id=mp.id,
                    str_id=sp.id,
                    polygon_wkt=inter.wkt
                ))
    return findings
```

Polygon-vs-AABB distinction matters: a 300×200 duct at 45° to a
beam can have zero AABB overlap yet physically intersect.

---

#### Check 5 — Clearance Zone Violation

```python
def clearance_check(m_poly, s_poly, min_clear_mm) -> Finding | None:
    d = m_poly.distance(s_poly)                    # Shapely built-in
    if 0 < d < min_clear_mm:
        return Finding(
            type="CLEARANCE",
            delta_mm=min_clear_mm - d,
            rule=f"required ≥ {min_clear_mm} mm, provided {d:.0f} mm"
        )
```

Example from §4 Capability 4: *"50 mm required, 20 mm provided → flag"*.

---

#### Check 6 — Elevation / T.O.S. Alignment

```python
def elevation_check(m, s, tol_mm) -> Finding | None:
    d_mm = abs(m.elevation_m - s.elevation_m) * 1000
    if d_mm > tol_mm:
        return Finding(
            type="ELEVATION",
            delta_mm=d_mm,
            rule=f"|ΔEL| > ±{tol_mm} mm",
            formula=f"|{m.elevation_m} - {s.elevation_m}|·1000 = {d_mm:.0f} mm"
        )
```

Example from §4 Capability 2: *"+13.150m required, +13.350m provided → flag"*.
Elevation values come from L3, which extracts them from "T.O.S.",
"EL.", "LVL CD(+)" text annotations.

---

#### Check 7 — Required-but-Missing

> A Mech-required support or opening has no fuzzy match in Str.

```python
def missing_check(mech_list, matched_str_ids) -> list[Finding]:
    return [
        Finding(type="MISSING", mech_id=m.id,
                rule="Required by Mech, not provided by Str")
        for m in mech_list
        if m.id not in matched_str_ids
    ]
```

---

#### Check 8 — Provided-but-Orphaned

> A Str-provided opening has no Mech requirement (engineer added it
> without consulting Mech — usually wrong).

```python
def orphan_check(str_list, matched_mech_ids) -> list[Finding]:
    return [
        Finding(type="ORPHAN", str_id=s.id,
                rule="Provided by Str, not required by Mech")
        for s in str_list
        if s.id not in matched_mech_ids
    ]
```

---

### 5.4 Finding record (L4 output)

Every finding carries the rule, the formula, and the numeric delta:

```json
{
  "finding_id":   "FND-0042",
  "type":         "POSITION_AND_SIZE",
  "severity":     "FAIL",
  "sheet":        "S-01",
  "rev":          "C",
  "grid":         "TP104-B/2",
  "elevation_m":  13.150,
  "mech": { "id": "OP-203", "w_mm": 300, "h_mm": 200, "x_mm": 12400 },
  "str":  { "id": "P11",    "w_mm": 250, "h_mm": 200, "x_mm": 12400 },
  "rule": [
    "Δw = 250 - 300 = -50 mm (required ±10)",
    "ΔEL = |13.150 - 13.350|·1000 = 200 mm (required ±50)"
  ],
  "formula": "√((Δx)² + (Δy)²); |Δelevation|·1000",
  "result_mm": { "width": -50, "elevation": 200 }
}
```

**No confidence percentages.** Every number is traceable to a formula.

---

## 6. Layer 5 — Reporting & Sign-off

**Source spec:** `WEBSITE_CONTENT_BRIEF.md §3` (Layer 5 stage implied) and §4 Capability 5 (Click-to-Locate).

### 6.1 Outputs

1. **JSON payload** for the click-to-locate viewer (per §4 Capability 5).
2. **Word / PDF RFI report** with embedded screenshots and full audit trail.

### 6.2 Viewer payload schema

```json
{
  "sheet":       "S-01",
  "grid":        "TP104-B/2",
  "x_mm":        12400,
  "y_mm":        6800,
  "finding_id":  "FND-0042",
  "rule_summary": "Δw -50 mm, ΔEL +200 mm",
  "zoom_box":    { "x_min": 12000, "y_min": 6500,
                   "x_max": 12600, "y_max": 7100 },
  "highlight":   { "mech_poly_wkt": "...", "str_poly_wkt": "..." }
}
```

### 6.3 Per §4 Capability 5 sub-features

- Sheet + grid + X-Y metadata per finding ✓
- One-click zoom in the drawing viewer
- Highlighted overlay on the relevant geometry
- Side-by-side Mech vs Str view
- Annotation layer for reviewer comments
- Export to Word / PDF with embedded screenshots

### 6.4 Audit ledger

Every action is logged (§10):

```
TS · USER · IP · ACTION(target, before, after)
```

`upload · view · override · sign-off · export`

Drawings are immutable once sealed; audit reports are read-only.

### 6.5 Superimposed model file generation

**Gap closed:** §6.1–6.3 describe a JSON payload for an in-browser
viewer. That is not the same thing as a **superimposed drawing file**
an engineer can open in AutoCAD/BricsCAD and hand to a client — which
is explicitly one of the three deliverables in scope (alongside Mech
GA and Structural GA analysis). This subsection defines that file.

```
input:  entities_mech[] (post-L2, aligned via §3.6 transform),
        entities_str[], findings[] (L4 output)
output: superimposed.dxf  (and optionally .dwg via ODA reverse
        conversion)

Step 1. Create a new DXF document, one layer group per source
        "MECH-*"   ← copy every Mech layer, prefixed, original color
        "STR-*"    ← copy every Str layer, prefixed, original color
        preserves each discipline's original layer names nested under
        the prefix, so toggling "MECH-DUCTWORK" on/off still works

Step 2. Apply the registration transform from §3.6
        write Str entities into the new document using
        transform_str_to_mech, so both disciplines land in one
        coordinate space without altering either source file

Step 3. Draw finding overlays as real entities, not just an image
        for each finding in findings[]:
            HARD_CLASH   → closed HATCH polygon on layer "CLASH-RED",
                            solid fill, from the Shapely intersection
                            polygon (§5.3 Check 4)
            CLEARANCE    → dashed polyline offset on layer
                            "CLASH-AMBER" showing the required vs.
                            actual clearance zone
            PASS         → thin outline on layer "CLASH-GREEN"
                            (optional — many firms suppress passes to
                            reduce visual noise; make this a toggle)
            attach an XDATA block to each overlay entity carrying
            `finding_id`, so clicking the entity in AutoCAD/BricsCAD
            can round-trip back to the same finding in the web viewer

Step 4. Insert a title block / legend
        block "ADV-LEGEND" placed at a fixed sheet location: color
        key, generation timestamp, source revision IDs + SHA-256 of
        both inputs, so the overlay file is self-describing even if
        it's forwarded outside the platform

Step 5. Emit both formats
        write superimposed.dxf directly (ezdxf `writer.write()`)
        optionally invoke ODA File Converter in reverse (DXF → DWG)
        for firms whose review process requires native DWG

Step 6. Version the output like any other drawing
        the superimposed file gets its own row in the revision ledger
        (§1), `family_id` derived from both source family_ids, so
        re-running the check after a Rev B upload produces a new,
        traceable superimposed revision rather than overwriting
```

This keeps the "model" as an actual portable CAD artifact, while the
JSON viewer payload (§6.2) remains the fast, no-install way to browse
findings in-browser.

---

## 7. Standards library (per §12)

Each rule cites the standard it's enforcing against. Coverage:

| Family | Codes |
|---|---|
| Structural | ACI 318, AISC 360, IS 800, Eurocode 3 |
| Load & General | ASCE 7, IS 875, Eurocode 1 |
| Seismic | IBC (Ch 16, 18, 19), IS 1893 |
| Building Code | IBC, CBC, NFPA |

A rule like `position_check` carries `citation = "ASCE 7 §1.5.6"` so
every flag is engineering-defensible.

---

## 8. Security model (per §10)

| Concern | Implementation |
|---|---|
| Encryption at rest | AES-256 |
| Encryption in transit | TLS 1.3 |
| Audit | SOC 2 Type II |
| Deployment | VPC or full on-prem |
| Access control | RBAC: Engineer · Reviewer · Admin · Super Admin + SSO via SAML 2.0 + SCIM provisioning |
| **LLM inference** | **Self-hosted local — Ollama / vLLM / llama.cpp** |
| **Third-party API calls** | **None. Zero. Drawings never leave your infrastructure.** |
| Audit trail | Every upload / view / override / sign-off / export logged with TS, user, IP |
| Drawings | Immutable once sealed |

---

## 9. Use cases the backend must serve

Per §11:

### Use Case 1 — Mech GA ↔ Str GA

> *"Mech GA requires a 300×200 duct opening at TP104-B/2 elevation
> +13.150m. Str GA provides 250×200 at +13.350m. Both fail tolerance
> → flagged."*

Pipeline: L0 → L1 → L2 → L3 (×2: mech + str) → L4 (all 8 checks) → L5.

### Use Case 2 — Revision Comparison

> *"Upload Rev A and Rev C of the Structural GA. Get a structural
> diff: which beams moved, which openings changed, which supports
> were added or removed."*

Pipeline: L0 loads both revisions → L1 → L2 → L3 (each rev) →
L4 run between Mech-Rev-A vs Str-Rev-A, then Mech-Rev-A vs
Str-Rev-C → diff the two finding sets → L5 emits a delta report.

### Use Case 3 — Multi-Discipline Clash Overlay

> *"Upload Mech + Str + Plumbing + Fire Protection. Get a unified
> superimposed view with all clashes color-coded by severity."*

Pipeline: L0 → L1 → L2 → L3 (×N disciplines) → L4 run pairwise →
L5 emits unified superimposed view with overlay colours:
- Red = hard clash
- Amber = soft intrusion / clearance
- Green = pass

---

## 10. End-to-end data flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Engineer │ →  │ Upload  │ →  │ L0       │ →  │ L1       │ →  │ L2       │ →  │ L3       │
│ uploads  │    │ UI      │    │ SHA-256  │    │ ezdxf    │    │ regex +  │    │ local    │
│ mech.dwg │    │         │    │ ledger   │    │ walk     │    │ R-tree   │    │ LLM      │
│ str.dwg  │    │         │    │          │    │          │    │          │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                                            ↓
                                                                       ┌──────────┐
                                                                       │ canonical│
                                                                       │ schema   │
                                                                       └──────────┘
                                                                            ↓
                                                                       ┌──────────┐
                                                                       │ L4       │
                                                                       │ 8 checks │
                                                                       │ Shapely  │
                                                                       │ NumPy    │
                                                                       │ RapidFuzz│
                                                                       │ sBERT    │
                                                                       └──────────┘
                                                                            ↓
                                                                       ┌──────────┐
                                                                       │ findings │
                                                                       │ list     │
                                                                       └──────────┘
                                                                            ↓
                                                                       ┌──────────┐
                                                                       │ L5       │
                                                                       │ viewer   │
                                                                       │ JSON     │
                                                                       │ + RFI    │
                                                                       │ DOCX/PDF │
                                                                       └──────────┘
                                                                            ↓
                                                                       ┌──────────┐
                                                                       │ Reviewer │
                                                                       │ signs    │
                                                                       │ off      │
                                                                       └──────────┘
```

---

## 11. Algorithm choices — the non-obvious ones

Each choice below is motivated by a real failure mode we avoid.

| Choice | Avoids | Source |
|---|---|---|
| **DWG-native, not raster** | Loses layers, blocks, real-world units; can't run tolerances | §0, §3 |
| **ezdxf + ODA** | ODA's native SDK is C++ and not free for commercial use; pure-Python is faster to iterate | §3, §8 |
| **Shapely polygon intersection (not bounding boxes)** | Diagonal duct + beam has zero AABB overlap yet physically intersects | §4 Cap 4 |
| **Levenshtein + embeddings + grid proximity ensemble** | Levenshtein alone fails on `BM-203` vs `TP4BM203`; embeddings alone give `PIPE ≈ PIPELINE` false positives | §4 Cap 3 |
| **Local LLM for reading, deterministic math for checking** | Putting math behind an LLM gives non-reproducible findings; reading without an LLM can't handle firm-specific conventions | §6, §3 |
| **JSON-schema / GBNF grammar enforcement** | LLMs emit trailing commas, prose, wrong types without grammar-constrained decoding | §3 L3 tech |
| **SHA-256 of raw file** | Two engineers uploading the same DWG twice should not produce two separate baselines | §3 L0 |
| **`$INSUNITS` for unit detection** | Never have to guess scale from pixel length | §3 L2 |
| **Self-hosted LLM, no API** | Drawing data never leaves the network; satisfies AEC security requirements | §10, §15 FAQ #8 |
| **Swappable model orchestration** | Lock-in; can switch Qwen → Llama → DeepSeek → Mistral → Granite without code change | §6 table |

---

## 12. Why "agentic AI" specifically (per §6)

The brief draws a clear line between *agentic* and *trained ML*:

| Factor | Agentic AI (self-hosted LLM) | Trained ML Model |
|---|---|---|
| Labeled training data | None | Hundreds–thousands of drawings |
| Time to first version | Days–weeks | Weeks–months |
| **DWG accuracy** | **Exact (entities, layers, blocks, real-world mm)** | Lost (must rasterise first) |
| Style robustness | Any DWG style out of the box | Struggles until retrained |
| Math check determinism | Fully deterministic formulas | Confidence-scored predictions |
| Audit / compliance defensibility | Every finding = exact formula + number | Every finding = predicted box + score |
| **Data residency** | **100 % on-prem, zero third-party API** | Depends on hosting |
| Model swap-ability | Swappable (Qwen / Llama / DeepSeek / Mistral / Granite) | Locked to retraining cycle |
| Ongoing maintenance | Light — model swap or prompt tuning | Heavy — labelling + retraining loop |
| Team required | Software engineers | Engineers + ML team + labelling team |

> *"The core checks are exact rule-based math — distance, size, overlap,
> tolerance — not pattern recognition. Putting exact formulas behind a
> self-hosted LLM agent that handles reading and normalization gives
> you deterministic, audit-defensible findings and full data residency."*
> — §6 Recommendation

---

## 13. Targets (per §15 FAQ #10)

- **5–15 minutes** for a single drawing set, depending on size.
- Order-of-magnitude faster than manual review.
- Faster than Navisworks federation + clash for non-BIM projects.

---

## 14. Reference patterns the design copies

Per the brief's appendix (§A) the design explicitly references:

- **getstructured.ai** — blueprint motif, sheet+grid+element grounding, QA/QC Compliance Checks block, agent playground, *No confidence percentages* differentiator
- **InspectMind.ai** — text-driven trust, code citations, free first check
- **Nonlinear.build** — accordion features, integrations, dark hero
- **Stru AI** — 2D PDF focus, engineer credibility, codes (IBC, ASCE 7, ACI 318, AISC 360)

---

## 15. Test & validation strategy

**Gap closed:** the original spec never defines how correctness is
verified before a customer trusts a FAIL/PASS finding — a real risk
given that engineers will act on these flags. This is the missing
piece between "designed" and "safe to ship."

### 15.1 Golden dataset

```
Build a held-out set of drawing pairs with known, hand-verified
answers before any model swap or rule change ships:

  - ≥ 20 Mech/Str GA pairs spanning: clean match, missing opening,
    orphaned support, size mismatch, elevation mismatch, hard clash,
    clearance violation, and at least 2 pairs with intentionally
    inconsistent tagging conventions (to stress-test Check 1 fuzzy
    matching)
  - ≥ 3 pairs with non-standard grid labeling (to stress-test §3.5)
  - ≥ 2 pairs with an XREF dependency (to stress-test §2.6)
  - each pair's expected findings recorded as fixed JSON, reviewed and
    signed off by a licensed engineer, not just the dev team
```

### 15.2 Two independent test layers

```
Layer A — Rule engine unit tests (deterministic, no LLM in the loop)
  feed the 8 checks (§5.3) synthetic canonical-schema objects
  directly, bypassing L1–L3 entirely
  → these must be 100% reproducible; any change to §5.3 math requires
    all existing unit tests to still pass before merge

Layer B — End-to-end regression against the golden dataset
  run the full L0→L5 pipeline against every golden pair
  compare findings[] against the recorded expected set:
    - false negative (missed a real finding)  → blocks release,
      always, regardless of model swap justification
    - false positive (flagged a non-issue)    → tracked as a metric,
      triaged by severity, does not automatically block release
  re-run this suite on every LLM model swap (§4.5), every prompt
  change, and every rule-engine change — this is what makes "swappable
  model" (§11) safe in practice, not just possible in theory
```

### 15.3 Ongoing production signal

```
Reviewer overrides (§6.4 audit ledger) are a live accuracy signal:
  if a reviewer overrides the same finding type on the same rule
  above a threshold rate (e.g. > 15% override rate on CLEARANCE
  findings in a rolling 30-day window), open a review ticket — it
  usually means either a tolerance default is miscalibrated for that
  project type, or the matching/registration layer is systematically
  misfiring for a drawing convention not yet in the golden dataset
```

---

## 16. Current implementation status

| Component | Status | Evidence in repo |
|---|---|---|
| Marketing site | **Built** | `index.html` |
| Content brief | **Built** | `WEBSITE_CONTENT_BRIEF.md` |
| Test drawings (3 PDFs) | **Present** | `TP-104 MECH GA.pdf`, `TP-104 STR GA.pdf`, `superimposed.pdf` |
| L0 — revision ledger + file validation | **Designed, not coded** | §1 |
| L1 — DWG extraction + XREF resolution | **Designed, not coded** | §2 |
| L2 — grid registration + cross-drawing alignment | **Designed, not coded** | §3 |
| L3 — local LLM normalisation + chunking strategy | **Designed, not coded** | §4 |
| L4 — rule engine | **Designed, not coded** | §5 |
| L5 — viewer + reports + superimposed model file | **Designed, not coded** | §6 |
| Golden dataset + regression suite | **Not started** | §15 |

---

*End of document. Source-of-truth for backend design — references every algorithm
back to a specific section / line in `WEBSITE_CONTENT_BRIEF.md` or `index.html`.*
