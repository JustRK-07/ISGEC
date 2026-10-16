# Tests — pytest Suite

> **Source:** `tests/` — 9 test files, ~1,540 LOC.
> **Runner:** `pytest` ≥ 8.3 with `pytest-asyncio` (`asyncio_mode = "auto"`).
> **Run:** `pytest tests/ -v`

The test suite covers every layer of the backend, from the custom DXF parser through to end-to-end HTTP flows. Heavy libraries (RapidFuzz, Shapely, scipy) are **optional** — tests work without them.

---

## 0. Layout

```
tests/
├── __init__.py                       # empty marker
├── conftest.py                       # (none yet — fixtures live in fixtures/ dir)
├── fixtures/
│   ├── tp104_mech.dxf                # real MECH drawing from the TP-104 conveyor project
│   └── tp104_str.dxf                 # real STR drawing from the TP-104 conveyor project
│
├── test_parse.py                      # 91 LOC  — DXF entity extraction
├── test_dwg_convert.py                # 86 LOC  — libredwg wrapper
├── test_dwg_real_geometry.py         # 191 LOC  — parser on real fixtures
├── test_rules.py                      # 84 LOC  — basic rules
├── test_rules_advanced.py            # 238 LOC  — edge cases for polygon/clearance/fuzzy
├── test_normalize.py                  # 99 LOC  — canonical schema + LLM fallback
├── test_revisions.py                 # 221 LOC  — Layer 0 revision ledger
├── test_events.py                    # 393 LOC  — append-only event log + aggregate_checks
└── test_e2e.py                       # 137 LOC  — full HTTP surface (upload → delete)
```

---

## 1. Quick start

### Install dev dependencies

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov httpx
```

(Or use the dev extras in `pyproject.toml`: `pip install -e .[dev]`)

### Run all tests

```bash
pytest tests/ -v
```

Expected output:

```
tests/test_dwg_convert.py::test_find_libredwg_env PASSED
tests/test_dwg_convert.py::test_convert_dwg_to_dxf_with_real_binary PASSED
tests/test_dwg_real_geometry.py::test_real_mech_entity_count PASSED
tests/test_dwg_real_geometry.py::test_real_str_grid_labels PASSED
tests/test_e2e.py::test_e2e_upload_list_get_delete PASSED
tests/test_e2e.py::test_e2e_revision_upload_then_duplicate_409 PASSED
tests/test_e2e.py::test_e2e_health_includes_llm_status PASSED
tests/test_events.py::test_emit_event_dedupe PASSED
...
```

### Coverage report

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

### Specific file

```bash
pytest tests/test_revisions.py -v
pytest tests/test_rules_advanced.py -k "polygon" -v
```

---

## 2. Test fixtures

### `tests/fixtures/tp104_mech.dxf`

The **real Mechanical GA** from the TP-104 conveyor project (16 MB raw, multiple stripped variants available in `../dxf/`). 289 entities in modelspace, 17 unique layer colors, 7 labeled gridlines (`TP104-A/B/C/D` + `1/2/3`).

Used by:
- `test_dwg_real_geometry.py` — end-to-end parse + classify

### `tests/fixtures/tp104_str.dxf`

The **real Structural GA** from the TP-104 conveyor project (8.4 MB raw). 1,953 INSERTs into `GridLine-*`, `Part-*`, `Bolt-*`, `Connection-*` blocks. Multiple stripped variants.

Used by:
- `test_dwg_real_geometry.py`

### In-test helpers

```python
def _dxf_bytes():
    """Build a minimal valid DXF payload — header + one TEXT + one LWPOLYLINE."""
    return (
        b"0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n"
        b"0\nSECTION\n2\nENTITIES\n"
        b"0\nTEXT\n8\nGRID-A\n10\n100.0\n20\n200.0\n40\n2.5\n1\nTP104-A\n"
        b"0\nLWPOLYLINE\n8\nOPENINGS\n10\n300.0\n20\n400.0\n"
        b"0\nENDSEC\n0\nEOF\n"
    )
```

A minimal DXF that the test fixture bytes include:
- HEADER section with `$INSUNITS = 4` (mm)
- One TEXT entity on layer `GRID-A` with text `TP104-A`
- One LWPOLYLINE on layer `OPENINGS`

Used by `test_e2e.py` for upload tests.

---

## 3. Per-file coverage

### `test_parse.py` (91 LOC) — DXF parser

Tests `services/parse.py`:

| Test | What it covers |
|---|---|
| `test_parse_dxf_basic` | `_parse_dxf` returns expected entity count, layer list |
| `test_parse_dxf_insunits` | `$INSUNITS` correctly extracted from HEADER |
| `test_dxf_to_entities` | `dxf_to_entities` produces dicts matching the Entity schema |
| `test_units_to_mm` | `INSUNITS_TO_MM` lookup correctness |
| `test_parse_dxf_desync_recovery` | Tokens with invalid group codes don't crash |
| `test_dwg_version_lookup` | `DWG_VERSIONS` dict returns correct version string |

### `test_dwg_convert.py` (86 LOC) — libredwg wrapper

Tests `services/dwg_convert.py`:

| Test | What it covers |
|---|---|
| `test_find_libredwg_env` | Resolves from `LIBREDWG_BIN` env var |
| `test_find_libredwg_path` | Falls back to `shutil.which("dwg2dxf")` |
| `test_convert_dwg_to_dxf_with_real_binary` | End-to-end with a real DWG file |
| `test_convert_dwg_to_dxf_missing_binary` | Returns `None` (not raise) when binary missing |
| `test_convert_dwg_to_dxf_timeout` | Returns `None` on subprocess timeout |

### `test_dwg_real_geometry.py` (191 LOC) — real drawings

Tests parser on `tests/fixtures/tp104_mech.dxf` + `tp104_str.dxf`:

| Test | What it covers |
|---|---|
| `test_real_mech_entity_count` | ~289 entities in MECH modelspace |
| `test_real_str_grid_labels` | 7 grid labels preserved (TP104-A/B/C/D/1/2/3) |
| `test_real_str_inserts` | 1,953 INSERTs into `GridLine-*` blocks |
| `test_real_text_labels_preserved` | TEXT entities kept after cleaning simulation |
| `test_layer_counts` | 17 unique layers in MECH |

### `test_rules.py` (84 LOC) — basic rules

Tests the basic happy-path behavior of `services/rules.py`:

| Test | What it covers |
|---|---|
| `test_run_checks_basic` | `run_checks` returns list of dicts |
| `test_simple_similarity` | Jaccard 3-gram correctness |
| `test_check_missing` | Mech-only opening → OPEN-MISS finding |
| `test_check_orphan` | Str-only opening → OPEN-ORPH finding |
| `test_check_position` | Position off → POS-D finding |
| `test_check_size` | Size off → SIZE-D finding |

### `test_rules_advanced.py` (238 LOC) — edge cases

| Test | What it covers |
|---|---|
| `test_polygon_clash_diagonal` | Diagonal overlap caught (AABB would miss) |
| `test_polygon_clash_threshold` | Min area filter respected |
| `test_clearance_zone_violation` | Sub-threshold distance → CLEAR-VIOL |
| `test_clearance_no_double_report` | Hard clash ≠ clearance |
| `test_fuzzy_match_hungarian` | Hungarian assignment via scipy |
| `test_fuzzy_match_greedy_fallback` | Greedy assignment when scipy missing |
| `test_fuzzy_verify_band` | Score 0.55-0.80 → TAG-VERIFY |
| `test_fuzzy_pass_band_silent` | Score ≥ 0.80 → no finding |
| `test_elevation_mismatch` | ELEV-DELTA with formula trace |
| `test_elevation_skip_when_missing` | Both sides must have elevation |
| `test_orchestrator_order` | run_checks calls in expected order |
| `test_run_checks_with_gemini_issues` | LLM issues feed in (currently unused) |

### `test_normalize.py` (99 LOC) — canonical schema

Tests `services/normalize.py`:

| Test | What it covers |
|---|---|
| `test_pydantic_models_validate` | Support/Opening/Member/Tolerance validate |
| `test_normalize_drawing_fallback` | Heuristic when no LLM configured |
| `test_normalize_heuristic_mapping` | kind→service + kind→member mappings |
| `test_normalize_with_gemini` | (skipped if no Gemini key) |
| `test_normalize_with_ollama` | (skipped if no Ollama) |
| `test_build_user_prompt` | Bounded prompt (first 200 entities) |

### `test_revisions.py` (221 LOC) — Layer 0 ledger

Tests `services/revisions.py` + `routers/revisions.py`:

| Test | What it covers |
|---|---|
| `test_normalize_family_id` | Various filename patterns (Rev, rev, R, (C), underscored, hyphenated) |
| `test_register_revision_happy_path` | A → B → C chain |
| `test_register_revision_duplicate_raises` | Same SHA-256 → DuplicateRevision |
| `test_register_revision_different_family` | Same SHA, different family_id → both accepted |
| `test_next_letter_wrap` | Z → A (rare edge case) |
| `test_router_post_revision` | 201 on first upload |
| `test_router_post_revision_duplicate` | 409 with existing revision_id |
| `test_router_post_revision_different_bytes` | 201, letter increments, supersedes set |
| `test_router_get_revisions` | List returns in upload order |

### `test_events.py` (393 LOC) — event log

Tests `services/events.py`:

| Test | What it covers |
|---|---|
| `test_emit_event_basic` | Insert with all fields |
| `test_emit_event_dedupe` | Same dedupe_key → same row |
| `test_emit_event_required_fields` | ValueError on missing fields |
| `test_tone_coercion` | `"OK"` → `"ok"`, invalid → `"info"` |
| `test_list_events_ordering` | Newest first |
| `test_list_events_limit_cap` | Hard cap at 500 |
| `test_ensure_event_table_idempotent` | Multiple calls no-op |
| `test_aggregate_checks_all_pass` | state=ok, count=N |
| `test_aggregate_checks_with_fail` | state=fail overrides warn/ok |
| `test_aggregate_checks_with_warn` | state=warn when no fail |
| `test_aggregate_checks_unknown_code` | Skipped (no check_id match) |
| `test_category_derivation` | Code prefix → category |
| `test_event_to_dict` | ORM row → JSON shape |

### `test_e2e.py` (137 LOC) — full HTTP surface

End-to-end smoke test exercising the public API.

#### Fixture: `client`

```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'adv.db'}")

    from app.config import get_settings
    get_settings.cache_clear()
    from app.db import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c
```

Each test gets an isolated `tmp_path` data dir + fresh DB. `lru_cache` on `get_settings()` is cleared between tests.

#### Tests

```python
def test_e2e_upload_list_get_delete(client):
    """End-to-end: upload → list → get → analyze → delete → 404."""

def test_e2e_revision_upload_then_duplicate_409(client):
    """Revisions: first 201, duplicate 409 with existing id, new bytes 201 letter=B."""

def test_e2e_health_includes_llm_status(client):
    """/api/health includes llm.provider + llm.ready."""
```

---

## 4. Test helpers and patterns

### Optional heavy imports

Heavy libraries are guarded so tests run without them:

```python
# In services/rules.py
try:
    from rapidfuzz import fuzz as _rf_fuzz; _HAS_RAPIDFUZZ = True
except ImportError: _HAS_RAPIDFUZZ = False

try:
    from shapely.geometry import Polygon as _Polygon
    from shapely.strtree import STRtree as _STRtree
    _HAS_SHAPELY = True
except ImportError: _HAS_SHAPELY = False
```

Tests that depend on Shapely/RapidFuzz skip gracefully when missing.

### Async tests

`asyncio_mode = "auto"` means async test functions are auto-detected:

```python
async def test_something():
    result = await some_async_func()
    assert result == expected
```

### DB cleanup between tests

The `client` fixture drops + recreates the schema before each test. For unit tests that don't use the HTTP client, models are isolated via:

```python
@pytest.fixture
def db_session():
    from app.db import Base, engine, SessionLocal
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        yield db
    Base.metadata.drop_all(bind=engine)
```

### Settings cache

`get_settings()` is decorated with `@lru_cache(maxsize=1)`. Tests that override env vars must clear the cache:

```python
monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
get_settings.cache_clear()
```

---

## 5. What's covered

| Concern | Coverage |
|---|---|
| DXF parsing | 91 LOC dedicated + 191 LOC on real fixtures |
| DWG conversion | 86 LOC |
| **All 8 rules** | 84 + 238 = 322 LOC dedicated |
| L3 normalization | 99 LOC |
| Layer 0 ledger | 221 LOC |
| Event log + aggregation | 393 LOC |
| **Full HTTP surface** | 137 LOC E2E |
| **Total** | **1,540 LOC** |

## 6. What's NOT covered

- **Real-time LLM calls** — Gemini/Ollama are mocked or skipped; live tests require API keys
- **PostgreSQL-specific behavior** — tests run on SQLite only
- **Multi-worker concurrency** — single-process uvicorn only
- **Authorization / authentication** — backend has no auth in v1

---

## 7. CI integration

```yaml
# .github/workflows/test.yml
- name: Install
  run: |
    pip install -r requirements.txt
    pip install pytest pytest-asyncio pytest-cov httpx

- name: Test
  run: pytest tests/ -v --cov=app --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

---

*For setup: [`SETUP.md`](./SETUP.md). For the architecture: [`ARCHITECTURE.md`](./ARCHITECTURE.md).*