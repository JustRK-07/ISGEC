# Index — ISGEC Documentation

A navigation aid. Read top-to-bottom for a tour, or jump to a specific doc.

---

## 📚 Reading order

If you're new to the codebase, read in this order:

1. **[README.md](./README.md)** — overview, file map, quickstart
2. **[`pipeline/OVERVIEW.md`](./pipeline/OVERVIEW.md)** — the geometry core
3. **[`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md)** — the FastAPI 6-layer pipeline
4. **[`backend/DATA_MODEL.md`](./backend/DATA_MODEL.md)** — every table, every column
5. **[`backend/API.md`](./backend/API.md)** — every REST endpoint
6. **[`backend/SERVICES.md`](./backend/SERVICES.md)** — business logic reference
7. **[`backend/RULES.md`](./backend/RULES.md)** — the 8 deterministic checks
8. **[`backend/LLM.md`](./backend/LLM.md)** — Gemini + Ollama clients
9. **[`frontend/STRUCTURE.md`](./frontend/STRUCTURE.md)** — the Next.js app
10. **[`reference/BACKEND_ARCHITECTURE.md`](./reference/BACKEND_ARCHITECTURE.md)** — design source-of-truth
11. **[`reference/WEBSITE_CONTENT_BRIEF.md`](./reference/WEBSITE_CONTENT_BRIEF.md)** — marketing source-of-truth

---

## 🎯 By task

### "I need to understand what this project does"

→ **[README.md](./README.md)** → **[`pipeline/OVERVIEW.md`](./pipeline/OVERVIEW.md)**

### "I need to run the geometry pipeline"

→ **[`pipeline/README.md`](./pipeline/README.md)** → §"Quick start"

### "I need to deploy the web app"

→ **[`backend/SETUP.md`](./backend/SETUP.md)** → §9 "Production hardening checklist"
→ **[`frontend/SETUP.md`](./frontend/SETUP.md)** → §4 "Docker"

### "I need to add a new REST endpoint"

→ **[`backend/API.md`](./backend/API.md)** (existing endpoints + JSON contracts)
→ **[`backend/SERVICES.md`](./backend/SERVICES.md)** (where to put business logic)
→ Look at `backend/app/routers/` for the FastAPI router pattern

### "I need to add a new validation rule"

→ **[`backend/RULES.md`](./backend/RULES.md)** (the 8 existing checks — pick a pattern)
→ Add the function to `backend/app/services/rules.py`
→ Add it to `run_checks` orchestrator
→ Add to `CHECK_CATALOG` in `backend/app/services/events.py` so it appears in the workspace rail
→ Add to `_CODE_TO_CHECK` if it has a unique code prefix

### "I need to add a new overlay strategy"

→ **[`pipeline/STRATEGY-A.md`](./pipeline/STRATEGY-A.md)** (the highest-editability strategy — easiest to extend)
→ Create `D/scripts/clean.py`, `D/scripts/fit.py`, `D/scripts/overlay.py` (copy A as the base)
→ Add `D/` to the `APPROACHES` list in `run_to_dxf.py`
→ Add verification check to `verify_all.py`

### "I need to understand the database"

→ **[`backend/DATA_MODEL.md`](./backend/DATA_MODEL.md)** (every table, every column, every relationship)

### "I need to debug a finding"

1. Find the issue via `GET /api/projects/{id}` → `issues` array
2. Read the `formula` field — that's the exact math
3. Check `result_json` — that's the structured output
4. The `code` prefix tells you which check produced it (see [`backend/RULES.md`](./backend/RULES.md))

### "I need to add a new LLM provider"

→ **[`backend/LLM.md`](./backend/LLM.md)** (existing Gemini + Ollama clients)
→ Add new client module in `backend/app/services/`
→ Wire into `normalize._call_provider` and `analyze.run_phase_2`

### "I need to understand the test suites"

→ **[`backend/TESTS.md`](./backend/TESTS.md)** (pytest, 1,540 LOC, 9 files)
→ **[`frontend/TESTING.md`](./frontend/TESTING.md)** (Vitest, 3 test files)

### "I need to set up local dev"

→ **[`backend/SETUP.md`](./backend/SETUP.md)** → §1 "Local development setup"
→ **[`frontend/SETUP.md`](./frontend/SETUP.md)** → §1 "Local development setup"

### "I need to add a new marketing section"

→ **[`frontend/MARKETING.md`](./frontend/MARKETING.md)** → §2 "Component index"
→ [`reference/WEBSITE_CONTENT_BRIEF.md`](./reference/WEBSITE_CONTENT_BRIEF.md) — the brief the components implement

### "I need to add a new workspace tab"

→ **[`frontend/WORKSPACE.md`](./frontend/WORKSPACE.md)** → §2 "Components"
→ Edit `frontend/components/workspace/IssueInspector.tsx`

---

## 📂 Files in this folder

### Top-level

| File | Purpose |
|---|---|
| `README.md` | Project overview, file map, quickstart |
| `INDEX.md` | This file — by-task navigation |

### `pipeline/` (the geometry core)

| File | Purpose |
|---|---|
| `pipeline/README.md` | Pipeline overview, layout, quick start |
| `pipeline/OVERVIEW.md` | What the pipeline does, source drawings, choosing A/B/C |
| `pipeline/CLEAN-FIT-OVERLAY.md` | The 3-stage process in detail |
| `pipeline/STRATEGY-A.md` | Per-entity overlay (highest editability, original colors) |
| `pipeline/STRATEGY-B.md` | 2-block overlay (forced red/blue, toggleable) |
| `pipeline/STRATEGY-C.md` | 1-block overlay (single atomic unit) |
| `pipeline/VERIFICATION.md` | Audit, overlap check, rendering |
| `pipeline/SCRIPTS.md` | Per-script behavior reference (pre-existing) |
| `pipeline/DXF_CLEANING_GUIDE.md` | Detailed cleaning guide (pre-existing) |

### `backend/` (the FastAPI service)

| File | Purpose |
|---|---|
| `backend/README.md` | Backend docs overview |
| `backend/ARCHITECTURE.md` | 6-layer pipeline, request lifecycle |
| `backend/DATA_MODEL.md` | Tables, columns, JSON contracts |
| `backend/API.md` | Every REST endpoint |
| `backend/SERVICES.md` | Business logic reference |
| `backend/RULES.md` | 8 deterministic checks |
| `backend/LLM.md` | Gemini + Ollama clients |
| `backend/REVISIONS.md` | Layer 0 revision ledger |
| `backend/EVENTS.md` | Append-only event log |
| `backend/SETUP.md` | Local dev + Docker |
| `backend/TESTS.md` | pytest suite |
| `backend/INDEX.md` | Backend navigation |

### `frontend/` (the Next.js app)

| File | Purpose |
|---|---|
| `frontend/README.md` | Frontend docs overview |
| `frontend/STRUCTURE.md` | Directory layout, routes, components |
| `frontend/MARKETING.md` | 16 marketing section components |
| `frontend/WORKSPACE.md` | Drawing workspace components |
| `frontend/TESTING.md` | Vitest unit tests |
| `frontend/SETUP.md` | Local dev + Docker |

### `reference/` (locally-cached design specs)

| File | Purpose |
|---|---|
| `reference/BACKEND_ARCHITECTURE.md` | 6-layer pipeline + algorithm spec |
| `reference/WEBSITE_CONTENT_BRIEF.md` | Marketing brief |

---

## 🔗 Cross-references

- **Source-of-truth design documents** (in [`reference/`](./reference/)):
  - [`BACKEND_ARCHITECTURE.md`](./reference/BACKEND_ARCHITECTURE.md) — pipeline + algorithm spec
  - [`WEBSITE_CONTENT_BRIEF.md`](./reference/WEBSITE_CONTENT_BRIEF.md) — product positioning + capabilities

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
  - `A/scripts/`, `B/scripts/`, `C/scripts/` — pipeline stages
  - `frontend/app/` — App Router pages
  - `frontend/components/` — React components
  - `frontend/lib/` — typed API client, Zustand stores, viewport utils

---

## 🔍 Search cheat sheet

### Code → docs

| Looking for… | Go to |
|---|---|
| `Project` model | `backend/app/models/project.py` + [`backend/DATA_MODEL.md`](./backend/DATA_MODEL.md) |
| `Issue` model | `backend/app/models/issue.py` + [`backend/DATA_MODEL.md`](./backend/DATA_MODEL.md) §4 |
| `Revision` model | `backend/app/models/revision.py` + [`backend/REVISIONS.md`](./backend/REVISIONS.md) |
| `ProjectEvent` model | `backend/app/models/event.py` + [`backend/EVENTS.md`](./backend/EVENTS.md) |
| `parse_file` function | `backend/app/services/parse.py` + [`backend/SERVICES.md`](./backend/SERVICES.md) §1 |
| `run_checks` orchestrator | `backend/app/services/rules.py` + [`backend/RULES.md`](./backend/RULES.md) §9 |
| `run_phase_1` / `run_phase_2` | `backend/app/services/analyze.py` + [`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md) §7 |
| `register_revision` | `backend/app/services/revisions.py` + [`backend/REVISIONS.md`](./backend/REVISIONS.md) |
| `emit_event` | `backend/app/services/events.py` + [`backend/EVENTS.md`](./backend/EVENTS.md) |
| `normalize_drawing` | `backend/app/services/normalize.py` + [`backend/LLM.md`](./backend/LLM.md) |
| `gemini.analyse_drawings` | `backend/app/services/llm_gemini.py` + [`backend/LLM.md`](./backend/LLM.md) |
| `ollama.normalize` | `backend/app/services/llm_ollama.py` + [`backend/LLM.md`](./backend/LLM.md) |
| `convert_dwg_to_dxf` | `backend/app/services/dwg_convert.py` + [`backend/SERVICES.md`](./backend/SERVICES.md) |
| All REST endpoints | `backend/app/routers/` + [`backend/API.md`](./backend/API.md) |
| All Pydantic schemas | `backend/app/schemas/` + [`backend/DATA_MODEL.md`](./backend/DATA_MODEL.md) §8 |
| `clean.py` | `A/scripts/clean.py` + [`pipeline/CLEAN-FIT-OVERLAY.md`](./pipeline/CLEAN-FIT-OVERLAY.md) |
| `fit.py` | `A/scripts/fit.py` + [`pipeline/CLEAN-FIT-OVERLAY.md`](./pipeline/CLEAN-FIT-OVERLAY.md) |
| `overlay.py` (A) | `A/scripts/overlay.py` + [`pipeline/STRATEGY-A.md`](./pipeline/STRATEGY-A.md) |
| `overlay.py` (B) | `B/scripts/overlay.py` + [`pipeline/STRATEGY-B.md`](./pipeline/STRATEGY-B.md) |
| `overlay.py` (C) | `C/scripts/overlay.py` + [`pipeline/STRATEGY-C.md`](./pipeline/STRATEGY-C.md) |
| `run_to_dxf.py` | `run_to_dxf.py` + [`pipeline/OVERVIEW.md`](./pipeline/OVERVIEW.md) |
| `verify_all.py` | `verify_all.py` + [`pipeline/VERIFICATION.md`](./pipeline/VERIFICATION.md) |
| Frontend routes | `frontend/app/` + [`frontend/STRUCTURE.md`](./frontend/STRUCTURE.md) |
| Marketing components | `frontend/components/marketing/` + [`frontend/MARKETING.md`](./frontend/MARKETING.md) |
| Workspace components | `frontend/components/workspace/` + [`frontend/WORKSPACE.md`](./frontend/WORKSPACE.md) |
| API client | `frontend/lib/api.ts` + [`frontend/STRUCTURE.md`](./frontend/STRUCTURE.md) §"Libraries" |
| Zustand stores | `frontend/lib/store.ts` + [`frontend/STRUCTURE.md`](./frontend/STRUCTURE.md) §"Libraries" |
| Viewport utilities | `frontend/lib/viewport.ts` + [`frontend/STRUCTURE.md`](./frontend/STRUCTURE.md) §"Libraries" |

### Docs → concept

| Concept | Go to |
|---|---|
| 6-layer pipeline | [`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md) |
| Layer 0 (revision ledger) | [`backend/REVISIONS.md`](./backend/REVISIONS.md) |
| Layer 1 (DXF/DWG extraction) | [`backend/SERVICES.md`](./backend/SERVICES.md) §1 |
| Layer 2 (grid registration) | [`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md) §3 |
| Layer 3 (LLM normalization) | [`backend/LLM.md`](./backend/LLM.md) |
| Layer 4 (8 deterministic checks) | [`backend/RULES.md`](./backend/RULES.md) |
| Layer 5 (reporting) | [`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md) §6 |
| Two-phase analyzer | [`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md) §7 |
| Reconciliation semantics | [`backend/SERVICES.md`](./backend/SERVICES.md) §3 |
| Append-only event log | [`backend/EVENTS.md`](./backend/EVENTS.md) |
| Gridline affine fit | [`pipeline/CLEAN-FIT-OVERLAY.md`](./pipeline/CLEAN-FIT-OVERLAY.md) §"Stage 2" |
| 3 overlay strategies | [`pipeline/OVERVIEW.md`](./pipeline/OVERVIEW.md) §2 |
| Pixel-level overlap check | [`pipeline/VERIFICATION.md`](./pipeline/VERIFICATION.md) §2 |
| Click-to-locate UX | [`frontend/WORKSPACE.md`](./frontend/WORKSPACE.md) §6 |
| Zero-API LLM callout | [`backend/LLM.md`](./backend/LLM.md) §0 |
| Production hardening | [`backend/SETUP.md`](./backend/SETUP.md) §9 |

---

*Start with [README.md](./README.md) → [INDEX.md](./INDEX.md) → [pipeline/OVERVIEW.md](./pipeline/OVERVIEW.md).*