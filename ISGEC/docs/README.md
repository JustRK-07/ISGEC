# ISGEC — Documentation

> **TP-104 Conveyor Overlay Pipeline + Web Application**
> A complete self-sufficient reference for the ISGEC project.

This folder contains the **complete documentation** for the ISGEC project. Every file lives inside `ISGEC/` — **no files from outside ISGEC/ are referenced or required** for understanding this codebase.

---

## 🎯 What ISGEC is

ISGEC is the geometry pipeline + web app for the **TP-104 Conveyor** project (ISGEC / Adani Infra / Dhamra Port). It aligns Mechanical and Structural GA drawings via labeled grid bubbles, producing a superimposed DXF with **sub-unit precision** (residual ~2.34e-7 DXF units). The web app wraps this with an agentic AI layer (8 deterministic checks + LLM enrichment) and a click-to-locate viewer.

**In three sizes** (fy_client):
1. **Geometry core** — Python `A/`, `B/`, `C/` pipelines that produce the superimposed DXF
2. **Backend** — FastAPI service (`backend/`) with the 6-layer agentic pipeline
3. **Frontend** — Next.js app (`frontend/`) for the user-facing workspace

---

## 📑 Index

| Section | Path | What you'll find |
|---|---|---|
| **[INDEX.md](./INDEX.md)** | `./` | Navigation hub — by-task lookup |
| **Pipeline docs** | [`pipeline/`](./pipeline/) | The A/B/C overlay strategies + verification |
| **Backend docs** | [`backend/`](./backend/) | FastAPI service — 6-layer pipeline + REST API |
| **Frontend docs** | [`frontend/`](./frontend/) | Next.js app — components, structure, tests |
| **Reference docs** | [`reference/`](./reference/) | Locally-cached source-of-truth specs |

---

## 🚀 Quick start

### Run the pipeline (geometry core only)

```bash
cd ISGEC/
python3 run_to_dxf.py           # produces dxf/superimposed.dxf + A/B/C variants
```

### Run the web app (backend + frontend)

```bash
cd ISGEC/
docker compose up --build       # starts backend on :8001, frontend on :3001
```

Open <http://localhost:3001>.

Or run individually:

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001

# Frontend (in a second terminal)
cd frontend
npm ci
npm run dev -- --hostname 0.0.0.0 --port 3001
```

### Verify

```bash
cd ISGEC/
python3 verify_all.py 3        # end-to-end audit
python3 check_overlap.py       # pixel-level overlap
python3 render_structure.py    # lime X markers on wrapper INSERTs
python3 render_all.py          # side-by-side composite
```

---

## 📂 Project layout

```
ISGEC/
├── README.md                       project quickstart
├── docker-compose.yml              backend + frontend stack
├── .env.example                    sample env vars
│
├── A/                              Strategy A: per-entity overlay
├── B/                              Strategy B: 2-block overlay
├── C/                              Strategy C: 1-block overlay
│
├── dwg/                            source DWG files (read-only)
├── dxf/                            source DXFs + cleaned + superimposed outputs
├── render/                         ~26 verification PNGs
│
├── run_to_dxf.py                   multi-approach driver
├── verify_all.py                   end-to-end audit
├── check_overlap.py                pixel-level verification
├── render_structure.py             lime X markers
├── render_all.py                   side-by-side composite
│
├── backend/                        FastAPI service
│   ├── app/                        (services, models, routers, schemas, utils)
│   ├── tests/                      pytest suite (9 files, ~1,540 LOC)
│   ├── scripts/seed_db.py          demo project seeder
│   ├── Dockerfile
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/                       Next.js app
│   ├── app/                        (App Router pages)
│   ├── components/                 (marketing, workspace, upload, auth)
│   ├── lib/                        (api, store, viewport — with tests)
│   ├── package.json
│   ├── Dockerfile
│   ├── tsconfig.json
│   ├── vitest.config.ts
│   └── next.config.mjs
│
└── docs/                           ← you are here
    ├── README.md                   (this overview)
    ├── INDEX.md                     (by-task navigation)
    ├── pipeline/                   (A/B/C overlay pipeline docs)
    ├── backend/                    (FastAPI service docs)
    ├── frontend/                   (Next.js app docs)
    └── reference/                  (locally-cached design specs)
```

---

## 🔒 Self-sufficient

This `docs/` folder contains **everything you need** to understand the ISGEC project:

- **All source code** — in `backend/`, `frontend/`, `A/`, `B/`, `C/`
- **All docs** — in `docs/`
- **Design specs** (locally cached in `docs/reference/`):
  - [`BACKEND_ARCHITECTURE.md`](./reference/BACKEND_ARCHITECTURE.md) — the 6-layer pipeline + algorithm spec
  - [`WEBSITE_CONTENT_BRIEF.md`](./reference/WEBSITE_CONTENT_BRIEF.md) — the marketing brief

No files outside `ISGEC/` are required or referenced.

---

## 📚 Reading order

If you're new to the codebase:

1. **[`pipeline/OVERVIEW.md`](./pipeline/OVERVIEW.md)** — the geometry pipeline (A/B/C)
2. **[`backend/ARCHITECTURE.md`](./backend/ARCHITECTURE.md)** — the FastAPI 6-layer pipeline
3. **[`backend/API.md`](./backend/API.md)** — every REST endpoint
5. **[`backend/RULES.md`](./backend/RULES.md)** — the 8 deterministic checks
6. **[`frontend/STRUCTURE.md`](./frontend/STRUCTURE.md)** — the Next.js app
7. **[`reference/BACKEND_ARCHITECTURE.md`](./reference/BACKEND_ARCHITECTURE.md)** — design source-of-truth
8. **[`reference/WEBSITE_CONTENT_BRIEF.md`](./reference/WEBSITE_CONTENT_BRIEF.md)** — marketing source-of-truth

---

## 🎯 By task

### "I want to understand the geometry"

→ [`pipeline/OVERVIEW.md`](./pipeline/OVERVIEW.md) → [`pipeline/CLEAN-FIT-OVERLAY.md`](./pipeline/CLEAN-FIT-OVERLAY.md)

### "I want to run the geometry pipeline"

→ [`pipeline/README.md`](./pipeline/README.md) → §"Quick start"

### "I want to deploy the web app"

→ [`backend/SETUP.md`](./backend/SETUP.md) → §9 "Production hardening checklist"

### "I want to add a new validation rule"

→ [`backend/RULES.md`](./backend/RULES.md) → §11 "Tweakable parameters"

### "I want to understand the data model"

→ [`backend/DATA_MODEL.md`](./backend/DATA_MODEL.md)

### "I want to debug a finding"

1. Find it via `GET /api/projects/{id}` → `issues` array
2. Read the `formula` field — that's the exact math
3. The `code` prefix tells you which check produced it (see [`backend/RULES.md`](./backend/RULES.md))

### "I want to understand the test suites"

→ [`backend/TESTS.md`](./backend/TESTS.md) + [`frontend/TESTING.md`](./frontend/TESTING.md)

### "I want to add a new endpoint"

→ [`backend/API.md`](./backend/API.md) for the existing pattern, then `backend/routers/`

### "I want to add a new LLM provider"

→ [`backend/LLM.md`](./backend/LLM.md)

### "I want to add a new marketing section"

→ [`frontend/MARKETING.md`](./frontend/MARKETING.md) → [`reference/WEBSITE_CONTENT_BRIEF.md`](./reference/WEBSITE_CONTENT_BRIEF.md)

---

## 🔍 Search cheat sheet

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
| All REST endpoints | `backend/app/routers/` + [`backend/API.md`](./backend/API.md) |
| All Pydantic schemas | `backend/app/schemas/` + [`backend/DATA_MODEL.md`](./backend/DATA_MODEL.md) §8 |
| A/B/C overlay algorithms | `A/scripts/`, `B/scripts/`, `C/scripts/` + [`pipeline/`](./pipeline/) |
| Frontend routes | `frontend/app/` + [`frontend/STRUCTURE.md`](./frontend/STRUCTURE.md) |
| Marketing components | `frontend/components/marketing/` + [`frontend/MARKETING.md`](./frontend/MARKETING.md) |
| Workspace components | `frontend/components/workspace/` + [`frontend/WORKSPACE.md`](./frontend/WORKSPACE.md) |

---

*Start with [INDEX.md](./INDEX.md) → [pipeline/OVERVIEW.md](./pipeline/OVERVIEW.md).*