# ISGEC Frontend — Next.js App

> **Source:** `ISGEC/frontend/`
> **Stack:** Next.js 14 (App Router, TypeScript) + Tailwind + Vitest

The ISGEC frontend is a Next.js application that provides the user-facing UI for uploading drawings, viewing superimposed overlays, and inspecting validation findings. It pairs with the `ISGEC/backend/` FastAPI service.

---

## 📑 Index

| File | What you'll find |
|---|---|
| **[STRUCTURE.md](./STRUCTURE.md)** | Directory layout, app routes, components, lib |
| **[MARKETING.md](./MARKETING.md)** | The 16 marketing section components (landing page) |
| **[WORKSPACE.md](./WORKSPACE.md)** | The drawing workspace (AppShell + DrawingCanvas + IssueInspector) |
| **[TESTING.md](./TESTING.md)** | Vitest setup, store/api/viewport unit tests |
| **[SETUP.md](./SETUP.md)** | Local dev, Docker, env vars |

---

## ⚡ Quick start

```bash
cd ISGEC/frontend
npm ci
npm run dev -- --hostname 0.0.0.0 --port 3001
```

Open <http://localhost:3001>.

```bash
# Tests
npm run test              # Vitest unit tests
npm run type-check        # TypeScript

# Build
npm run build
npm run start
```

---

## 🎯 What the frontend does

The frontend is a **single-page application** with three main flows:

1. **Marketing landing page** (`/`) — composed of 16 section components (Hero, Capabilities, FAQ, Pricing, etc.) matching the brief in `docs/reference/WEBSITE_CONTENT_BRIEF.md`.

2. **Upload flow** (`/upload`) — drag-and-drop upload modal for STR + MECH drawings.

3. **Workspace** (`/dashboard/{id}`) — the drawing viewer + issue inspector:
   - **`AppShell`** — outer layout (nav, status bar, chat tab)
   - **`DrawingCanvas`** — renders entities, supports zoom/pan, click-to-locate
   - **`IssueInspector`** — 4-tab findings panel matching the prototype

---

## Stack

| Layer | Choice |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript (strict) |
| Styling | Tailwind CSS (configured but disabled in `app/globals.css` so the prototype CSS from a sibling project can be used verbatim) |
| State | Zustand (`lib/store.ts`) |
| API client | Typed fetch wrapper (`lib/api.ts`) |
| Tests | Vitest + jsdom |
| Container | Multi-stage Docker build |

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8001` | FastAPI backend URL (overridable in dev) |

In Docker, set to `http://backend:8001` (compose service name).

---

## Reference

- **[STRUCTURE.md](./STRUCTURE.md)** — directory layout, file map
- `ISGEC/frontend/package.json` — dependencies + scripts
- `ISGEC/frontend/tsconfig.json` — TypeScript config
- `ISGEC/frontend/next.config.mjs` — Next.js config
- `ISGEC/frontend/Dockerfile` — production build
- `ISGEC/docs/reference/WEBSITE_CONTENT_BRIEF.md` — marketing brief the components implement