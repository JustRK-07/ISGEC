# Services — ISGEC Backend

> **Source:** `app/services/` — 9 business-logic modules, ~3,160 LOC total.
> Services contain everything that *isn't* HTTP routing, ORM models, or config.

| Service | LOC | Purpose |
|---|---:|---|
| `parse.py` | 950 | DXF/DWG/IFC/PDF parser — extracts entities |
| `rules.py` | 624 | All 8 validation checks |
| `analyze.py` | 515 | Two-phase orchestrator (parse → rules → LLM) |
| `events.py` | 280 | Append-only event log + check aggregation |
| `normalize.py` | 236 | Layer 3 canonical schema (LLM normalization) |
| `llm_gemini.py` | 190 | Google Gemini client |
| `dwg_convert.py` | 125 | libredwg subprocess wrapper |
| `llm_ollama.py` | 111 | Self-hosted Ollama client (zero-API) |
| `revisions.py` | 129 | Layer 0 revision ledger |

---

## 1. `parse.py` — DXF/DWG/IFC/PDF parser (950 LOC)

The biggest service file. Ports `parseDxf` from the `app/services/parse.py` with desync-recovery logic.

### Public API

```python
def parse_file(
    file_path: str | Path,
    original_name: str | None = None,
    max_primitives: int = 50_000,
) -> ParsedDrawing: ...

def parse_dxf(buf: bytes, name: str, max_primitives: int = 50_000) -> ParsedDrawing: ...
def parse_dwg(buf: bytes, name: str, file_path: str, max_primitives: int = 50_000) -> ParsedDrawing: ...
def parse_ifc(buf: bytes, name: str) -> ParsedDrawing: ...
def parse_pdf_stub(name: str) -> ParsedDrawing: ...

def units_to_mm(ins_units: int | None) -> float: ...
```

### `ParsedDrawing` dataclass

```python
@dataclass
class ParsedDrawing:
    ok: bool
    kind: str                              # 'dxf' | 'dwg' | 'ifc' | 'pdf'
    entity_count: int = 0
    entities: list[dict] = field(default_factory=list)
    layers: list[dict] = field(default_factory=list)        # [{ name, count }, ...] (top 60)
    text_labels: list[dict] = field(default_factory=list)   # [{ layer, text }, ...] (first 200)
    header: dict = field(default_factory=dict)
    parse_meta: dict = field(default_factory=dict)
    parse_status: str = "ok"
    error: str | None = None
```

### Constants

```python
INSUNITS_TO_MM = { 0:1, 1:25.4, 2:304.8, 4:1, 5:10, 6:1000 }

_GEOMETRY_ENTITY_TYPES = frozenset({
    "LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE",
    "TEXT", "MTEXT", "INSERT", "ATTRIB", "ATTDEF", "HATCH", "SOLID", "3DFACE",
    "DIMENSION", "LEADER", "POINT"
})

DWG_VERSIONS = {
    "AC1012": "R13", "AC1014": "R14", "AC1015": "R2000",
    "AC1018": "R2004", "AC1021": "R2007", "AC1024": "R2010",
    "AC1027": "R2013", "AC1032": "R2018",
}

VALID_GROUP_MAX = 1071
```

### Internal: `_parse_dxf`

3-pass tolerant parser:

1. **Pass 0** — recover from desync (libredwg emits unescaped newlines inside MTEXT)
2. **Pass 0b** — find `$INSUNITS` in the HEADER section
3. **Pass 1** — walk BLOCKS + ENTITIES, classify entities by type, capture block definitions
4. **Pass 2** — `_expand_inserts(entities, blocks, max_primitives=50_000)` — turns Revit-style 3D exports into renderable 2D geometry

### Public: `dxf_to_entities`

```python
def dxf_to_entities(
    parsed: ParsedDrawing,
    discipline: str,
    project_id: str,
    uuid_factory: Callable[[], str],
) -> list[dict]:
    """Convert a ParsedDrawing into entity rows for the entities table."""
```

Returns dicts matching the [`Entity`](./DATA_MODEL.md#entities-table) schema, with `id` from `uuid_factory()`, `project_id`, `discipline`, `sheet`, `kind`, `label`, `x_mm`, `y_mm`, `w_mm`, `h_mm`, `rotation`, `meta` (JSON string).

---

## 2. `rules.py` — All 8 deterministic checks (624 LOC)

The second-biggest service. Implements every check from `BACKEND_ARCHITECTURE §5.3`.

### Public API

```python
@dataclass
class Finding:
    severity: str    # 'high' | 'medium' | 'low' | 'pass'
    category: str    # 'clash' | 'missing' | 'orphan' | 'clearance' | 'elevation' | 'size' | 'position' | 'tag' | 'general'
    code: str
    title: str
    evidence: str | None = None
    sheet: str | None = None
    grid: str | None = None
    mech_ref: str | None = None
    str_ref: str | None = None
    formula: str | None = None
    result: dict | None = None

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
) -> list[dict]: ...

# Per-check functions (also public):
def check_missing(entities, threshold=0.55) -> list[Finding]: ...
def check_orphan(entities, matched_str_ids) -> list[Finding]: ...
def check_fuzzy_id(entities, threshold=0.55) -> list[Finding]: ...
def fuzzy_match_pairs(mech_list, str_list, threshold=0.55, grid_scale_mm=1000.0) -> list[tuple]: ...
def check_position(mech, str_, tol_mm=25.0) -> Finding | None: ...
def check_size(mech, str_, w_tol_mm=10.0, h_tol_mm=10.0) -> Finding | None: ...
def check_polygon_clash(entities, min_intersect_area_mm2=1.0) -> list[Finding]: ...
def check_clearance(entities, min_clear_mm=50.0) -> list[Finding]: ...
def check_elevation(entities, tol_mm=50.0) -> list[Finding]: ...

def simple_similarity(a: str, b: str) -> float: ...
```

### Lazy heavy imports

```python
try:
    from rapidfuzz import fuzz as _rf_fuzz; _HAS_RAPIDFUZZ = True
except ImportError: _HAS_RAPIDFUZZ = False

try:
    from shapely.geometry import Polygon as _Polygon
    from shapely.strtree import STRtree as _STRtree
    _HAS_SHAPELY = True
except ImportError: _HAS_SHAPELY = False

try:
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    _HAS_SCIPY = True
except ImportError: _HAS_SCIPY = False
```

Tests work without the heavy libs; production uses them.

### Check 1 (Fuzzy) — score formula

```
score = 0.45 * lev + 0.40 * cos + 0.15 * prox
```

Where:
- `lev` = `rapidfuzz.fuzz.ratio(a, b) / 100` (or `simple_similarity` fallback)
- `cos` = 1.0 (placeholder; sentence-transformers not loaded by default)
- `prox` = `1.0 / (1.0 + grid_dist / grid_scale_mm)` (grid_scale_mm = 1000)

**Bands**:
- `pass` — score ≥ 0.80 (auto-accepted, silent)
- `verify` — 0.55 ≤ score < 0.80 (TAG-VERIFY finding)
- `manual` — score < 0.55 (not matched)

**Assignment**: Hungarian (`scipy.optimize.linear_sum_assignment`) when available; greedy best-first fallback otherwise.

### Helper: `simple_similarity(a, b)`

Jaccard similarity on 3-grams:

```python
def grams(s): return {s[i:i+3] for i in range(len(s) - 2)}
inter = len(grams(a) & grams(b))
union = len(grams(a) | grams(b))
return inter / union if union else 0.0
```

### Helper: `_entity_polygon(entity)`

Converts a `{x_mm, y_mm, w_mm, h_mm}` dict into an axis-aligned Shapely Polygon (centroid + half-extents).

### Helper: `_entity_elevation_m(entity)`

Tries `meta.elevation`, `meta.elevation_m`, `meta.tos`, `entity.elevation`, `entity.elevation_m`, then scans `label` for regex `([+-]?\d{1,2}\.\d{2,3})\s*m`. Returns `float` (e.g. `13.150`) or `None`.

Full per-check documentation: **[RULES.md](./RULES.md)**.

---

## 3. `analyze.py` — Two-phase orchestrator (515 LOC)

### Public API

```python
@dataclass
class AnalysisState:
    status: str = "idle"          # 'idle' | 'running' | 'done' | 'error'
    phase: str | None = None      # 'rules' | 'llm'
    started_at: int | None = None
    finished_at: int | None = None
    error: str | None = None
    summary: dict[str, int] | None = None
    issue_count: int | None = None
    llm_status: str | None = None # 'pending' | 'running' | 'done' | 'failed' | 'skipped'
    llm_error: str | None = None

def get_analysis_state(project_id: str) -> AnalysisState: ...

async def run_analysis(db: Session, project_id: str) -> dict: ...
async def run_phase_1(db: Session, project_id: str) -> dict: ...
async def run_phase_2(db: Session, project_id: str) -> None: ...
```

### In-process state map

```python
_STATE: dict[str, AnalysisState] = {}
```

**Caveat**: This is a single-process map. When the FastAPI app moves to multi-worker, replace with Redis.

### Two-phase pipeline

```
run_analysis(db, project_id)
    │
    ├─ await run_phase_1(db, project_id)       # sync, fast
    │   ├─ set project.status = "processing"
    │   ├─ emit_event("analyze.started")
    │   ├─ parse.parse_file() for str + mech
    │   ├─ parse.dxf_to_entities() → all_entities
    │   ├─ _persist_entities() [DELETE + INSERT]
    │   ├─ emit_event("rules.completed", entityCount)
    │   ├─ rules.run_checks(entities) → findings
    │   ├─ _persist_issues_reconciling(findings)
    │   └─ set project.status = "ready"
    │
    └─ _schedule_phase_2(db, project_id)       # fire-and-forget
        │
        ├─ if running loop: asyncio.create_task(run_phase_2(...))
        └─ else: daemon thread → asyncio.run(run_phase_2(...))
                │
                ├─ emit_event("llm.started")
                ├─ asyncio.wait_for(llm.analyse_drawings(...), 20s)
                │   ├─ on TimeoutError → emit AI-TIMEOUT finding
                │   ├─ on Exception    → emit AI-UNAVAIL finding
                │   └─ on success      → reconcile LLM findings
                ├─ emit_event("llm.completed" or "llm.failed")
                └─ update state.llmStatus, summary, issue_count
```

### Reconciliation semantics

```python
def _persist_issues_reconciling(db, project_id, findings, *, source="deterministic"):
    fingerprint = (code, sheet, str_ref, mech_ref)

    for finding in findings:
        match = existing_by_fingerprint.get(fingerprint(finding))
        if match:
            # Update severities/messages but preserve user state
            match.severity = finding["severity"]
            match.formula = finding.get("formula", match.formula)
            if finding.get("result_json"):
                match.result_json = json.dumps(finding["result_json"])
            # state, assigned, created_at are preserved
        else:
            # Insert new finding
            db.add(Issue(state="open", assigned=None, created_at=now, ...))

    # Existing open issues not matched → mark obsolete
    for issue in existing:
        if issue not in seen and issue.state == "open":
            issue.state = "obsolete"
```

User state (`resolved`, `dismissed`, `assigned`) survives re-analysis. Resolved/dismissed issues are never silently deleted.

---

## 4. `events.py` — Append-only event log (280 LOC)

### Public API

```python
# Idempotent migration
def ensure_event_table(engine: Engine) -> None: ...

# Insert with dedupe
def emit_event(
    db: Session,
    project_id: str,
    code: str,
    message: str,
    *,
    tone: str = "info",
    payload: dict | None = None,
    dedupe_key: str | None = None,
    created_at: int | None = None,
) -> ProjectEvent: ...

# Most-recent first, bounded
def list_events(
    db: Session,
    project_id: str,
    limit: int = DEFAULT_EVENTS_LIMIT,  # 200
) -> list[ProjectEvent]: ...

# Helper for routers
def _event_to_dict(row: ProjectEvent) -> dict: ...

# Compute check aggregation from issues
def aggregate_checks(issues: list) -> list[dict]: ...
```

### Constants

```python
MAX_EVENTS_RETURNED = 500
DEFAULT_EVENTS_LIMIT = 200
_VALID_TONES = {"info", "ok", "warn", "fail"}
```

### `ensure_event_table`

Idempotent SQLite migration. Uses `sqlalchemy.inspect(engine)` to check if the table exists before creating — safe to call on every startup.

### `emit_event` dedup logic

```python
if dedupe_key:
    existing = db.execute(
        select(ProjectEvent).where(ProjectEvent.dedupe_key == dedupe_key)
    ).scalar_one_or_none()
    if existing is not None:
        return existing   # ← idempotent
```

If `dedupe_key` not provided, generates `f"{project_id}:{code}:{uuid.uuid4()}"` (always unique, never deduped).

### `aggregate_checks(issues)`

Derives a CHECKS-shaped list from the issues in a project:

```python
CHECK_CATALOG = [
    {"id": "fuzzy", "name": "Fuzzy ID match",       "meta": "..."},
    {"id": "pos",   "name": "Position tolerance",    "meta": "..."},
    {"id": "size",  "name": "Size tolerance",        "meta": "..."},
    {"id": "poly",  "name": "Polygon clash",         "meta": "..."},
    {"id": "clear", "name": "Clearance zone",        "meta": "..."},
    {"id": "elev",  "name": "Elevation alignment",   "meta": "..."},
    {"id": "req",   "name": "Required-not-missing",  "meta": "..."},
    {"id": "orph",  "name": "Orphan-provided",       "meta": "..."},
]

_CODE_TO_CHECK = [
    ("FUZZY", "fuzzy"),  ("POS", "pos"),       ("SIZE", "size"),
    ("CLASH", "poly"),   ("POLY", "poly"),     ("CLEAR", "clear"),
    ("ELEV",  "elev"),   ("OPEN-MISS", "req"), ("OPEN-ORPH", "orph"),
]
```

For each check ID, computes:
- `state` = `"fail"` (any high) | `"warn"` (any medium/low) | `"ok"` (only pass)
- `count` = number of issues at the highest non-ok severity

Full reference: **[EVENTS.md](./EVENTS.md)**.

---

## 5. `normalize.py` — Layer 3 canonical schema (236 LOC)

### Pydantic models

```python
class Support(BaseModel):
    id: str
    type: Literal["restraint", "anchor", "guide", "saddle"]
    grid: str | None = None
    x_mm: float
    y_mm: float
    load_kg: float | None = None
    fluid: str | None = None

class Opening(BaseModel):
    id: str
    service: Literal["duct", "pipe", "cable-tray", "sleeve", "trench"]
    grid: str | None = None
    x: float
    y: float
    w: float
    h: float
    elevation: float | None = None

class Member(BaseModel):
    id: str
    type: Literal["beam", "column", "brace", "truss", "joist"]
    section: str | None = None
    grid_start: str | None = None
    grid_end: str | None = None
    profile: dict[str, Any] | None = None

class Tolerance(BaseModel):
    project_default_mm: float = 25.0
    opening_size_mm: float = 10.0
    position_mm: float = 25.0
    elevation_mm: float = 50.0
    clearance_mm: float = 50.0

class NormalizedDrawing(BaseModel):
    supports: list[Support] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    members: list[Member] = Field(default_factory=list)
    tolerance: Tolerance = Field(default_factory=Tolerance)
```

### Public API

```python
SYSTEM_PROMPT = """You are ADV — an AEC drawing normalizer running on a {provider} LLM.
Read the supplied DWG entity metadata (layers, text labels, geometry in mm) and
emit a JSON object matching the canonical schema: ...
"""

async def normalize_drawing(
    discipline: str,
    entities: list[dict],
    file_meta: dict | None = None,
    *,
    max_retries: int = 2,
) -> NormalizedDrawing:
    """Call the configured LLM and return a validated NormalizedDrawing.

    Falls back to a heuristic-only NormalizedDrawing derived from the parsed
    entities when no LLM is configured.
    """
```

### Behavior

1. Try configured provider → if it succeeds, validate + return
2. Try the other provider (Gemini ↔ Ollama) → if it succeeds, validate + return
3. Fall back to `_heuristic_normalize` (always succeeds)

### `_heuristic_normalize` mapping

```python
_KIND_TO_SERVICE = {"duct": "duct", "pipe": "pipe", "opening": "duct"}
_KIND_TO_MEMBER  = {"beam": "beam", "column": "column"}

# For each entity:
#   kind in _KIND_TO_SERVICE  → Opening
#   kind in _KIND_TO_MEMBER   → Member (no x/y)
#   kind == "equipment"       → Support (type: "restraint")
```

---

## 6. `llm_gemini.py` — Google Gemini client (190 LOC)

### Pydantic schema

```python
class IssueFromLLM(BaseModel):
    severity: Literal["high", "medium", "low", "pass"]
    category: str
    code: str
    title: str
    evidence: str
    sheet: str | None = None
    grid: str | None = None
    mech_ref: str | None = None
    str_ref: str | None = None
    formula: str | None = None

class IssuesResponse(BaseModel):
    issues: list[IssueFromLLM]
```

### Public API

```python
def gemini_configured() -> bool:
    return bool(get_settings().gemini_api_key)

async def analyse_drawings(
    project_meta: dict, str_meta: dict, mech_meta: dict,
) -> list[dict]:
    """Call Gemini with a hard timeout. Returns a list of normalized issue dicts."""

async def normalize(system: str, prompt: str, schema: type[BaseModel]) -> dict:
    """Call Gemini with the canonical schema as response_schema."""
```

### Call structure

```python
client = genai.Client(api_key=settings.gemini_api_key)

result = await asyncio.wait_for(
    asyncio.to_thread(
        client.models.generate_content,
        model=settings.gemini_model,            # default: 'gemini-2.5-flash'
        contents=prompt,
        config={
            "system_instruction": SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "response_schema":    IssuesResponse.model_json_schema(),
            "temperature":        0.2,
        },
    ),
    timeout=settings.gemini_timeout_sec,         # default: 20s
)
text = result.text
parsed_dict = json.loads(text)
```

### Severity rules (encoded in SYSTEM_PROMPT)

- `high`: hard clash, missing primary support, off-by-tolerance (>100mm)
- `medium`: clearance violation, orphan opening, off-by-tolerance (25-100mm)
- `low`: cosmetic / tagging / convention mismatch
- `pass`: representative all-good baseline (return at least 1 per drawing pair)

Full LLM documentation: **[LLM.md](./LLM.md)**.

---

## 7. `llm_ollama.py` — Self-hosted Ollama client (111 LOC)

### Public API

```python
def ollama_configured() -> bool:
    return bool(get_settings().ollama_base_url)

async def analyse_drawings(
    project_meta: dict, str_meta: dict, mech_meta: dict,
) -> list[dict]:
    """POST a prompt to a local Ollama server, return normalized issue dicts."""

async def normalize(system: str, prompt: str) -> dict:
    """POST to a local Ollama /api/chat endpoint and return a dict matching
    the canonical schema. Used by services/normalize.py."""
```

### Call structure (analyse_drawings)

```python
url = f"{settings.ollama_base_url}/api/generate"
body = {
    "model":  settings.ollama_model,   # default: 'qwen2.5:14b'
    "prompt": prompt,
    "stream": False,
    "format": "json",                  # forces JSON output
}

async with httpx.AsyncClient(timeout=settings.gemini_timeout_sec * 2) as client:
    resp = await client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()

raw = data.get("response", "{}")
parsed = json.loads(raw)
issues = parsed.get("issues", [])
```

### Call structure (normalize)

```python
url = f"{settings.ollama_base_url}/api/chat"
body = {
    "model":  settings.ollama_model,
    "messages": [
        {"role": "system", "content": system},
        {"role": "user",   "content": prompt},
    ],
    "stream": False,
    "format": "json",
}
```

Full LLM documentation: **[LLM.md](./LLM.md)**.

---

## 8. `dwg_convert.py` — libredwg subprocess wrapper (125 LOC)

### Public API

```python
def find_libredwg(explicit: str | None = None) -> Path | None:
    """Resolution order:
       1. explicit arg (typically $LIBREDWG_BIN env var)
       2. dwg2dxf resolved from $PATH
       """

def libredwg_available() -> bool:
    return find_libredwg() is not None

def convert_dwg_to_dxf(
    dwg_path: str | Path,
    out_dir: Path | None = None,
    timeout_sec: int = 60,
) -> Path | None:
    """Convert a DWG file to DXF using libredwg.

    Returns the absolute path to the produced DXF, or None on any failure.
    Never raises.
    """
```

### Resolution

```python
candidates = []
if explicit:              candidates.append(explicit)
if os.environ.get("LIBREDWG_BIN"): candidates.append(os.environ["LIBREDWG_BIN"])
path_bin = shutil.which("dwg2dxf")
if path_bin:               candidates.append(path_bin)

for raw in candidates:
    p = Path(raw).expanduser()
    if p.is_file() and os.access(p, os.X_OK):
        return p
return None
```

### Conversion

```python
args = [str(bin_path), "-y", "-o", str(out_dxf), str(dwg_p)]

# NOTE: we deliberately do NOT pass -m (minimal) because we need the
# full BLOCKS section to expand INSERT references — Revit 3D exports
# represent every structural member as an INSERT into a Part-* block,
# and without the BLOCKS section those INSERTs cannot be expanded.

proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_sec, check=False)
```

### Failure modes (all return `None`, never raise)

- Binary not found
- DWG file doesn't exist
- Subprocess timeout (60s default)
- `OSError` (binary failed to launch)
- Non-zero exit code
- Empty output file

---

## 9. `revisions.py` — Layer 0 revision ledger (129 LOC)

### Public API

```python
class DuplicateRevision(Exception):
    """Raised when an uploaded file's SHA-256 already exists in the ledger."""
    revision_id: str

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

### Algorithm

```python
def register_revision(db, *, family_id, sha256, filename, size_bytes, project_id, uploaded_by=None):
    existing = find_by_sha(db, sha256)
    if existing:
        raise DuplicateRevision(existing.id)     # ← idempotent dedupe

    previous_letter = _latest_letter_for_family(db, family_id)
    new_letter = _next_letter(previous_letter or "")

    previous = latest revision in family_id
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

### `_next_letter` (with wrap-around)

```python
def _next_letter(current):
    if not current or current not in string.ascii_uppercase:
        return "A"
    idx = string.ascii_uppercase.index(current)
    return string.ascii_uppercase[(idx + 1) % 26]   # Z → A (wraps)
```

Full reference: **[REVISIONS.md](./REVISIONS.md)**.

---

## 10. Dependency graph

```
HTTP request
     │
     ▼
routers/projects.py ──────► services/analyze.py
     │                          │
     │                          ├─► services/parse.py ──► services/dwg_convert.py
     │                          │                  └─► ezdxf (libredwg subprocess)
     │                          │
     │                          ├─► services/rules.py ──► Shapely, RapidFuzz, scipy
     │                          │
     │                          └─► services/llm_gemini.py / services/llm_ollama.py
     │
     ├─► services/events.py (emit at every step)
     ├─► services/revisions.py (POST /revisions)
     └─► utils/storage.py (persist_upload, SHA-256, format detection)
              │
              └─► utils/hashing.py (hashlib.sha256)
```

---

*For check-specific reference: [`RULES.md`](./RULES.md). For LLM details: [`LLM.md`](./LLM.md). For data model: [`DATA_MODEL.md`](./DATA_MODEL.md).*