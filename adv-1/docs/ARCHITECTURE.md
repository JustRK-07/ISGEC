# Architecture

The full pipeline architecture lives in
[`../../BACKEND_ARCHITECTURE.md`](../../BACKEND_ARCHITECTURE.md). This
document only captures the **target** layout for the Next.js + FastAPI
conversion.

## High-level

```
        ┌──────────────────────────────────────────────────────────────┐
        │                         Next.js 14                            │
        │  (App Router · TS · Tailwind · SWR · Zustand)                  │
        │                                                               │
        │  /             marketing landing (server components)           │
        │  /dashboard    project list                                   │
        │  /dashboard/:id workspace (DrawingCanvas + IssueInspector)   │
        │  /upload       multipart upload form                          │
        └────────────────────────┬──────────────────────────────────────┘
                                 │  /api/* → rewrite → FastAPI
                                 ▼
        ┌──────────────────────────────────────────────────────────────┐
        │                         FastAPI                                │
        │  /api/health, /api/projects, /api/projects/{id}                │
        │  /api/projects/{id}/analyze, /api/projects/{id}/analysis       │
        │  /api/issues/{id}, /uploads/{project_id}/{filename}            │
        │                                                               │
        │  Routers ──▶ Services ──▶ SQLAlchemy ORM ──▶ SQLite (WAL)      │
        │              │                                                │
        │              ├─▶ services/parse.py (ezdxf + libredwg)          │
        │              ├─▶ services/rules.py (Shapely + RapidFuzz)      │
        │              ├─▶ services/llm_gemini.py (google-genai)        │
        │              └─▶ services/llm_ollama.py (zero-API on-prem)    │
        └──────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
        ┌──────────────────────────────────────────────────────────────┐
        │                   Optional: Ollama (zero-API)                 │
        │     serves Qwen / Llama / DeepSeek / Mistral / Granite        │
        └──────────────────────────────────────────────────────────────┘
```

## Two-phase analyze pipeline

`POST /api/projects/{id}/analyze` triggers:

1. **Phase 1 — synchronous (< 1 s):** parse files → emit normalized entities →
   run 8 deterministic rules → persist issues → mark project `ready`. The HTTP
   request returns immediately because phase 2 is fire-and-forget.

2. **Phase 2 — background (< 20 s timeout):** call LLM (Gemini by default,
   Ollama when `LLM_PROVIDER=ollama`). Append any new findings to the issue
   set. Update the in-process analysis state so the polling endpoint
   `/api/projects/{id}/analysis` can stream progress.

The frontend polls `analysis.llmStatus` until it is `done` / `failed` /
`skipped`, then renders the merged issue list.

## Layer mapping

| BACKEND_ARCHITECTURE § | Component | This repo |
|---|---|---|
| L0 Ingestion & Revision Lock | `models/revision.py` | ✅ model scaffolded |
| L1 DWG → DXF | `services/parse.py` | ✅ ported from `lib/parse.js` |
| L2 Grid registration | `services/parse.py` (header parsing) | ✅ partial |
| L3 Normalization (LLM) | `services/llm_gemini.py`, `services/llm_ollama.py` | ✅ scaffolded |
| L4 Rule engine | `services/rules.py` | ⚠ Checks 7 & 8 complete; 1–6 stubbed |
| L5 Reporting | `components/workspace/IssueInspector.tsx` | ✅ |
