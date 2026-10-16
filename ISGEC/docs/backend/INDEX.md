# Index — ISGEC Backend Documentation

A navigation aid. Read top-to-bottom for a tour, or jump to a specific doc.

---

## 📚 Reading order

If you're new to the codebase, read in this order:

1. **[README.md](./README.md)** — overview, file map, quickstart
2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** — the 6-layer pipeline, request lifecycle
3. **[DATA_MODEL.md](./DATA_MODEL.md)** — every table, every column, JSON contracts
4. **[SERVICES.md](./SERVICES.md)** — business logic reference
5. **[API.md](./API.md)** — every REST endpoint
6. **[RULES.md](./RULES.md)** — the 8 deterministic checks
7. **[LLM.md](./LLM.md)** — Gemini + Ollama clients
8. **[REVISIONS.md](./REVISIONS.md)** — Layer 0 revision ledger
9. **[EVENTS.md](./EVENTS.md)** — append-only event log
10. **[SETUP.md](./SETUP.md)** — local dev + Docker
11. **[TESTS.md](./TESTS.md)** — pytest suite

---

## 🎯 By task

### "I need to understand what this service does"

→ **[README.md](./README.md)** → **[ARCHITECTURE.md](./ARCHITECTURE.md)**

### "I need to add a new REST endpoint"

→ **[API.md](./API.md)** (existing endpoints + JSON contracts)
→ **[SERVICES.md](./SERVICES.md)** (where to put business logic)
→ Look at `app/routers/` for the FastAPI router pattern

### "I need to add a new validation rule"

→ **[RULES.md](./RULES.md)** (the 8 existing checks — pick a pattern)
→ Add the function to `app/services/rules.py`
→ Add it to `run_checks` orchestrator
→ Add to `CHECK_CATALOG` in `app/services/events.py` so it appears in the workspace rail
→ Add to `_CODE_TO_CHECK` if it has a unique code prefix

### "I need to understand the database"

→ **[DATA_MODEL.md](./DATA_MODEL.md)** (every table, every column, every relationship)

### "I need to debug a finding"

1. Find the issue via `GET /api/projects/{id}` → `issues` array
2. Read the `formula` field — that's the exact math
3. Check `result_json` — that's the structured output
4. The `code` prefix tells you which check produced it (see **[RULES.md](./RULES.md)**)

### "I need to add a new LLM provider"

→ **[LLM.md](./LLM.md)** (existing Gemini + Ollama clients)
→ Add new client module in `app/services/`
→ Wire into `normalize._call_provider` and `analyze.run_phase_2`

### "I need to understand the test suite"

→ **[TESTS.md](./TESTS.md)** (layout, fixtures, helpers)

### "I need to deploy this"

→ **[SETUP.md](./SETUP.md)** → §9 "Production hardening checklist"

### "I need to set up local dev"

→ **[SETUP.md](./SETUP.md)** → §1 "Local development setup"

---

## 📂 Files in this folder

| File | Size | Last updated |
|---|---:|---|
| `README.md` | overview + index | generated |
| `DATA_MODEL.md` | tables, columns, JSON contracts | generated |
| `API.md` | REST endpoints | generated |
| `ARCHITECTURE.md` | 6-layer pipeline | generated |
| `SERVICES.md` | business logic reference | generated |
| `RULES.md` | 8 deterministic checks | generated |
| `LLM.md` | Gemini + Ollama | generated |
| `REVISIONS.md` | Layer 0 ledger | generated |
| `EVENTS.md` | append-only event log | generated |
| `SETUP.md` | local dev + Docker | generated |
| `TESTS.md` | pytest suite | generated |
| `INDEX.md` | this file | generated |

---

## 🔗 Cross-references

- **Source-of-truth design documents** (in [`../reference/`](../reference/)):
  - [`BACKEND_ARCHITECTURE.md`](../reference/BACKEND_ARCHITECTURE.md) — pipeline + algorithm spec
  - [`WEBSITE_CONTENT_BRIEF.md`](../reference/WEBSITE_CONTENT_BRIEF.md) — product positioning + capabilities
  - `CONVERSION_PLAN.md` (planned) — phased migration plan

- **Code locations** referenced throughout:
  - `app/main.py` — FastAPI factory
  - `app/config.py` — settings
  - `app/db.py` — engine + lifespan init
  - `app/models/` — 6 SQLAlchemy ORM classes
  - `app/schemas/` — Pydantic v2 request/response models
  - `app/routers/` — 6 FastAPI routers
  - `app/services/` — 9 business-logic modules
  - `app/utils/` — hashing + storage helpers
  - `tests/` — 9 pytest files
  - `scripts/seed_db.py` — demo data seeder

---

## 🔍 Search cheat sheet

| Looking for… | Go to |
|---|---|
| `Project` model | `app/models/project.py` + `DATA_MODEL.md §1` |
| `Issue` model | `app/models/issue.py` + `DATA_MODEL.md §4` |
| `Revision` model | `app/models/revision.py` + `DATA_MODEL.md §5` + `REVISIONS.md` |
| `ProjectEvent` model | `app/models/event.py` + `DATA_MODEL.md §6` + `EVENTS.md` |
| `parse_file` function | `app/services/parse.py` + `SERVICES.md §1` |
| `run_checks` orchestrator | `app/services/rules.py` + `RULES.md §9` |
| `run_phase_1` / `run_phase_2` | `app/services/analyze.py` + `ARCHITECTURE.md §7` |
| `register_revision` | `app/services/revisions.py` + `REVISIONS.md §3` |
| `emit_event` | `app/services/events.py` + `EVENTS.md §3` |
| `normalize_drawing` | `app/services/normalize.py` + `LLM.md §4` |
| `gemini.analyse_drawings` | `app/services/llm_gemini.py` + `LLM.md §2` |
| `ollama.normalize` | `app/services/llm_ollama.py` + `LLM.md §3` |
| `convert_dwg_to_dxf` | `app/services/dwg_convert.py` + `SERVICES.md §8` |
| All REST endpoints | `app/routers/` + `API.md` |
| All Pydantic schemas | `app/schemas/` + `DATA_MODEL.md §8` |

---

*Start with [README.md](./README.md) → [ARCHITECTURE.md](./ARCHITECTURE.md).*