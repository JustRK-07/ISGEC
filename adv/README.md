# ADV — Agentic Drawing Validator (Next.js + FastAPI conversion)

> Engineering-defensible, DWG-native, agentic drawing validation. Read the
> full spec in [`CONVERSION_PLAN.md`](./CONVERSION_PLAN.md) and
> [`../BACKEND_ARCHITECTURE.md`](../BACKEND_ARCHITECTURE.md).

## Stack

- **Frontend** — Next.js 14 (App Router, TypeScript, Tailwind)
- **Backend** — FastAPI (Python 3.11+, SQLAlchemy 2, Pydantic v2)
- **Storage** — SQLite (WAL) + on-disk uploads
- **LLM** — Google Gemini by default; swap to local Ollama via `LLM_PROVIDER=ollama`

## Quickstart

```bash
# 1. backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env  # fill in GEMINI_API_KEY if using Gemini
uvicorn app.main:app --reload --port 8000

# 2. frontend (in a second terminal)
cd frontend
npm install
npm run dev   # http://localhost:3000

# OR run both with docker compose
docker compose up
```

Backend auto-generated docs: `http://localhost:8000/docs`

## Layout

```
adv/
├── CONVERSION_PLAN.md   ← phased rollout + verification gates
├── frontend/            ← Next.js
├── backend/             ← FastAPI
├── docker-compose.yml
└── docs/                ← design tokens, API notes
```

## Migration status

See `CONVERSION_PLAN.md §7` for the phased plan. The current state of
each phase is tracked inline as ✅ / ⬜ checkboxes.
