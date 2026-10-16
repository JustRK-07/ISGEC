# Events — Append-Only Audit Log

> **Source:** `app/services/events.py` (280 LOC), `app/models/event.py`
> **Table:** `project_events`
> **Workstream:** 9 (per `BACKEND_ARCHITECTURE.md`)

Every meaningful state change in a project's lifecycle is recorded in an append-only event log. The log is **idempotent** (UNIQUE `dedupe_key`) so re-emitted events collapse into a single row, and the migration is **idempotent** (`ensure_event_table` is safe to call on every startup).

---

## 0. Why a separate event log?

The events table complements the `issues` table:
- **`issues`** = validation findings (with reconciliation semantics)
- **`project_events`** = lifecycle transitions ("upload started", "rules completed", "LLM failed")

This separation lets the audit trail survive project deletion (`project_events` rows are NOT auto-cascaded) and lets the UI show a chronological activity feed without polluting the issue stream.

---

## 1. Data model

```python
class ProjectEvent(Base):
    __tablename__ = "project_events"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_project_events_dedupe_key"),
        Index("ix_project_events_project_created", "project_id", "created_at"),
    )

    id:           Mapped[str]   = mapped_column(String, primary_key=True)
    project_id:   Mapped[str]   = mapped_column(String, nullable=False, index=True)
    category:     Mapped[str]   = mapped_column(String, nullable=False)
    code:         Mapped[str]   = mapped_column(String, nullable=False)
    tone:         Mapped[str]   = mapped_column(String, nullable=False, default="info")
    message:      Mapped[str]   = mapped_column(Text, nullable=False)
    payload_json: Mapped[str|None] = mapped_column(Text, nullable=True)
    created_at:   Mapped[int]   = mapped_column(BigInteger, nullable=False)
    dedupe_key:   Mapped[str]   = mapped_column(String, nullable=False)
```

### Enums

**`category`** (derived from `code` prefix):
| Prefix | Category |
|---|---|
| `upload.*` | `upload` |
| `parse.*` | `parse` |
| `rules.*` / `analyze.*` | `analyze` |
| `llm.*` / `ai.*` | `llm` |
| `issue.*` | `issue` |
| `revision.*` | `revision` |
| `system.*` (catch-all) | `system` |

**`tone`**:
- `info` — informational, neutral
- `ok` — success
- `warn` — recoverable issue (e.g. duplicate upload)
- `fail` — error (e.g. parse failure, LLM timeout)

---

## 2. Public API (`app/services/events.py`)

```python
def emit_event(
    db: Session,
    project_id: str,
    code: str,
    message: str,
    *,
    tone: str = "info",
    payload: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    created_at: int | None = None,
) -> ProjectEvent:
    """Insert a new event row. If ``dedupe_key`` matches an existing row,
    return that row instead of creating a duplicate.

    Caller is responsible for ``db.commit()`` — keeps the existing pattern
    where routers/services batch their writes.
    """

def list_events(
    db: Session,
    project_id: str,
    limit: int = DEFAULT_EVENTS_LIMIT,    # 200
) -> list[ProjectEvent]:
    """Return up to ``limit`` events for the project, newest first."""

def ensure_event_table(engine: Engine) -> None:
    """Create the ``project_events`` table + indexes if they do not exist.
    Idempotent migration. Safe to call on every startup.
    """

def aggregate_checks(issues: list) -> list[dict[str, Any]]:
    """Compute a CHECKS-shaped list (id, name, meta, state, count) from
    the issues that exist for the project. ``state`` is one of
    ``"ok" | "warn" | "fail"`` — derived from severities, not invented.
    """

def _event_to_dict(row: ProjectEvent) -> dict[str, Any]: ...
```

### Constants

```python
MAX_EVENTS_RETURNED = 500
DEFAULT_EVENTS_LIMIT = 200
_VALID_TONES = {"info", "ok", "warn", "fail"}
```

---

## 3. Idempotent insert (`emit_event`)

```python
def emit_event(db, project_id, code, message, *, tone="info", payload=None, dedupe_key=None, created_at=None):
    if not project_id: raise ValueError("project_id is required")
    if not code:       raise ValueError("code is required")
    if not message:    raise ValueError("message is required")

    if dedupe_key:
        existing = db.execute(
            select(ProjectEvent).where(ProjectEvent.dedupe_key == dedupe_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing   # ← idempotent: no duplicate row

    row = ProjectEvent(
        id=str(uuid.uuid4()),
        project_id=project_id,
        category=_derive_category(code),
        code=code,
        tone=_coerce_tone(tone),
        message=message,
        payload_json=json.dumps(payload, separators=(",", ":")) if payload else None,
        created_at=created_at if created_at is not None else _now_ms(),
        dedupe_key=dedupe_key or f"{project_id}:{code}:{uuid.uuid4()}",
    )
    db.add(row)
    db.flush()
    return row
```

### Caller pattern

```python
emit_event(db, project_id, "upload.started", "Project upload started.")
db.commit()   # ← caller commits
```

The service does NOT auto-commit. This matches the project's existing pattern where routers and services batch their writes for transaction efficiency.

---

## 4. Idempotent migration (`ensure_event_table`)

```python
def ensure_event_table(engine: Engine) -> None:
    insp = inspect(engine)
    if "project_events" in insp.get_table_names():
        return   # ← already exists, nothing to do
    from app.db import Base
    Base.metadata.create_all(bind=engine, tables=[ProjectEvent.__table__])
```

Called from `app/db.py:init_db()` on every FastAPI startup. Safe because it inspects first.

---

## 5. Event catalog

| `code` | Category | When | Tone | dedupe_key format |
|---|---|---|---|---|
| `upload.started` | upload | Project row inserted | info | `upload.started:{project_id}` |
| `upload.{discipline}` | upload | File persisted per discipline | ok | `upload.{discipline}:{sha256}` |
| `upload.complete` | upload | All files persisted | ok | `upload.complete:{project_id}` |
| `parse.ok` | parse | (Future) Parse result | ok | (per-file) |
| `analyze.started` | analyze | Phase 1 started | info | `analyze.started:{project_id}` |
| `rules.completed` | analyze | Phase 1 done | ok | `rules.completed:{project_id}` |
| `llm.started` | llm | Phase 2 LLM call began | info | `llm.started:{project_id}` |
| `llm.skipped` | llm | No LLM configured | info | `llm.skipped:{project_id}` |
| `llm.completed` | llm | LLM returned valid findings | ok | `llm.completed:{project_id}` |
| `llm.failed` | llm | Timeout or exception | fail | (same as completed; later emit overrides earlier) |
| `llm.timeout` | llm | (alias) 20s exceeded | fail | `llm.timeout:{project_id}` |
| `issue.{state}` | issue | User state transition | ok/info | `issue.{state}:{project_id}` |
| `revision.registered` | revision | New revision accepted | ok | `revision.registered:{revision_id}` |
| `revision.duplicate` | revision | SHA-256 already known | warn | `revision.duplicate:{sha256}` |
| `system.error` | system | Catch-all for failures | fail | `system.error.{phase}:{project_id}` |

### Emission examples

```python
# Upload lifecycle
emit_event(db, project_id, "upload.started", "Project upload started.",
           dedupe_key=f"upload.started:{project_id}", created_at=now)
emit_event(db, project_id, "upload.str", "Uploaded STR drawing ...",
           tone="ok", payload={"filename": "...", "sizeBytes": 3131396, "sha256": "..."},
           dedupe_key=f"upload.str:{sha256}")
emit_event(db, project_id, "upload.complete", "Drawing upload completed; analysis queued.",
           tone="ok", dedupe_key=f"upload.complete:{project_id}")

# Analyze lifecycle
emit_event(db, project_id, "analyze.started", "Deterministic QA/QC pipeline started.",
           dedupe_key=f"analyze.started:{project_id}")
emit_event(db, project_id, "rules.completed",
           f"Rule engine completed across {n} elements.",
           tone="ok", payload={"entityCount": n},
           dedupe_key=f"rules.completed:{project_id}")

# LLM lifecycle
emit_event(db, project_id, "llm.started", f"Calling LLM ({provider}) for enrichment.",
           dedupe_key=f"llm.started:{project_id}")
emit_event(db, project_id, "llm.completed", f"LLM enrichment produced {n} additional findings.",
           tone="ok", payload={"count": n}, dedupe_key=f"llm.completed:{project_id}")
emit_event(db, project_id, "llm.failed", f"LLM enrichment failed: {err}",
           tone="fail", payload={"count": n}, dedupe_key=f"llm.completed:{project_id}")

# Issue state transition
emit_event(db, issue.project_id, f"issue.{issue.state}",
           f"Issue {issue.code} marked {issue.state}.",
           tone="ok" if issue.state == "resolved" else "info",
           payload={"issueId": issue.id, "previousState": previous_state, "state": issue.state})
```

---

## 6. Listing events (`list_events`)

```python
def list_events(db, project_id, limit=DEFAULT_EVENTS_LIMIT):
    bounded = max(1, min(int(limit), MAX_EVENTS_RETURNED))  # hard-cap at 500
    return list(
        db.execute(
            select(ProjectEvent)
            .where(ProjectEvent.project_id == project_id)
            .order_by(ProjectEvent.created_at.desc(), ProjectEvent.id.desc())
            .limit(bounded)
        ).scalars()
    )
```

Sorted newest-first. Returns `list[ProjectEvent]` ORM rows — router converts via `_event_to_dict()`.

### `_event_to_dict`

```python
def _event_to_dict(row: ProjectEvent) -> dict:
    return {
        "id":        row.id,
        "projectId": row.project_id,
        "category":  row.category,
        "code":      row.code,
        "tone":      row.tone,
        "message":   row.message,
        "payload":   json.loads(row.payload_json) if row.payload_json else None,
        "createdAt": row.created_at,
    }
```

---

## 7. CHECKS aggregation (`aggregate_checks`)

A pure function that derives a CHECKS-shaped list from the existing `issues` rows — no separate counter table needed.

### `CHECK_CATALOG`

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

### `_CODE_TO_CHECK` (prefix mapping)

```python
_CODE_TO_CHECK = [
    ("FUZZY",     "fuzzy"),
    ("POS",       "pos"),
    ("SIZE",      "size"),
    ("CLASH",     "poly"),
    ("POLY",      "poly"),
    ("CLEAR",     "clear"),
    ("ELEV",      "elev"),
    ("OPEN-MISS", "req"),
    ("OPEN-ORPH", "orph"),
]
```

### Algorithm

```python
def aggregate_checks(issues: list) -> list[dict[str, Any]]:
    counts = {c["id"]: {"fail": 0, "warn": 0, "ok": 0} for c in CHECK_CATALOG}

    for it in issues:
        check_id = _code_to_check_id(it.code)
        if not check_id: continue
        sev = (it.severity or "").lower()
        if   sev == "high":           counts[check_id]["fail"] += 1
        elif sev in ("medium", "low"): counts[check_id]["warn"] += 1
        elif sev == "pass":           counts[check_id]["ok"]   += 1

    out = []
    for c in CHECK_CATALOG:
        b = counts[c["id"]]
        if   b["fail"] > 0: state, count = "fail", b["fail"]
        elif b["warn"] > 0: state, count = "warn", b["warn"]
        else:               state, count = "ok",   b["ok"]
        out.append({"id": c["id"], "name": c["name"], "meta": c["meta"],
                    "state": state, "count": count})
    return out
```

### Output shape

```json
[
  { "id": "fuzzy", "name": "Fuzzy ID match",       "meta": "...", "state": "ok",   "count": 0 },
  { "id": "pos",   "name": "Position tolerance",    "meta": "...", "state": "fail", "count": 3 },
  { "id": "size",  "name": "Size tolerance",        "meta": "...", "state": "warn", "count": 2 },
  { "id": "poly",  "name": "Polygon clash",         "meta": "...", "state": "fail", "count": 5 },
  { "id": "clear", "name": "Clearance zone",        "meta": "...", "state": "ok",   "count": 0 },
  { "id": "elev",  "name": "Elevation alignment",   "meta": "...", "state": "warn", "count": 1 },
  { "id": "req",   "name": "Required-not-missing",  "meta": "...", "state": "fail", "count": 2 },
  { "id": "orph",  "name": "Orphan-provided",       "meta": "...", "state": "warn", "count": 4 }
]
```

This is what powers the **CHECKS rail** in the workspace — a fixed list of 8 cards, each showing a name + state badge + count. Engineers scan the rail top-to-bottom to triage.

---

## 8. JSON returned by `GET /api/projects/{id}`

```json
{
  ...,
  "events": [
    {
      "id":        "uuid",
      "projectId": "uuid",
      "category":  "analyze",
      "code":      "rules.completed",
      "tone":      "ok",
      "message":   "Rule engine completed across 2242 elements.",
      "payload":   { "entityCount": 2242 },
      "createdAt": 1721073600000
    },
    ...
  ],
  "checks": [...]
}
```

---

## 9. Why dedupe keys are mandatory for state transitions

Without `dedupe_key`, retries (network blips, idempotent POSTs, app restart mid-analyze) would create duplicate rows. The UNIQUE constraint on `dedupe_key` makes the operation safe:

```python
# User clicks "Resolve" twice in 200ms
emit_event(..., "issue.resolved", ..., dedupe_key="issue.resolved:abc123")
# Second emit returns the original row instead of inserting a duplicate
```

This means the UI can safely re-poll and the audit log won't grow spurious entries.

---

## 10. Testing (`tests/test_events.py`, 393 LOC)

Covers:
- `emit_event` with and without `dedupe_key`
- Idempotent insert (same key → same row)
- Tone coercion (`"OK"` → `"ok"`, invalid tones → `"info"`)
- `list_events` ordering (newest first), limit cap at 500
- `ensure_event_table` idempotency (call twice → no error)
- `aggregate_checks` derivation:
  - all `pass` → state `"ok"`, count = N passes
  - any `high` → state `"fail"`
  - `medium`/`low` without `high` → state `"warn"`
- Category derivation from code prefix
- `_event_to_dict` roundtrip

---

*For data model: [`DATA_MODEL.md`](./DATA_MODEL.md). For analysis pipeline: [`ARCHITECTURE.md`](./ARCHITECTURE.md).*