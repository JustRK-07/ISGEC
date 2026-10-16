# Data Model — ISGEC Backend

> **Source:** `app/models/` (6 SQLAlchemy ORM classes) + `app/schemas/` (Pydantic v2 request/response models).
> **Storage:** SQLite (WAL mode + foreign keys ON) at `./data/isgec.db`.

This document describes every table, every column, every relationship, and every JSON contract — both at the ORM level and at the API boundary.

---

## 0. Schema overview

```
┌──────────────┐         ┌─────────────┐          ┌──────────────┐
│   projects   │ 1     * │    files    │          │  revisions   │
│              │─────────│             │          │              │
└──────┬───────┘         └─────────────┘          └──────┬───────┘
       │ 1                                                │
       │                                                  │ self-ref
       │ *                                                ▼
       │                                            ┌───────────┐
       │                                            │  (chain)  │
       │                                            └───────────┘
       │ 1
       ▼ *
┌──────────────┐         ┌──────────────┐         ┌─────────────────┐
│   issues     │         │  entities    │         │ project_events  │
│              │         │              │         │  (append-only)  │
└──────────────┘         └──────────────┘         └─────────────────┘
```

| Table | Purpose |
|---|---|
| `projects` | Top-level project container (one per drawing pair) |
| `files` | Uploaded DWG/DXF/IFC/PDF files belonging to a project |
| `entities` | Extracted drawing primitives (lines, openings, beams, etc.) |
| `issues` | Validation findings — matches, mismatches, clashes, orphans |
| `revisions` | Git-like DAG of uploaded DWGs (Layer 0 ledger) |
| `project_events` | Append-only audit/activity log |

---

## 1. `projects` table

### Schema

```python
class Project(Base):
    __tablename__ = "projects"

    id:           Mapped[str]   = mapped_column(String, primary_key=True)
    label:        Mapped[str]   = mapped_column(String, nullable=False)
    short_name:   Mapped[str]   = mapped_column(String, nullable=False)
    rev:          Mapped[str|None] = mapped_column(String, nullable=True)
    kind:         Mapped[str]   = mapped_column(String, nullable=False, default="Str + Mech")
    status:       Mapped[str]   = mapped_column(String, nullable=False)  # processing|ready|error
    created_at:   Mapped[int]   = mapped_column(BigInteger, nullable=False)  # epoch ms
    last_opened:  Mapped[int]   = mapped_column(BigInteger, nullable=False)  # epoch ms

    files:  Mapped[list[File]]  = relationship("File",  back_populates="project",
                                                cascade="all, delete-orphan")
    issues: Mapped[list[Issue]] = relationship("Issue", back_populates="project",
                                                cascade="all, delete-orphan")
```

### Status transitions

```
[created, processing]  ─── parse OK, rules done ───→  [ready]
                                        │
                                        └── parse/rule exception ──→ [error]
```

### Properties

```python
@property
def created_at_dt(self) -> datetime:
    return datetime.fromtimestamp(self.created_at / 1000)

@property
def last_opened_dt(self) -> datetime:
    return datetime.fromtimestamp(self.last_opened / 1000)
```

### JSON contract (GET /api/projects)

```json
{
  "id":         "uuid",
  "label":      "TP-104 Conveyor",
  "shortName":  "TP-104",
  "rev":        "C" | null,
  "kind":       "Str + Mech",
  "status":     "processing" | "ready" | "error",
  "createdAt":  1721073600000,
  "lastOpened": 1721073610000,
  "summary":    { "pass": 5, "warn": 2, "fail": 3 }
}
```

---

## 2. `files` table

### Schema

```python
class File(Base):
    __tablename__ = "files"

    id:           Mapped[str]   = mapped_column(String, primary_key=True)
    project_id:   Mapped[str]   = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"),
                                                nullable=False, index=True)
    discipline:   Mapped[str]   = mapped_column(String, nullable=False)  # 'str' | 'mech' | 'extra'
    filename:     Mapped[str]   = mapped_column(String, nullable=False)
    format:       Mapped[str]   = mapped_column(String, nullable=False)  # 'dwg' | 'dxf' | 'ifc' | 'pdf'
    size_bytes:   Mapped[int]   = mapped_column(BigInteger, nullable=False)
    sha256:       Mapped[str]   = mapped_column(String, nullable=False)
    stored_path:  Mapped[str]   = mapped_column(String, nullable=False)
    parse_meta:   Mapped[str|None] = mapped_column(Text, nullable=True)  # JSON
    parse_status: Mapped[str]   = mapped_column(String, nullable=False, default="pending")
    parse_error:  Mapped[str|None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="files")
```

### Enums

**`discipline`**:
- `str` — Structural GA
- `mech` — Mechanical GA
- `extra` — Optional reference drawing (superimposed, etc.)
- `rev` — Revision upload (separate from `files` table; tracked in `revisions`)

**`format`**:
- `dwg` — AutoCAD binary
- `dxf` — AutoCAD text format
- `ifc` — BIM model (stub parser)
- `pdf` — Reference only (stub parser)

**`parse_status`**:
- `pending` — not parsed yet
- `ok` — full parse
- `failed` — parse failed (see `parse_error`)
- `partial` — parsed but with caveats
- `skipped` — non-geometry format

### JSON contract

```json
{
  "id":           "uuid",
  "discipline":   "str" | "mech" | "extra",
  "filename":     "TP-104 STR GA.dwg",
  "format":       "dwg",
  "sizeBytes":    3131396,
  "sha256":       "9f86d0...",
  "parseStatus":  "ok",
  "parseMeta":    { ... see parse_meta section ... }
}
```

### `parse_meta` JSON shape

```json
{
  "kind":             "dwg" | "dxf",
  "parser":           "custom",
  "entityCount":      2242,
  "layers":           [{ "name": "GRID-A", "count": 12 }, ...],  // top 60
  "headerUnits":      4 | 6,                          // $INSUNITS code
  "textLabels":       [{ "layer": "GRID-A", "text": "TP104-A" }, ...],  // first 200
  "header":           { "$INSUNITS": 4 },
  "parseMeta":        { ... },
  "magicBytes":       "AC1024",
  "dwgVersion":       "R2010",
  "layerCandidates":  ["GRID-A", "OPENINGS", "P11"],
  "elevations":       ["+13.150m", "+13.350m"],
  "pipes":            ["P11", "P12"],
  "truncatedInserts": true | false,
  "blockDefs":        17
}
```

### Storage layout (on disk)

```
uploads/<project_id>/
├── str.dwg
├── mech.dxf
└── extra.pdf  (optional)
```

`stored_path` is stored **relative to `DATA_DIR`** when `upload_dir` is inside `data_dir`; otherwise absolute. The relative pattern keeps uploads portable.

---

## 3. `entities` table

### Schema

```python
class Entity(Base):
    __tablename__ = "entities"

    id:           Mapped[str]   = mapped_column(String, primary_key=True)
    project_id:   Mapped[str]   = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"),
                                                nullable=False, index=True)
    discipline:   Mapped[str]   = mapped_column(String, nullable=False)  # 'str' | 'mech'
    sheet:        Mapped[str]   = mapped_column(String, nullable=False, default="default")
    kind:         Mapped[str]   = mapped_column(String, nullable=False)
    label:        Mapped[str|None] = mapped_column(String, nullable=True)
    x_mm:         Mapped[float|None] = mapped_column(Float, nullable=True)
    y_mm:         Mapped[float|None] = mapped_column(Float, nullable=True)
    w_mm:         Mapped[float|None] = mapped_column(Float, nullable=True)
    h_mm:         Mapped[float|None] = mapped_column(Float, nullable=True)
    rotation:     Mapped[float|None] = mapped_column(Float, nullable=True)
    meta:         Mapped[str|None] = mapped_column(Text, nullable=True)  # JSON
```

### `kind` values

| `kind` | Source layer | Used by |
|---|---|---|
| `opening` / `duct` / `pipe` | "OPENINGS" / "P11" / "DUCT" | Rules checks 1, 2, 3, 4, 5, 6, 7, 8 |
| `beam` / `brace` | "P11" / "BEAMS" | Rules checks 1, 4, 5 |
| `column` | "COLS" | Rules checks 1, 4, 5 |
| `equipment` | "EQUIPMENT" / "MECH" | Rules checks 1, 4, 5 |
| `grid` | "GRID-A" etc. | Render-only (not part of rules) |
| `text-label` | TEXT entities with grid convention | Grid registration |

### JSON contract

```json
{
  "id":          "uuid",
  "discipline":  "str" | "mech",
  "sheet":       "0001",
  "kind":        "opening" | "duct" | "pipe" | "beam" | "column" | "equipment",
  "label":       "OP-203" | null,
  "x_mm":        12000.0,
  "y_mm":        6800.0,
  "w_mm":        300.0,
  "h_mm":        200.0,
  "rotation":    0.0,
  "meta":        {
    "layer":      "P11",
    "elevation":  "+13.150m",
    "vertices":   [[12000, 6500], [12300, 6500], ...]
  }
}
```

`meta` is the free-form JSON blob that captures everything the parser didn't promote to a top-level column. Common fields:
- `layer` — DXF layer name
- `elevation` / `elevation_m` — extracted T.O.S. value
- `tos` — top-of-steel annotation
- `vertices` — LWPOLYLINE / HATCH paths
- `blockName` — owning block (for INSERTs inside blocks)
- `type` — original DXF type code (LINE, LWPOLYLINE, …)

---

## 4. `issues` table

### Schema

```python
class Issue(Base):
    __tablename__ = "issues"

    id:           Mapped[str]   = mapped_column(String, primary_key=True)
    project_id:   Mapped[str]   = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"),
                                                nullable=False, index=True)
    severity:     Mapped[str]   = mapped_column(String, nullable=False)  # high|medium|low|pass
    category:     Mapped[str]   = mapped_column(String, nullable=False)
    code:         Mapped[str]   = mapped_column(String, nullable=False)
    title:        Mapped[str]   = mapped_column(String, nullable=False)
    evidence:     Mapped[str|None] = mapped_column(Text, nullable=True)
    sheet:        Mapped[str|None] = mapped_column(String, nullable=True)
    grid:         Mapped[str|None] = mapped_column(String, nullable=True)
    mech_ref:     Mapped[str|None] = mapped_column(String, nullable=True)
    str_ref:      Mapped[str|None] = mapped_column(String, nullable=True)
    formula:      Mapped[str|None] = mapped_column(Text, nullable=True)
    result_json:  Mapped[str|None] = mapped_column(Text, nullable=True)  # JSON
    state:        Mapped[str]   = mapped_column(String, nullable=False, default="open")
    assigned:     Mapped[str|None] = mapped_column(String, nullable=True)
    created_at:   Mapped[int]   = mapped_column(BigInteger, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="issues")
```

### Enums

**`severity`**:
- `high` — hard clash, missing primary support, off-by-tolerance (>100mm)
- `medium` — clearance violation, orphan opening, off-by-tolerance (25-100mm)
- `low` — cosmetic / tagging / convention mismatch
- `pass` — representative all-good baseline

**`state`**:
- `open` — new, needs review
- `resolved` — fixed by reviewer (DRAFT.raised → user confirmed)
- `dismissed` — false positive, won't fix
- `obsolete` — no longer produced by the latest analysis run (preserved for audit)

**`category`** (from rules + LLM):
- `clash` (HARD-CLASH)
- `position` (POS-DELTA)
- `size` (SIZE-DELTA)
- `clearance` (CLEAR-VIOL)
- `elevation` (ELEV-DELTA)
- `tag` (TAG-VERIFY)
- `missing` (OPEN-MISS)
- `orphan` (OPEN-ORPH)
- `general` (LLM-emitted, catch-all)

### JSON contract

```json
{
  "id":         "uuid",
  "severity":   "high",
  "category":   "clash",
  "code":       "HARD-CLASH",
  "title":      "Hard clash between \"OP-203\" and \"P11\"",
  "evidence":   "Polygon intersection area = 12450 mm². ...",
  "sheet":      "0001",
  "grid":       "TP104-B/2",
  "mech_ref":   "OP-203",
  "str_ref":    "P11",
  "formula":    "area(m ∩ s) = 12450 mm²",
  "result": {
    "intersect_area_mm2": 12450,
    "wkt": "POLYGON ((12000 6500, 12300 6500, 12300 6700, 12000 6700, 12000 6500))"
  },
  "state":      "open",
  "assigned":   null,
  "created_at": 1721073600000
}
```

### `result_json` shapes per check

| Check | `result_json` |
|---|---|
| TAG-VERIFY | `{ "score": 0.65, "band": "verify" }` |
| POS-DELTA | `{ "delta_mm": 45, "dx_mm": 30, "dy_mm": -33 }` |
| SIZE-DELTA | `{ "dw_mm": -50, "dh_mm": 0 }` |
| HARD-CLASH | `{ "intersect_area_mm2": 12450, "wkt": "POLYGON(...)" }` |
| CLEAR-VIOL | `{ "distance_mm": 20, "required_mm": 50 }` |
| ELEV-DELTA | `{ "mech_elevation_m": 13.150, "str_elevation_m": 13.350, "delta_mm": 200 }` |
| OPEN-MISS | (none) |
| OPEN-ORPH | (none) |

### Issue fingerprint (reconciliation key)

```
fingerprint = (code, sheet, str_ref, mech_ref)
```

When a re-run produces the same fingerprint, the existing row's `severity/category/title/evidence/grid/formula/result_json` are updated but `state/assigned/created_at` are preserved.

---

## 5. `revisions` table

### Schema

```python
class Revision(Base):
    __tablename__ = "revisions"

    id:              Mapped[str]   = mapped_column(String, primary_key=True)
    family_id:       Mapped[str]   = mapped_column(String, nullable=False, index=True)
    revision_letter: Mapped[str]   = mapped_column(String, nullable=False)
    supersedes:      Mapped[str|None] = mapped_column(ForeignKey("revisions.id", ondelete="SET NULL"),
                                                     nullable=True)
    sha256:          Mapped[str]   = mapped_column(String, nullable=False, unique=True)
    filename:        Mapped[str]   = mapped_column(String, nullable=False)
    size_bytes:      Mapped[int]   = mapped_column(BigInteger, nullable=False)
    uploaded_by:     Mapped[str|None] = mapped_column(String, nullable=True)
    uploaded_at:     Mapped[int]   = mapped_column(BigInteger, nullable=False)
    project_id:      Mapped[str]   = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"),
                                                   nullable=False, index=True)
```

### Why `sha256` is UNIQUE

A given SHA-256 may only exist once — re-uploading the same bytes returns the existing revision (no duplicates). The 409 Conflict response includes the existing `revision_id` so the client can de-duplicate.

### JSON contract (POST /api/projects/{id}/revisions)

```json
{
  "id":              "uuid",
  "family_id":       "tp-104 str ga",
  "revision_letter": "C",
  "supersedes":      "<prev-revision-uuid>" | null,
  "sha256":          "9f86d0...",
  "filename":        "TP-104 STR GA.dwg",
  "size_bytes":      3131396,
  "uploaded_by":     "user-uuid" | null,
  "uploaded_at":     1721073600000
}
```

### Family ID normalization

`revisions.normalize_family_id(filename)` strips:
- File extension
- Common revision markers: `Rev A`, `rev 2`, `_rev3`, `-R4`, `(C)`

Examples:

| Filename | `family_id` |
|---|---|
| `TP-104 STR GA.dwg` | `tp-104 str ga` |
| `TP-104 STR GA - Rev B.dwg` | `tp-104 str ga` |
| `plan_rev2.DXF` | `plan` |
| `TP-104 STR GA rev C.dwg` | `tp-104 str ga` |

Full reference: **[REVISIONS.md](./REVISIONS.md)**.

---

## 6. `project_events` table (append-only)

### Schema

```python
class ProjectEvent(Base):
    __tablename__ = "project_events"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_project_events_dedupe_key"),
        Index("ix_project_events_project_created", "project_id", "created_at"),
    )

    id:          Mapped[str]   = mapped_column(String, primary_key=True)
    project_id:  Mapped[str]   = mapped_column(String, nullable=False, index=True)
    category:    Mapped[str]   = mapped_column(String, nullable=False)
    code:        Mapped[str]   = mapped_column(String, nullable=False)
    tone:        Mapped[str]   = mapped_column(String, nullable=False, default="info")
    message:     Mapped[str]   = mapped_column(Text, nullable=False)
    payload_json:Mapped[str|None] = mapped_column(Text, nullable=True)  # JSON
    created_at:  Mapped[int]   = mapped_column(BigInteger, nullable=False)  # epoch ms
    dedupe_key:  Mapped[str]   = mapped_column(String, nullable=False)
```

### Enums

**`category`** (derived from `code` prefix):
- `upload` (e.g. `upload.complete`, `upload.str`, `upload.mech`)
- `parse`
- `analyze` / `rules`
- `llm` / `ai`
- `issue`
- `revision`
- `system` (catch-all)

**`tone`**:
- `info` — informational
- `ok` — success
- `warn` — recoverable issue (e.g. duplicate upload)
- `fail` — error

### JSON contract

```json
{
  "id":        "uuid",
  "projectId": "uuid",
  "category":  "upload",
  "code":      "upload.complete",
  "tone":      "ok",
  "message":   "Drawing upload completed; analysis queued.",
  "payload":   {
    "filename": "TP-104 STR GA.dwg",
    "sizeBytes": 3131396,
    "sha256":   "9f86d0..."
  },
  "createdAt": 1721073600000
}
```

### Dedup key format

```
{uuid}:{code}:{uuid}            (default, auto-generated)
upload.{discipline}:{sha256}    (per-file dedupe)
upload.complete:{project_id}     (one-per-project)
analyze.started:{project_id}     (one-per-project)
rules.completed:{project_id}
llm.started:{project_id}
llm.completed:{project_id}       (any-replay collapses)
llm.skipped:{project_id}
revision.registered:{revision_id}
revision.duplicate:{sha256}
issue.{state}:{project_id}      (user state transitions)
system.error.rules:{project_id}
```

Full event log reference: **[EVENTS.md](./EVENTS.md)**.

---

## 7. `CHECK_CATALOG` (derived, not a table)

This is not stored in the DB — it's computed on the fly by `aggregate_checks(issues)`:

```python
CHECK_CATALOG = [
    {"id": "fuzzy", "name": "Fuzzy ID match",       "meta": "Levenshtein + sentence-transformer + grid proximity"},
    {"id": "pos",   "name": "Position tolerance",    "meta": "Euclidean · default ±25 mm"},
    {"id": "size",  "name": "Size tolerance",        "meta": "Per-axis · default ±25 mm"},
    {"id": "poly",  "name": "Polygon clash",         "meta": "Shapely polygon intersection"},
    {"id": "clear", "name": "Clearance zone",        "meta": "Min. distance threshold per service type"},
    {"id": "elev",  "name": "Elevation alignment",   "meta": "T.O.S. drift · default ±50 mm"},
    {"id": "req",   "name": "Required-not-missing",  "meta": "Required element not present on partner sheet"},
    {"id": "orph",  "name": "Orphan-provided",       "meta": "Provided element not required"},
]
```

The `state` for each check is derived from the severity counts:
- any `high` → `fail`
- any `medium`/`low` → `warn`
- otherwise → `ok`

The `count` is the number of issues at the **highest non-ok severity**.

---

## 8. Pydantic schemas (request/response boundary)

| Schema | Used by |
|---|---|
| `ProjectCreate` | `POST /api/projects` multipart fields |
| `ProjectSummary` | `GET /api/projects` list response |
| `ProjectOut` | `POST /api/projects` create response |
| `ProjectDetail` | `GET /api/projects/{id}` full detail |
| `FileSummary` | Per-discipline metadata in `POST` response |
| `FileOut` | Full file row in `GET` detail |
| `IssueOut` | Issue row in `GET` detail |
| `IssuePatch` | Body for `PATCH /api/issues/{id}` |
| `AnalysisState` | `GET /api/projects/{id}/analysis` |

All schemas use `ConfigDict(from_attributes=True)` to serialize from ORM instances. Camelcase aliases map snake_case DB columns to the JSON the frontend expects.

### Camelcase mapping examples

```python
# In model:          In JSON:
created_at     →     createdAt
last_opened    →     lastOpened
size_bytes     →     sizeBytes
parse_status   →     parseStatus
parse_meta     →     parseMeta
result_json    →     result
```

---

## 9. Cascade behaviour

```
Project deletion
  └─→ CASCADE all files (ON DELETE CASCADE on FK)
  └─→ CASCADE all issues (ON DELETE CASCADE on FK)
  └─→ CASCADE all entities (ON DELETE CASCADE on FK)
  └─→ CASCADE all revisions (ON DELETE CASCADE on FK)
  └─→ CASCADE all project_events (no FK, but cleaned up by app logic)
  └─→ remove_project_uploads(project_id)  # shutil.rmtree on uploads/<id>/
```

`project_events` rows are NOT auto-cascaded (no FK on `project_id`) — they survive project deletion to preserve the audit trail.

`revisions.supersedes` is `ON DELETE SET NULL` — deleting a revision doesn't cascade-delete the revisions that point at it.

---

## 10. SQLite pragmas (applied on every connection)

```sql
PRAGMA journal_mode = WAL;   -- better write throughput, concurrent reads
PRAGMA foreign_keys = ON;     -- enforce CASCADE / SET NULL
```

Configured in `app/db.py:engine` via a SQLAlchemy event listener.

---

*For query pattern→[API.md](./API.md). For analysis pipeline: [ARCHITECTURE.md](./ARCHITECTURE.md).*