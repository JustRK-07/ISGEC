# Revisions — Layer 0 Ingestion & Revision Lock

> **Source:** `app/services/revisions.py` (129 LOC), `app/models/revision.py`, `app/routers/revisions.py` (130 LOC)
> **Spec:** `BACKEND_ARCHITECTURE.md §1` (Layer 0 — Ingestion & Revision Lock)

The revision ledger is a **Git-like DAG** of every uploaded DWG. Two rules:

1. A given **SHA-256 may only exist once** — re-uploading the same bytes returns the existing revision (no duplicates).
2. When a new file with the **same `family_id`** is uploaded and differs from the previous revision, the new one **increments the `revision_letter`** (A → B → C) and points `supersedes` at its predecessor.

---

## 0. Why this matters

Stop validating against a stale baseline. Engineers routinely review against Rev A when Rev C has already been issued; the ledger makes the revision chain explicit.

---

## 1. Data model

```python
class Revision(Base):
    __tablename__ = "revisions"

    id:              Mapped[str]   = mapped_column(String, primary_key=True)
    family_id:       Mapped[str]   = mapped_column(String, nullable=False, index=True)
    revision_letter: Mapped[str]   = mapped_column(String, nullable=False)
    supersedes:      Mapped[str|None] = mapped_column(
        ForeignKey("revisions.id", ondelete="SET NULL"), nullable=True
    )
    sha256:          Mapped[str]   = mapped_column(String, nullable=False, unique=True)
    filename:        Mapped[str]   = mapped_column(String, nullable=False)
    size_bytes:      Mapped[int]   = mapped_column(BigInteger, nullable=False)
    uploaded_by:     Mapped[str|None] = mapped_column(String, nullable=True)
    uploaded_at:     Mapped[int]   = mapped_column(BigInteger, nullable=False)
    project_id:      Mapped[str]   = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
```

### Indexes / constraints

- `family_id` — indexed for fast `find_by_family` queries
- `sha256` — **UNIQUE** — enforces the idempotent dedupe at the storage layer
- `supersedes` — `ON DELETE SET NULL` (deleting a revision doesn't cascade-delete the chain)
- `project_id` — indexed; cascades on project delete

---

## 2. Public API (`app/services/revisions.py`)

```python
class DuplicateRevision(Exception):
    """Raised when an uploaded file's SHA-256 already exists in the ledger."""
    revision_id: str   # ← the existing revision the duplicate would clash with

def find_by_sha(db: Session, sha256: str) -> Revision | None: ...
def find_by_family(db: Session, family_id: str) -> list[Revision]: ...

def normalize_family_id(name: str) -> str:
    """Strip extension + lower-case a family id.

    Examples:
        'TP-104 STR GA.dwg'           → 'tp-104 str ga'
        'TP-104 STR GA - Rev B.dwg'   → 'tp-104 str ga'
        'plan_rev2.DXF'               → 'plan'
        'TP-104 STR GA rev C.dwg'     → 'tp-104 str ga'
    """

def register_revision(
    db: Session,
    *,
    family_id: str,
    sha256: str,
    filename: str,
    size_bytes: int,
    project_id: str,
    uploaded_by: str | None = None,
) -> Revision:
    """Idempotent insert. Raises DuplicateRevision if SHA-256 already known."""
```

---

## 3. Algorithm — `register_revision`

```python
def register_revision(db, *, family_id, sha256, filename, size_bytes, project_id, uploaded_by=None):
    # Step 1. SHA-256 dedupe (idempotent)
    existing = find_by_sha(db, sha256)
    if existing:
        raise DuplicateRevision(existing.id)

    # Step 2. Compute next revision letter for this family
    previous_letter = _latest_letter_for_family(db, family_id)
    new_letter = _next_letter(previous_letter or "")

    # Step 3. Find the latest revision in this family (for supersedes pointer)
    previous = db.execute(
        select(Revision)
        .where(Revision.family_id == family_id)
        .order_by(Revision.uploaded_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Step 4. Insert
    rev = Revision(
        id=str(uuid.uuid4()),
        family_id=family_id,
        revision_letter=new_letter,
        supersedes=previous.id if previous else None,
        sha256=sha256,
        filename=filename,
        size_bytes=size_bytes,
        uploaded_by=uploaded_by,
        uploaded_at=int(time.time() * 1000),
        project_id=project_id,
    )
    db.add(rev); db.commit(); db.refresh(rev)
    return rev
```

### Letter increment

```python
def _next_letter(current: str) -> str:
    """A → B → … → Z. Wraps Z → A (rarely hit in practice)."""
    if not current or current not in string.ascii_uppercase:
        return "A"
    idx = string.ascii_uppercase.index(current)
    return string.ascii_uppercase[(idx + 1) % 26]
```

---

## 4. Family ID normalization

```python
def normalize_family_id(name: str) -> str:
    base = re.sub(r"\.[A-Za-z0-9]+$", "", name)              # strip extension
    base = re.sub(r"[\s_\-]*r?ev[\s_\-]*[a-z0-9]+", " ", base, flags=re.I)  # 'Rev A', 'rev 2'
    base = re.sub(r"[\s_\-]*r\d+", " ", base, flags=re.I)                     # 'R4'
    base = re.sub(r"\([a-z0-9]+\)", " ", base, flags=re.I)                    # '(C)'
    base = re.sub(r"\s+", " ", base).strip()
    return base.lower() or "untitled"
```

### Examples

| Filename | `family_id` |
|---|---|
| `TP-104 STR GA.dwg` | `tp-104 str ga` |
| `TP-104 STR GA - Rev B.dwg` | `tp-104 str ga` |
| `plan_rev2.DXF` | `plan` |
| `TP-104 STR GA rev C.dwg` | `tp-104 str ga` |

The family_id is a **logical grouping**; `revision_letter` differentiates revisions within it. The normalization strips common revision markers so renames like "Rev B" / "rev2" don't accidentally start a new family.

---

## 5. REST endpoints (`app/routers/revisions.py`)

### `POST /api/projects/{project_id}/revisions`

Upload a new revision of a project file. Same bytes → 409 Conflict with the existing `revision_id`.

**Request**: `multipart/form-data`
| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | file | yes | The new revision DWG/DXF |
| `uploaded_by` | string | no | Optional user identifier |

**Flow**:
1. Read uploaded file bytes
2. `persist_upload(bytes, project_id, "rev", filename)` → `StoredFile { sha256, size_bytes, format }`
3. `normalize_family_id(filename)` → `family_id`
4. Call `register_revision(db, ...)`
   - On `DuplicateRevision`: emit `revision.duplicate` event, return 409
   - On success: emit `revision.registered` event, return 201
5. Also insert a row into `files` table (`discipline="extra"`, `parse_status="pending"`) — the revision is tracked alongside the project's primary files

**Response 201**:
```json
{
  "id":              "uuid",
  "family_id":       "tp-104 str ga",
  "revision_letter": "B",
  "supersedes":      "<prev-revision-uuid>" | null,
  "sha256":          "9f86d0...",
  "filename":        "TP-104 STR GA rev B.dwg",
  "size_bytes":      3145728,
  "uploaded_by":     "engineer@firm.com" | null,
  "uploaded_at":     1721073610000
}
```

**Response 409** (duplicate SHA-256):
```json
{
  "detail": {
    "error":       "File already ingested",
    "code":        "DUPLICATE_REVISION",
    "revision_id": "<existing-revision-uuid>"
  }
}
```

---

### `GET /api/projects/{project_id}/revisions`

List all revisions for a project.

**Response 200**:
```json
[
  {
    "id":              "uuid",
    "family_id":       "tp-104 str ga",
    "revision_letter": "A",
    "supersedes":      null,
    "sha256":          "9f86d0...",
    "filename":        "TP-104 STR GA.dwg",
    "size_bytes":      3131396,
    "uploaded_at":     1721073600000
  },
  ...
]
```

Sorted by `uploaded_at ASC` (insertion order = revision chain order).

---

## 6. Family chain in action

```
TP-104 STR GA.dwg        →  family_id="tp-104 str ga", letter=A, supersedes=null
TP-104 STR GA Rev B.dwg    →  family_id="tp-104 str ga", letter=B, supersedes=A
TP-104 STR GA rev C.dwg    →  family_id="tp-104 str ga", letter=C, supersedes=B
TP-104 STR GA Rev B.dwg (re-upload, same bytes)
                          →  409 DUPLICATE_REVISION, returns existing B's id
```

---

## 7. Event emission

| Event | When | Tone |
|---|---|---|
| `revision.registered` | New revision accepted | `ok` |
| `revision.duplicate` | SHA-256 already known | `warn` |

### Dedupe keys

```python
emit_event(
    db, project_id,
    "revision.registered",
    f"Revision {rev.revision_letter} registered for {file.filename}.",
    tone="ok",
    payload={"filename": file.filename, "revisionId": rev.id, "letter": rev.revision_letter},
    dedupe_key=f"revision.registered:{rev.id}",
)

emit_event(
    db, project_id,
    "revision.duplicate",
    f"Duplicate revision ignored: {file.filename}.",
    tone="warn",
    payload={"filename": file.filename, "revisionId": e.revision_id},
    dedupe_key=f"revision.duplicate:{stored.sha256}",  # ← one per sha
)
```

---

## 8. Edge cases

### Different files with same filename but different bytes

```
TP-104 STR GA.dwg  (3,131,396 bytes)          →  letter=A
TP-104 STR GA.dwg  (3,145,728 bytes, edited)  →  letter=B (different SHA-256)
```

The SHA-256 differs → new revision accepted. Filename alone doesn't trigger dedupe.

### Different filenames with same bytes

```
TP-104 STR GA.dwg        (sha=abc123)
TP-104 STR.dwg           (sha=abc123)  →  409 (same SHA, different filename)
```

Hash content, not filename.

### Re-uploading after deleting the project

Project delete cascades `revisions` (FK CASCADE). The next upload creates a fresh `family_id` chain.

### Cross-project SHA collisions

Two engineers uploading the same DWG to two different projects each get their own revision row. SHA uniqueness is **scoped to the global table**, not to project_id. This is intentional — it means if Engineer B re-uploads Engineer A's drawing to their own project, they get the same SHA → 409 with the existing revision_id (which belongs to A's project). The frontend can use this to dedupe across projects.

---

## 9. Testing

Tests live in `tests/test_revisions.py` (221 LOC). Covers:

- `find_by_sha` / `find_by_family` lookups
- `normalize_family_id` for various filename patterns (Rev, rev, R, (C), underscored, hyphenated)
- `register_revision` happy path (sequential A → B → C)
- Duplicate SHA-256 → `DuplicateRevision` exception
- `_next_letter` with wrap-around (Z → A)
- Cross-family isolation (same SHA, different family_id, both accepted)
- Router integration: 201 on first upload, 409 on duplicate, 201 on different bytes

---

## 10. Why Git-like

Revisions form a DAG via `supersedes`. Future work could enable:
- `git log`-style diff between any two revisions
- "Show me what changed between Rev A and Rev C" via entity comparison
- Pre-baseline validation (warn when validating against an outdated chain)

Currently, the ledger just records the chain — diff functionality is out of scope for v1.

---

*For the full pipeline: [`ARCHITECTURE.md`](./ARCHITECTURE.md). For event emission: [`EVENTS.md`](./EVENTS.md).*