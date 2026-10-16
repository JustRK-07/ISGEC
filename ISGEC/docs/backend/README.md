# ISGEC Backend — Documentation

> **Agentic Drawing Validator — ISGEC edition.**
> A FastAPI service that validates Mechanical ↔ Structural GA drawings by reading native DWG files, aligning them via labeled gridlines, and running eight deterministic checks plus an optional LLM enrichment pass.

This folder contains the documentation for `ISGEC/backend/`. The README in the parent directory has the quickstart; this folder is the **reference manual**.

---

## 📑 Index

| File | What you'll find |
|---|---|
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | The 6-layer pipeline (L0 Ingestion → L5 Reporting), request lifecycle, two-phase analyzer |
| **[DATA_MODEL.md](./DATA_MODEL.md)** | Every SQLAlchemy table, columns, relationships, indices, JSON shape contracts |
| **[API.md](./API.md)** | Every REST endpoint — method, path, request/response shape, status codes |
| **[SERVICES.md](./SERVICES.md)** | Business-logic services — `parse`, `rules`, `analyze`, `normalize`, `dwg_convert`, `revisions`, `events`, `llm_gemini`, `llm_ollama` |
| **[RULES.md](./RULES.md)** | All 8 deterministic checks — formula, severity thresholds, code prefixes, scoring |
| **[LLM.md](./LLM.md)** | Gemini + Ollama clients, prompt structure, response schemas, the zero-API callout |
| **[REVISIONS.md](./REVISIONS.md)** | Layer 0 revision ledger — SHA-256 dedupe, family chain, `revision_letter` increment |
| **[EVENTS.md](./EVENTS.md)** | Append-only event log — categories, tones, dedupe keys, `aggregate_checks` |
| **[SETUP.md](./SETUP.md)** | Local dev + Docker setup, environment, troubleshooting |
| **[TESTS.md](./TESTS.md)** | pytest suite layout, fixtures, test helpers |

---

## 🏗️ At a glance

```
ISGEC/backend/
├── app/
│   ├── main.py             FastAPI app factory, CORS, lifespan
│   ├── config.py           pydantic-settings — 12 setting groups
│   ├── db.py               SQLAlchemy engine + WAL + foreign_keys pragma
│   ├── deps.py             get_db() FastAPI dependency
│   │
│   ├── models/             6 ORM classes (Project, File, Entity, Issue, Revision, ProjectEvent)
│   ├── schemas/            Pydantic v2 request/response models
│   ├── routers/            6 FastAPI routers (health, projects, analysis, issues, revisions, files)
│   ├── services/           9 business-logic modules
│   └── utils/              hashing + storage helpers
│
├── tests/                  pytest suite — 9 files, ~1,540 LOC
│   └── fixtures/           tp104_mech.dxf, tp104_str.dxf (real drawings)
│
├── scripts/
│   └── seed_db.py          demo project seeder
│
├── Dockerfile              python:3.11-slim, exposes 8001
├── requirements.txt        15 packages
├── pyproject.toml          Python ≥3.11, dev deps (pytest, ruff, mypy)
└── docs/                   ← you are here
```

**5,559 lines across 35 files** (services: 3,160 / tests: 1,540 / routers: 619 / models: 240 / other).

---

## 🎯 What this service does, in one paragraph

It reads a **Mechanical GA** drawing (`.dwg` or `.dxf`) and a **Structural GA** drawing of the same floor and validates that every support, opening, and penetration required by Mech is actually provided by Str — with the correct size, at the correct position, with the correct clearance, and without colliding with a structural member. Every finding is grounded to a **sheet**, a **grid intersection**, an **element**, and an **exact formula**. The pipeline runs **100% on-prem** behind a **self-hosted local LLM** when `LLM_PROVIDER=ollama` — no third-party API is ever called.

```
   L0            L1            L2            L3              L4
INGESTION →   DWG → DXF   →  GRID / COORD → NORMALISATION →  RULES    →  L5 REPORT
+ REVISION   ENTITY         REGISTRATION    (LOCAL LLM)    (DETERMINISTIC)
LEDGER        EXTRACT
```

**Core principle:** *reading* (L1-L3) is probabilistic. *Checking* (L4) is exact. Findings are deterministic, not confidence-scored.

See **[ARCHITECTURE.md](./ARCHITECTURE.md)** for the full pipeline specification.

---

## ⚡ Quickstart

```bash
# 1. Install
cd ISGEC/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env: set GEMINI_API_KEY=...  (or LLM_PROVIDER=ollama)

# 3. Run
uvicorn app.main:app --host 0.0.0.0 --port 8001

# 4. Verify
curl http://localhost:8001/api/health
# → {"ok": true, "version": "0.1.0", "llm": {"provider": "gemini", "ready": true}, ...}

# 5. Tests
pytest tests/ -v
```

Full setup details, environment variables, and Docker instructions → **[SETUP.md](./SETUP.md)**.

---

## 📚 Source-of-truth references

This service implements every layer of the design documents in [`../reference/`](../reference/):

- **[`BACKEND_ARCHITECTURE.md`](../reference/BACKEND_ARCHITECTURE.md)** — 6-layer pipeline spec, every algorithm cited
- **[`WEBSITE_CONTENT_BRIEF.md`](../reference/WEBSITE_CONTENT_BRIEF.md)** — product positioning, capabilities
- `CONVERSION_PLAN.md` (planned) — phased migration plan

When the design docs and the code disagree, **the design docs win** — file an issue and update the code.