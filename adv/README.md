# ADV — Agentic Drawing Validator (Next.js + FastAPI conversion)

> Engineering-defensible, DWG-native, agentic drawing validation. Read the
> full spec in [`CONVERSION_PLAN.md`](./CONVERSION_PLAN.md) and
> [`../BACKEND_ARCHITECTURE.md`](../BACKEND_ARCHITECTURE.md).

## Stack

- **Frontend** — Next.js 14 (App Router, TypeScript). Tailwind is
  installed but disabled in `app/globals.css` so the prototype CSS
  (`../index.html`) can be used verbatim.
- **Backend** — FastAPI (Python 3.11+, SQLAlchemy 2, Pydantic v2).
  **Does not serve HTML** — JSON API only.
- **Storage** — SQLite (WAL) + on-disk uploads
- **LLM** — Google Gemini by default; swap to local Ollama via `LLM_PROVIDER=ollama`

## Quickstart

Ports 3000 / 8000 are taken by other apps on this machine, so the dev
servers run on **3001 (Next.js)** and **8001 (FastAPI)**. The defaults
in `backend/.env` already point at those ports.

```bash
# 1. backend (port 8001)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# 2. frontend (port 3001) — in a second terminal
cd frontend
npm install
PORT=3001 npm run dev   # http://localhost:3001
```

Then visit <http://localhost:3001>:

- `/`            — full marketing landing page (mirrors `../index.html`)
- `/dashboard`   — projects grid (auto-opens sign-in if not signed in)
- `/upload`      — opens the upload modal
- `/dashboard/{id}` — drawing workspace for a project

Sign-in is **demo mode**: any email + 4+ char password is accepted
(client-side state, no backend auth).

Backend auto-generated docs: `http://localhost:8001/docs`

## Layout

```
adv/
├── CONVERSION_PLAN.md   ← phased rollout + verification gates
├── frontend/            ← Next.js
│   ├── app/
│   │   ├── page.tsx         ← marketing landing (composes all sections)
│   │   ├── layout.tsx       ← root layout (fonts, metadata)
│   │   ├── globals.css      ← prototype CSS (verbatim from index.html)
│   │   ├── dashboard/
│   │   │   ├── page.tsx     ← projects grid
│   │   │   └── [id]/page.tsx ← workspace
│   │   └── upload/page.tsx  ← opens the upload modal
│   ├── components/
│   │   ├── marketing/       ← 16 section components + Nav + Footer
│   │   ├── auth/            ← SignInModal
│   │   ├── upload/          ← UploadModal
│   │   └── workspace/       ← AppShell, DrawingCanvas, IssueInspector
│   └── lib/
│       ├── api.ts           ← typed FastAPI client
│       └── store.ts         ← Zustand stores (session, projects, modals)
├── backend/             ← FastAPI
├── docker-compose.yml
└── docs/                ← design tokens, API notes
```

## Migration status

See `CONVERSION_PLAN.md §7` for the phased plan. The current state of
each phase is tracked inline as ✅ / ⬜ checkboxes.
