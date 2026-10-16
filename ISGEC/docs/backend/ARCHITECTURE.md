# Architecture — ISGEC Backend

> **Source spec:** [`BACKEND_ARCHITECTURE.md`](../reference/BACKEND_ARCHITECTURE.md) in this repo's `docs/reference/` folder.
> **Audience:** Backend engineers, ML engineers, QA leads.
> **Status:** Implemented (Phases 0–9 of the conversion plan complete).

---

## 0. One-paragraph summary

ADV reads a Mechanical General Arrangement (GA) drawing and a Structural GA drawing of the same floor and validates that every support, opening, and penetration required by Mech is actually provided by Str — with the correct size, at the correct position, at the correct elevation, with the correct clearance, and without colliding with a structural member. Every finding is grounded to a **sheet**, a **grid intersection**, an **element**, and an **exact formula**. The pipeline runs 100% on-prem behind a self-hosted local LLM when `LLM_PROVIDER=ollama` — no third-party API is ever called.

```
   L0            L1            L2            L3              L4
INGESTION →   DWG → DXF   →  GRID / COORD → NORMALISATION →  RULES    →  L5 REPORT
+ REVISION   ENTITY         REGISTRATION    (LOCAL LLM)    (DETERMINISTIC)
LEDGER        EXTRACT
```

**Core principle:** *reading* (L1–L3) is probabilistic. *checking* (L4) is exact. Findings are deterministic, not confidence-scored.

---

## 1. Layer 0 — Ingestion & Revision Lock

**Files:** `routers/revisions.py`, `services/revisions.py`, `models/revision.py`

### Purpose

Stop validating against a stale baseline. Engineers routinely review against Rev A when Rev C has already been issued; the ledger makes the revision chain explicit.

### Algorithm

```
input:  uploaded DWG/DXF file (binary blob) + filename
output: revision ledger entry (or 409 Conflict)

Step 1. Compute SHA-256 of the raw bytes
        digest = sha256(file_bytes).hexdigest()    # 64 hex chars

Step 2. Lookup digest in revision ledger
        if digest known:
            → reject upload (409 Conflict: "DUPLICATE_REVISION",
                            returns existing revision_id)
        else:
            → proceed

Step 3. Detect supersession
        normalize_family_id(filename) → e.g. "tp-104 str ga"
        if a sibling with same family_id exists and the new file differs:
            → increment revision_letter (A → B → C)
            → set supersedes = previous_revision_id

Step 4. Persist + emit event
        INSERT INTO revisions (...)
        emit_event("revision.registered", tone="ok")
```

### Data contract

```json
{
  "id":              "uuid-v4",
  "family_id":       "tp-104 str ga",
  "revision_letter": "C",
  "supersedes":      "<prev_revision_id or null>",
  "sha256":          "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "filename":        "TP-104 STR GA.dwg",
  "size_bytes":      3131396,
  "uploaded_by":     "user-uuid",
  "uploaded_at":     1721073600000,
  "project_id":      "project-uuid"
}
```

### Tech

- **SHA-256**: `hashlib.sha256(data).hexdigest()` from stdlib (`app/utils/hashing.py`)
- **Revision ledger**: SQLite (WAL mode) — `app/models/revision.py`
- **Why Git-like**: revisions form a DAG via `supersedes` → enables `git log`-style diff

Full reference: **[REVISIONS.md](./REVISIONS.md)**.

---

## 2. Layer 1 — DWG → DXF & Entity Extraction

**Files:** `services/parse.py` (950 LOC), `services/dwg_convert.py` (125 LOC), `services/events.py`

### Purpose

Read what the engineer actually drafted — not a flattened raster. DWG already stores real-world mm, layer names, block definitions, and line types. All of this is **lost** when the drawing is exported to PDF.

### Algorithm

```
input:  file.dwg  | file.dxf  | file.ifc  | file.pdf
output: ParsedDrawing { entities[], layers[], text_labels[], header{}, parse_meta{} }

Step 1. Convert if needed
        if extension == ".dwg":
            subprocess.run("dwg2dxf -y -o <out.dxf> <file.dwg>")
            (libredwg binary; supports up to R2018)
        if extension == ".dxf":
            skip conversion
        if extension == ".ifc" | ".pdf":
            stub return (ParsedDrawing.ok=False)

Step 2. Parse DXF with custom tolerant parser (parse_file → _parse_dxf)
        Pass 0: recover from desync (libredwg emits unescaped newlines)
        Pass 0b: find $INSUNITS in HEADER section
        Pass 1: walk BLOCKS + ENTITIES sections, classify entity types
        Pass 2: expand INSERTs in modelspace (capped at 50,000 primitives)

Step 3. Read $INSUNITS header
        header_units = code-9 $INSUNITS / code-70
        INSUNITS_TO_MM = {0:1, 1:25.4, 2:304.8, 4:1, 5:10, 6:1000}
        # 6 = millimetres, 4 = millimetres too, 1 = inches, …

Step 4. Emit ParsedDrawing
        entity_count, layers (top 60 by count),
        text_labels (first 200), header, parse_meta
```

### Geometry entity types captured

```
LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, ELLIPSE, SPLINE,
TEXT, MTEXT, INSERT, ATTRIB, ATTDEF, HATCH, SOLID, 3DFACE,
DIMENSION, LEADER, POINT
```

### DWG version support

```
AC1012 → R13
AC1014 → R14
AC1015 → R2000
AC1018 → R2004
AC1021 → R2007
AC1024 → R2010    ← TP-104 reference
AC1027 → R2013
AC1032 → R2018
```

### INSERT expansion safety

Revit 3D exports represent every primitive inside a `Part-*` block; expanding INSERTs is what makes the geometry renderable. Capped at `max_insert_expansion = 50,000` (real TP-104 drawings emit 15-25k primitives, so 50k is a generous safety margin). When the cap is hit, `parse_meta.truncatedInserts = True`.

### Tech

- **ezdxf** — pure-Python DXF parser (used for non-DWG paths + DWG reading for older R13/R14/R2000)
- **GNU libredwg** — DWG → DXF subprocess wrapper (`app/services/dwg_convert.py`), supports up to R2018
- **Custom tolerant parser** — ports `parseDxf` from `app/services/parse.py` with desync-recovery logic

---

## 3. Layer 2 — Grid & Coordinate Registration

**Files:** `services/analyze.py` (run_phase_1), `services/parse.py`

### Purpose

Put every entity on a **shared coordinate frame** so distance formulas between Mech and Str drawings are meaningful. Without grid registration, "the Mech opening at grid B/2" and "the Str opening at grid B/2" are just two unrelated points.

### Algorithm

```
input:  ParsedDrawing (Layer 1 output), $INSUNITS
output: entities[] with discipline, sheet, x_mm, y_mm, w_mm, h_mm, rotation, meta{}

Step 1. dxf_to_entities(parsed, discipline, project_id, uuid_factory)
        Walks every parsed entity, classifies by layer convention:
          kind in {"opening","duct","pipe"}     → kind="opening"
          kind in {"beam","column","brace"}     → kind="beam"
          kind = "equipment"                    → kind="equipment"

Step 2. Convert all coordinates to mm
        if header_units != 4 (mm):
            factor = INSUNITS_TO_MM[header_units]
            coords = scale(coords, factor)

Step 3. Persist entities
        DELETE FROM entities WHERE project_id = ?
        INSERT each (id, project_id, discipline, sheet, kind, label, x_mm, ...)
```

### Why "no scale detection"

DWG's `$INSUNITS` header already declares real-world units (typically 4 or 6 = mm for AEC). Unlike PDF/image input, we never have to guess "this line is 5 px long, so it's X mm at this scale". This is the central technical reason DWG-native is preferred over raster.

---

## 4. Layer 3 — Semantic Normalization (Agent Layer)

**Files:** `services/normalize.py` (236 LOC), `services/llm_gemini.py`, `services/llm_ollama.py`

### Purpose

Collapse firm-specific naming chaos into **one canonical schema**. Different firms call the same physical beam different things (`F11WE`, `TP4BM101`, `BM-203-ISMC150`, `M-OP-203`); downstream rules must not have to learn every firm's convention.

### Canonical schema (output of this layer)

```python
class Support(BaseModel):
    id: str
    type: Literal["restraint", "anchor", "guide", "saddle"]
    grid: str | None
    x_mm: float
    y_mm: float
    load_kg: float | None = None
    fluid: str | None = None

class Opening(BaseModel):
    id: str
    service: Literal["duct", "pipe", "cable-tray", "sleeve", "trench"]
    grid: str | None
    x: float
    y: float
    w: float
    h: float
    elevation: float | None = None

class Member(BaseModel):
    id: str
    type: Literal["beam", "column", "brace", "truss", "joist"]
    section: str | None
    grid_start: str | None
    grid_end: str | None
    profile: dict | None

class Tolerance(BaseModel):
    project_default_mm: float = 25.0
    opening_size_mm: float = 10.0
    position_mm: float = 25.0
    elevation_mm: float = 50.0
    clearance_mm: float = 50.0
```

### Algorithm

```
input:  entities[] (Layer 2 output), file_meta{}
output: NormalizedDrawing (canonical schema)

Step 1. Chunk entities into element-sized groups
        group by layer convention + spatial proximity + entity type

Step 2. Build LLM prompt (capped to first 200 entities)
        system: "You are ADV — an AEC drawing normalizer..."
        user:   discipline, file_meta, entities[]

Step 3. Local LLM inference
        configured: llm_gemini (hosted) or llm_ollama (zero-API)
        both clients: response_schema = NormalizedDrawing.model_json_schema()
                      response_mime_type = "application/json"

Step 4. Validate
        Pydantic v2 .model_validate() on the response
        required fields present, types correct
        reject + retry once, then fall back to heuristic

Step 5. Heuristic fallback
        maps parser kind → canonical schema:
          duct/pipe/opening → Opening
          beam/column       → Member
          equipment         → Support (default: restraint)
```

### Why a local LLM (not a hosted API)

Per the security brief and FAQ #8:

> **No drawing data ever leaves your infrastructure.** All LLM inference runs locally on your hardware — Ollama, vLLM, or llama.cpp serving an open-weight model. No tokens, no rate limits, no API keys, no telemetry to third parties. Models are swappable (Qwen, Llama, DeepSeek, Mistral, Granite).

Full client documentation: **[LLM.md](./LLM.md)**.

---

## 5. Layer 4 — Rule Engine (Deterministic)

**Files:** `services/rules.py` (624 LOC)

### Purpose

Run **exact math** against the canonical schema. This is where findings are born. Eight checks.

### Tech stack

- **Python** (orchestration)
- **Shapely** — 2D geometry (intersection, distance, polygons)
- **NumPy** — linear algebra, vectorisation
- **RapidFuzz** — Levenshtein / fuzzy string distance
- **scipy** (optional) — `linear_sum_assignment` for Hungarian matching

### The 8 checks

| # | Function | Category | Severity | Code prefix |
|---|---|---|---|---|
| 1 | `check_fuzzy_id` | tag | low | TAG-VERIFY |
| 2 | `check_position` | position | high/medium | POS-DELTA |
| 3 | `check_size` | size | high/medium | SIZE-DELTA |
| 4 | `check_polygon_clash` | clash | high | HARD-CLASH |
| 5 | `check_clearance` | clearance | medium | CLEAR-VIOL |
| 6 | `check_elevation` | elevation | high/medium | ELEV-DELTA |
| 7 | `check_missing` | missing | high | OPEN-MISS |
| 8 | `check_orphan` | orphan | medium | OPEN-ORPH |

Full per-check reference: **[RULES.md](./RULES.md)**.

### Orchestrator

```python
def run_checks(
    entities: list[dict],
    gemini_issues: list[dict] | None = None,
    fuzzy_threshold: float = 0.55,
    position_tol_mm: float = 25.0,
    size_w_tol_mm: float = 10.0,
    size_h_tol_mm: float = 10.0,
    clearance_mm: float = 50.0,
    elevation_tol_mm: float = 50.0,
    clash_min_area_mm2: float = 1.0,
) -> list[dict]:
    """Run all deterministic checks. Returns a list of issue dicts."""
```

### Finding record (L4 output)

```json
{
  "id":         "uuid",
  "severity":   "high" | "medium" | "low" | "pass",
  "category":   "clash" | "missing" | "orphan" | ...,
  "code":       "HARD-CLASH" | "POS-DELTA" | ...,
  "title":      "Hard clash between \"OP-203\" and \"P11\"",
  "evidence":   "Polygon intersection area = 12450 mm². ...",
  "sheet":      "S-01",
  "grid":       "TP104-B/2",
  "mech_ref":   "OP-203",
  "str_ref":    "P11",
  "formula":    "area(m ∩ s) = 12450 mm²",
  "result_json": { "intersect_area_mm2": 12450, "wkt": "POLYGON(...)" },
  "state":      "open" | "resolved" | "dismissed" | "obsolete",
  "assigned":   "engineer-uuid" | null,
  "created_at": 1721073600000
}
```

**No confidence percentages.** Every number is traceable to a formula.

---

## 6. Layer 5 — Reporting & Sign-off

**Files:** `routers/projects.py` (GET /:id), `routers/issues.py` (PATCH), `services/events.py`

### Outputs

1. **JSON payload** for the click-to-locate workspace (per §4 Capability 5)
2. **Append-only event log** (`project_events` table)
3. **Issue ledger** with reconciliation semantics (state survives re-analysis)
4. **CHECKS aggregation** — 8 named checks with derived (state, count)

### Viewer payload (GET /api/projects/{id})

```json
{
  "id": "uuid",
  "label": "TP-104 Conveyor",
  "shortName": "TP-104",
  "rev": "C",
  "kind": "Str + Mech",
  "status": "ready",
  "files": [{ "discipline": "str", "parseStatus": "ok", ... }],
  "issues": [{ "code": "HARD-CLASH", ... }],
  "entities": { "str": [...], "mech": [...] },
  "sheets": ["0001", "M-01"],
  "analysis": {
    "status": "done",
    "phase": "rules+llm",
    "llmStatus": "done",
    "llmError": null,
    "summary": { "pass": 5, "warn": 2, "fail": 3 },
    "issueCount": 10,
    "startedAt": 1721073600000,
    "finishedAt": 1721073610000
  },
  "checks": [
    { "id": "fuzzy", "name": "Fuzzy ID match", "state": "ok", "count": 0 },
    { "id": "pos", "name": "Position tolerance", "state": "fail", "count": 3 },
    ...
  ],
  "events": [{ "category": "...", "code": "...", "message": "...", "tone": "ok" }],
  "summary": { "pass": 5, "warn": 2, "fail": 3 }
}
```

### Audit ledger

Every action emits an event:

```
TS · CATEGORY · CODE · TONE · MESSAGE · PAYLOAD
```

| Category | When emitted |
|---|---|
| `upload` | Upload started/completed, per-discipline file persisted |
| `parse` | File parse lifecycle |
| `analyze` | Rules pipeline started/completed |
| `llm` | LLM pass started/skipped/timed-out/failed/completed |
| `issue` | Issue state transition |
| `revision` | Revision registered/duplicate detected |
| `system` | Catch-all (errors, migrations) |

Full event log reference: **[EVENTS.md](./EVENTS.md)**.

---

## 7. Two-phase analyzer (`services/analyze.py`)

```
HTTP POST /api/projects
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 1 (sync, fast, in-request)                            │
│                                                             │
│   1. Validate file extensions                               │
│   2. Insert Project row (status="processing")               │
│   3. Emit "upload.started" event                             │
│   4. For each file (str, mech, extra):                      │
│        a. Validate size ≤ max_upload_bytes                   │
│        b. persist_upload() → on-disk + SHA-256              │
│        c. Insert File row                                    │
│        d. Emit "upload.{discipline}" event with dedupe_key  │
│   5. Emit "upload.complete" event                           │
│   6. db.commit()                                                 │
│   7. _background_run_analysis(project_id) — daemon thread   │
│   8. Return 201 with project metadata + files summary        │
└─────────────────────────────────────────────────────────────┘
       │
       │ (background thread)
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 1 (continued) — run_phase_1(db, project_id)          │
│                                                             │
│   1. Set project.status = "processing"                       │
│   2. Emit "analyze.started" event                           │
│   3. Parse STR + MECH via parse.parse_file()                │
│   4. Persist parse_meta on File rows                         │
│   5. parse.dxf_to_entities() → all entities[]                │
│   6. Persist entities (DELETE + INSERT)                      │
│   7. Emit "rules.completed" event with entityCount          │
│   8. rules.run_checks(entities) → findings[]                │
│   9. _persist_issues_reconciling() (preserves state)        │
│   10. Set project.status = "ready"                          │
│   11. Update _STATE[project_id] = AnalysisState(done)       │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2 (async, slow, fire-and-forget)                      │
│                                                             │
│   1. Check _llm_available()                                  │
│      → if no provider configured: state.skip, return         │
│   2. Emit "llm.started" event                               │
│   3. asyncio.wait_for(                                       │
│        llm.analyse_drawings(...) or           │
│        llm_ollama.analyse_drawings(...),    │
│        timeout=settings.gemini_timeout_sec  │
│     )                                                        │
│   4. On TimeoutError: emit AI-TIMEOUT finding               │
│   5. On Exception: emit AI-UNAVAIL finding                  │
│   6. On success: persist LLM issues via reconciliation     │
│   7. Emit "llm.completed" or "llm.failed" event             │
│   8. Recompute summary across all issues                    │
│   9. Update _STATE: llmStatus=done/failed                   │
└─────────────────────────────────────────────────────────────┘
```

### Reconciliation semantics (`_persist_issues_reconciling`)

```
Fingerprint: (code, sheet, str_ref, mech_ref)

For each new finding:
    if (code, sheet, str_ref, mech_ref) matches an existing Issue:
        → UPDATE severity, category, title, evidence, grid, formula, result_json
        → preserve state, assigned, created_at
    else:
        → INSERT new Issue with state="open"

For each existing open Issue not matched by any new finding:
    → UPDATE state = "obsolete"  (preserves audit trail)
```

User state (`state`, `assigned`) survives re-analysis. Resolved/dismissed issues are never silently deleted.

---

## 8. End-to-end data flow

```
Engineer        Upload UI          L0          L1          L2          L3              L4              L5
  │                 │             SHA-256      │           │          LLM            rules           │
  │ POST /projects  │             ledger       │           │       (Gemini/         (8 checks)       │
  │ (multipart)     │                          │           │        Ollama)                          │
  ▼                 ▼                          ▼           ▼            ▼              ▼               ▼
┌─────────┐    ┌─────────┐                ┌────────┐ ┌─────────┐ ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Project │ →  │ routers │ → emit       │    │parse  │ │ canonical│ │ findings │   │ viewer   │
│ upload  │    │projects │    events    │    │entities│ │ schema   │ │ list     │ → │ JSON     │ → Reviewer
│ (str+    │ +───────────────────────────────────────────────────────────────+    +──────────┘   signs off
│  mech)   │    │         │              │    │        │ │          │ │          │                    │
└─────────┘    └─────────┘              └────────┘ └─────────┘ └──────────┘   └──────────┘                    │
                                                                                            ┌──────────┐     │
                                                                                            │ audit    │ ◄───┘
                                                                                            │ events   │
                                                                                            └──────────┘
```

---

## 9. Security model

| Concern | Implementation |
|---|---|
| Encryption at rest | AES-256 (filesystem-level; SQLite WAL files) |
| Encryption in transit | TLS 1.3 (deployed behind reverse proxy) |
| Audit | SOC 2 Type II trail via `project_events` (append-only) |
| Deployment | VPC or full on-prem |
| Access control | RBAC at reverse proxy layer; backend trusts upstream auth |
| **LLM inference** | **Self-hosted local — Ollama / vLLM / llama.cpp** |
| **Third-party API calls** | **None. Zero. Drawings never leave your infrastructure.** when `LLM_PROVIDER=ollama` |
| Audit trail | Every upload / view / override / sign-off / export logged with TS, code, payload |
| Drawings | Immutable once sealed (project cascade + storage cleanup) |

---

## 10. Algorithm choices — the non-obvious ones

Each choice below is motivated by a real failure mode we avoid.

| Choice | Avoids |
|---|---|
| **DWG-native, not raster** | Loses layers, blocks, real-world units; can't run tolerances |
| **ezdxf + libredwg** | ODA's native SDK is C++ and not free for commercial use; pure-Python is faster to iterate |
| **Shapely polygon intersection (not bounding boxes)** | Diagonal duct + beam has zero AABB overlap yet physically intersects |
| **Levenshtein + grid proximity ensemble** | Levenshtein alone fails on `BM-203` vs `TP4BM203`; sentence-transformers not loaded by default |
| **Local LLM for reading, deterministic math for checking** | Putting math behind an LLM gives non-reproducible findings |
| **JSON-schema / response_schema enforcement** | LLMs emit trailing commas, prose, wrong types without grammar-constrained decoding |
| **SHA-256 of raw file** | Two engineers uploading the same DWG twice should not produce two separate baselines |
| **`$INSUNITS` for unit detection** | Never have to guess scale from pixel length |
| **Self-hosted LLM, no API** | Drawing data never leaves the network; satisfies AEC security requirements |
| **Swappable model orchestration** | Lock-in; can swap Gemini → Ollama without code change |
| **Reconciliation-friendly issue persistence** | User state (resolved/dismissed/assigned) survives re-analysis |
| **Append-only event log** | Audit trail is preserved across deletes, deletes don't drop context |
| **Dedupe via UNIQUE constraint** | Idempotent event emission; same key → same row |

---

## 11. Source-of-truth alignment

Every algorithm in this codebase references a specific section of:

- **`BACKEND_ARCHITECTURE.md`** — pipeline + algorithms
- **`WEBSITE_CONTENT_BRIEF.md`** — product positioning + capabilities

When the design docs and the code disagree, **the design docs win** — file an issue and update the code.

---

*End of architecture document. For data-model specifics: [`DATA_MODEL.md`](./DATA_MODEL.md). For REST endpoints: [`API.md`](./API.md).*