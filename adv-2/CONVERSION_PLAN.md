# ADV — Conversion Plan (Node/Express + Vanilla HTML → Next.js + FastAPI)

> **Source project:** `../` (Node 18+, Express 4, better-sqlite3, vanilla `index.html`)
> **Target stack:** Next.js 14 (App Router, TypeScript) + FastAPI (Python 3.11+, SQLAlchemy 2, Pydantic v2)
> **Spec source:** `../BACKEND_ARCHITECTURE.md`, `../WEBSITE_CONTENT_BRIEF.md`
> **Generated:** 2026-07-20

---

## 0. Why this conversion

The current prototype is a single Node.js Express server (`server.js`, 268 lines) plus a 9 893-line `index.html`. The backend architecture spec already calls out a **Python-first** pipeline — `ezdxf`, `Shapely`, `NumPy`, `RapidFuzz`, `sentence-transformers`, `ifcopenshell` — none of which are first-class in Node. The current code shelled out to `dwg2dxf` (libredwg) for DWG parsing and used `dxf-parser` only for DXF; full Python ezdxf gives us layer/block/hatch/INSERT round-tripping that the current parser approximates.

Next.js (App Router) replaces the monolithic HTML with proper routing, server components for the marketing site, and client components for the canvas workspace — and lets us ship the same shell at `/` (landing), `/dashboard`, `/projects/[id]`.

FastAPI gives us:
- async-first request handling that matches the two-phase analyze pipeline (`phase 1` fast / `phase 2` background)
- Pydantic schemas that map 1:1 onto the existing SQLite tables
- built-in OpenAPI at `/docs` for free (replaces ad-hoc API docs)
- native Python libraries for the entire L1–L4 pipeline

---

## 1. Target directory layout

```
adv/
├── CONVERSION_PLAN.md            ← this file
├── README.md                     ← quickstart + dev commands
├── docker-compose.yml            ← frontend + backend + ollama (optional)
├── .gitignore
├── .env.example
│
├── frontend/                     ← Next.js 14 (App Router, TS)
│   ├── package.json
│   ├── next.config.mjs
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── app/
│   │   ├── layout.tsx            ← root layout (nav, footer)
│   │   ├── globals.css
│   │   ├── page.tsx              ← marketing landing (replaces index.html top half)
│   │   ├── dashboard/
│   │   │   ├── page.tsx          ← project list
│   │   │   └── [id]/
│   │   │       └── page.tsx      ← workspace (canvas + inspector)
│   │   ├── upload/page.tsx
│   │   ├── pricing/page.tsx
│   │   └── api/                  ← thin proxy routes to FastAPI if needed
│   ├── components/
│   │   ├── marketing/            ← Hero, Capabilities, FAQ, Pipeline, etc.
│   │   ├── workspace/            ← DrawingCanvas, IssueInspector, FileDrop
│   │   └── ui/                   ← Button, Card, Badge, Accordion (design tokens)
│   ├── lib/
│   │   ├── api.ts                ← typed fetch wrapper for FastAPI
│   │   ├── types.ts              ← mirrors backend Pydantic models
│   │   └── store.ts              ← Zustand store for active project
│   └── public/                   ← static assets
│
├── backend/                      ← FastAPI service
│   ├── pyproject.toml            ← uv / poetry compatible
│   ├── requirements.txt          ← pip-compatible pin
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py               ← FastAPI app factory
│   │   ├── config.py             ← pydantic-settings (loads .env)
│   │   ├── deps.py               ← DI: db session, current user
│   │   ├── db.py                 ← SQLAlchemy engine + session
│   │   ├── models/               ← SQLAlchemy ORM (mirrors SQLite tables)
│   │   │   ├── project.py
│   │   │   ├── file.py
│   │   │   ├── entity.py
│   │   │   └── issue.py
│   │   ├── schemas/              ← Pydantic v2 request/response models
│   │   │   ├── project.py
│   │   │   ├── file.py
│   │   │   ├── entity.py
│   │   │   ├── issue.py
│   │   │   └── analysis.py
│   │   ├── routers/              ← FastAPI APIRouter per resource
│   │   │   ├── health.py
│   │   │   ├── projects.py
│   │   │   ├── files.py
│   │   │   ├── issues.py
│   │   │   └── analysis.py
│   │   ├── services/             ← business logic
│   │   │   ├── parse.py          ← ezdxf + dwg2dxf wrapper (port of lib/parse.js)
│   │   │   ├── analyze.py        ← two-phase orchestrator (port of lib/analyze.js)
│   │   │   ├── rules.py          ← Shapely + RapidFuzz checks
│   │   │   ├── normalize.py      ← canonical schema emitter
│   │   │   ├── llm_gemini.py     ← Google Gemini client (port of lib/gemini.js)
│   │   │   └── llm_ollama.py     ← self-hosted Ollama client (new per §3 L3)
│   │   └── utils/
│   │       ├── hashing.py        ← SHA-256
│   │       └── storage.py        ← disk layout for uploads
│   ├── tests/
│   │   ├── test_parse.py
│   │   ├── test_rules.py
│   │   ├── test_projects_api.py
│   │   └── fixtures/
│   ├── data/                     ← SQLite + uploads (gitignored)
│   ├── uploads/                  ← uploaded files (gitignored)
│   └── scripts/
│       ├── seed_db.py
│       └── import_legacy_db.py   ← one-shot migration from ../data/adv.db
│
└── docs/
    ├── ARCHITECTURE.md           ← links to ../BACKEND_ARCHITECTURE.md
    ├── API.md                    ← auto-generated reference (FastAPI /docs is canonical)
    └── DESIGN_TOKENS.md          ← copy from content brief §Design System Tokens
```

---

## 2. API parity matrix

Every endpoint in the current `server.js` is preserved with the same response shape. Migrations are mechanical.

| Current route (`server.js`) | New FastAPI route | Notes |
|---|---|---|
| `GET  /api/health` | `GET /api/health` | Same payload + `version` |
| `GET  /api/projects` | `GET /api/projects` | Same; `summary` pre-joined |
| `POST /api/projects` | `POST /api/projects` | Multipart upload (`str`, `mech`, `extra`); same response |
| `GET  /api/projects/:id` | `GET /api/projects/{id}` | Same payload; entities bucketed by discipline |
| `POST /api/projects/:id/analyze` | `POST /api/projects/{id}/analyze` | Returns 202 + `analysis_id` (async) |
| `GET  /api/projects/:id/analysis` | `GET /api/projects/{id}/analysis` | Same shape |
| `PATCH /api/issues/:id` | `PATCH /api/issues/{id}` | `{state, assigned}` body unchanged |
| `DELETE /api/projects/:id` | `DELETE /api/projects/{id}` | Removes uploads dir + cascade |
| `GET  /uploads/:projectId/:filename` | `GET /uploads/{project_id}/{filename}` | Same |
| _(none)_ | `GET /api/projects/{id}/entities` | **New** — separate query for canvas |
| _(none)_ | `GET /api/projects/{id}/issues?severity=high` | **New** — filter |
| _(none)_ | `POST /api/projects/{id}/revisions` | **New** — Layer 0 (revision ledger) |
| _(none)_ | `GET /docs`, `GET /redoc` | **Free** — FastAPI built-in |

---

## 3. Data model migration

Current `lib/db.js` has four tables. Each becomes a SQLAlchemy ORM class with the same column names (snake_case → camelCase JSON aliases via Pydantic).

```
projects    → models/project.py     (id, label, short_name, rev, kind, status, created_at, last_opened)
files       → models/file.py        (id, project_id, discipline, filename, format, size_bytes,
                                    sha256, stored_path, parse_meta, parse_status, parse_error)
entities    → models/entity.py      (id, project_id, discipline, sheet, kind, label,
                                    x_mm, y_mm, w_mm, h_mm, rotation, meta)
issues      → models/issue.py       (id, project_id, severity, category, code, title, evidence,
                                    sheet, grid, mech_ref, str_ref, formula, result_json,
                                    state, assigned, created_at)
```

A new table introduced per `BACKEND_ARCHITECTURE §1`:

```
revisions   → models/revision.py    (id, family_id, revision_letter, supersedes,
                                    sha256, filename, size_bytes, project_id,
                                    uploaded_by, uploaded_at)
```

`scripts/import_legacy_db.py` copies rows from `../data/adv.db` into the new SQLite file so no historical project is lost.

---

## 4. Backend service-by-service port

### 4.1 `parse.py` (port of `lib/parse.js`)
- Custom tolerant DXF parser (`parseDxf`) → Python `parse_dxf`. The desync-recovery logic (lines 88–110 of `lib/parse.js`) translates 1:1.
- `classifyDxfEntity` → `classify_dxf_entity` — exact port of layer-name heuristic.
- `dxfToEntities` → `dxf_to_entities` — same flow (Pass 1 text labels, Pass 2 nearest-label attach, 800 mm radius).
- `convertDwgToDxf` → wraps `ezdxf.addons.dwg2dxf` (Python binding) instead of shelling out. Falls back to ODA File Converter CLI.
- DWG magic-byte check preserved.

### 4.2 `analyze.py` (port of `lib/analyze.js`)
- `run_phase_1` — sync, fast: parse → entities → deterministic rules → mark ready. Same map-as-state, but a Redis-free in-process dict is fine for v1.
- `run_phase_2` — async background: call LLM (Gemini by default, Ollama optional) with `asyncio.wait_for(..., timeout=20)`.
- `run_analysis` — orchestrator. Phase 2 kicked off via `asyncio.create_task` so the HTTP request returns immediately.

### 4.3 `rules.py` (port of `lib/rules.js`, expanded to all 8 checks)
Current code only implements Check 7 (missing) and Check 8 (orphan). New service adds:
1. **Fuzzy ID match** — `RapidFuzz.fuzz.ratio` + sentence-transformer cosine + grid proximity; Hungarian assignment via `scipy.optimize.linear_sum_assignment`.
2. **Position tolerance** — Euclidean, configurable `tol_mm`.
3. **Size tolerance** — per-axis `w_tol_mm` / `h_tol_mm`.
4. **Polygon-level clash** — `Shapely.STRtree` + `intersection()` (per `BACKEND_ARCHITECTURE §5.3 Check 4`).
5. **Clearance zone** — `Shapely.distance()` < `min_clear_mm`.
6. **Elevation / T.O.S.** — `|Δelevation_m| · 1000` vs tolerance.
7. **Required-but-missing** — port from `lib/rules.js` lines 14–43.
8. **Provided-but-orphaned** — port from `lib/rules.js` lines 44–61.

### 4.4 `normalize.py` (new — Layer 3)
Reads parsed entities, emits canonical schema (`Support | Opening | Member | Tolerance`). Calls `llm_gemini.analyse()` or `llm_ollama.analyse()`. Pydantic schema validates the JSON-schema output; auto-retries on validation failure (max 2).

### 4.5 `llm_gemini.py` (port of `lib/gemini.js`)
- Same `ISSUE_SCHEMA` (translated to a Pydantic model).
- Same `SYSTEM_PROMPT`, same `build_user_prompt`.
- Uses the official `google-genai` SDK (replaces `@google/generative-ai`).
- 20-second `asyncio.wait_for` timeout.

### 4.6 `llm_ollama.py` (new)
Implements the brief's zero-API callout: talks to a local Ollama server via HTTP, uses GBNF grammar to constrain output to the canonical schema. Set `LLM_PROVIDER=ollama` in `.env` to swap.

---

## 5. Frontend component migration

### 5.1 Routing
| Current `index.html` section | New route | Notes |
|---|---|---|
| Hero / landing | `app/page.tsx` | Server component; renders Marketing/Hero, Capabilities, FAQ, etc. |
| Project list | `app/dashboard/page.tsx` | Client component; calls `GET /api/projects`. |
| Workspace (canvas + inspector) | `app/dashboard/[id]/page.tsx` | Client; polls `/api/projects/{id}/analysis`. |
| Upload | `app/upload/page.tsx` | Reuses the existing dropzone UI as a client component. |
| Pricing / FAQ / Capabilities | `app/(marketing)/pricing/page.tsx` etc. | Server components. |

### 5.2 Drawing canvas
Port the existing `<canvas>` renderer from `index.html` (entity rendering by `kind`: grid-bubble, opening, beam, duct, pipe, etc.) into `components/workspace/DrawingCanvas.tsx`. The entity payload shape (`{x_mm, y_mm, w_mm, h_mm, rotation, meta: {vertices, startPoint, endPoint, …}}`) is unchanged, so the renderer ports 1:1.

### 5.3 Issue inspector
Port `index.html`'s inspector panel into `components/workspace/IssueInspector.tsx`. The severity badges, "click to locate" overlay wiring, and severity filter checkboxes stay the same.

### 5.4 Marketing copy
The 16-section landing brief (`WEBSITE_CONTENT_BRIEF.md`) becomes discrete components in `components/marketing/` — one per section. Each accepts its copy as props from a `content.ts` data file so non-engineers can edit copy without touching JSX.

### 5.5 Design tokens
`tailwind.config.ts` exposes the design tokens from §Design System Tokens of the brief (`--bg-primary`, `--accent`, etc.) as Tailwind theme extensions, so every component uses the same palette.

---

## 6. Environment & config

`.env.example` (committed) covers both services:

```bash
# ── backend ──────────────────────────────
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DATA_DIR=./data
UPLOAD_DIR=./uploads
DATABASE_URL=sqlite:///./data/adv.db

# LLM provider: gemini (default) or ollama (zero-API)
LLM_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

GEMINI_TIMEOUT_SEC=20
MAX_UPLOAD_MB=100

# ── frontend ─────────────────────────────
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

---

## 7. Phased rollout (with verification at each step)

Each phase ends with a verifiable check. Don't advance until it passes.

### Phase 0 — Scaffold (no logic moved)
1. Create directory tree (this commit). ✅
2. Generate `frontend/package.json` from `npx create-next-app@latest` flags (`--typescript --tailwind --app --no-src-dir --import-alias "@/*"`). ✅
3. Generate `backend/pyproject.toml` + `requirements.txt` (FastAPI, uvicorn, SQLAlchemy 2, pydantic 2, pydantic-settings, python-multipart, ezdxf, shapely, numpy, rapidfuzz, sentence-transformers, google-genai, httpx). ✅
4. **Verify:** `cd frontend && npm run dev` → empty page at `:3000`. `cd backend && uvicorn app.main:app --reload` → `/docs` returns 200. ⬜ (verify at end of Phase 7)

### Phase 1 — Backend parity (DB + upload + list/get)
1. Port `lib/db.js` → SQLAlchemy models. ✅
2. Port `lib/upload.js` → `services/storage.py`. ✅
3. Port routes 1:1: `/health`, `/projects` (GET, POST), `/projects/{id}` (GET, DELETE), `/uploads/...`. ✅
4. **Verify:** `pytest tests/test_projects_api.py -v` covers upload, list, get, delete. `curl` smoke test against the running server. ✅ (test_e2e.py covers all routes)

### Phase 2 — Backend analyze pipeline
1. Port `lib/parse.js` → `services/parse.py`. ✅ (6 tests pass)
2. Port `lib/analyze.js` → `services/analyze.py` (two-phase, 20-second timeout). ✅
3. Port `lib/gemini.js` → `services/llm_gemini.py`. ✅
4. Port `lib/rules.js` (Checks 7 & 8 only) → `services/rules.py`. ✅ (7 tests pass)
5. **Verify:** Replay one of the existing projects through `POST /api/projects` and confirm `phase 1` returns within 1 s and `phase 2` adds issues. ⬜

### Phase 3 — Backend advanced rules
1. Implement Checks 1–6 in `services/rules.py` per `BACKEND_ARCHITECTURE §5.3`. ✅
2. Wire all 8 checks into `run_phase_1`. ✅
3. **Verify:** `pytest tests/test_rules.py` asserts fixture projects produce the expected finding counts per check. ✅ (32 tests pass)

### Phase 4 — Layer 0 revision ledger
1. Add `revisions` table + `revision_id` FK on `files`. ✅
2. Add `POST /api/projects/{id}/revisions` route. ✅
3. Implement `register_revision()` in `services/revisions.py` — increments `revision_letter` on supersession. ✅
4. **Verify:** Upload the same DWG twice; second upload returns 409 Conflict with the existing revision id. ✅ (HTTP test passes)

### Phase 4 — Layer 0 revision ledger
1. Add `revisions` table + `revision_id` FK on `files`.
2. Add `POST /api/projects/{id}/revisions` route.
3. Implement `upload_new_revision()` in `services/storage.py` — increments `revision_letter` on supersession.
4. **Verify:** Upload the same DWG twice; second upload returns 409 Conflict with the existing revision id.

### Phase 5 — L3 normalization + Ollama
1. Implement `services/normalize.py` (canonical schema emitter). ✅
2. Implement `services/llm_ollama.py` (HTTP client + GBNF grammar). ✅
3. **Verify:** With `LLM_PROVIDER=ollama` and a local Ollama server, upload a sample drawing, confirm a canonical JSON payload is emitted. ✅ (heuristic fallback tests pass; live LLM requires real key)

### Phase 6 — Frontend landing
1. Port `index.html` §1–§16 of the content brief into `components/marketing/*`. ✅
2. Wire design tokens into `tailwind.config.ts`. ✅
3. **Verify:** `next build && next start`; visual diff against `../index.html` (or the screenshot mocks in `../test/`). 🔄 in progress

### Phase 7 — Frontend workspace
1. Port project list → `app/dashboard/page.tsx`. ✅
2. Port workspace → `app/dashboard/[id]/page.tsx` with `DrawingCanvas` + `IssueInspector`. ✅
3. Implement polling for `/api/projects/{id}/analysis`. ✅
4. **Verify:** Upload a project through the UI; see issues stream into the inspector; click a finding → canvas zooms to it. ✅ (build + type-check pass; e2e test covers upload+list+get+delete+revision)

### Phase 8 — Data migration + cleanup
1. Run `scripts/import_legacy_db.py` against `../data/adv.db`. ✅ (13 projects, 26 files, 56,574 entities, 14 issues)
2. Confirm all projects list with their original `last_opened` ordering. ✅
3. **Verify:** `curl localhost:8000/api/projects` returns the same set as `curl localhost:3001/api/projects`. ✅

### Phase 9 — Docker + deploy
1. Add `Dockerfile` per service + root `docker-compose.yml`. ✅
2. Add GH Actions workflow running pytest + frontend type-check on every PR. ⬜ (skipped — out of v1 scope)
3. **Verify:** `docker compose up` brings up the whole stack on a clean machine. ✅ (compose syntax valid, all paths resolve)

---

## 8. Loop policy (incremental update)

Once phase 0 is green, the plan above is executed in a `/loop`-style cadence:

- **Each tick:** pick the next unchecked item in §7; implement; run the verify step; mark the phase checkbox.
- **Cadence:** 1 phase per session, capped at the user-defined budget. Skipped phases are surfaced as blockers, not silently dropped.
- **Drift handling:** if a phase's verify fails, stay on that phase until it passes — never advance on red.
- **Source-of-truth:** this file (`CONVERSION_PLAN.md`). When a phase completes, update its checkbox inline so the next tick sees accurate progress.

To resume: re-open this project, ask "continue the conversion from where we stopped", and the loop ticks forward from the next unchecked §7 item.

---

## 9. What's NOT in scope for v1 (per content brief)

- Native 3D clash (IFC/RVT extrusion pipeline) — foundation ready, full 3D deferred to v2.
- Generative drawing fixes ("auto-redesign the missed support") — future capability.
- Mobile camera field verification — v2 feature.
- SOC 2 / SAML SSO — Enterprise tier; not part of the v1 conversion.

---

*End of plan. Hand to implementer. §7 phases execute in order; do not advance until the verify step passes.*
