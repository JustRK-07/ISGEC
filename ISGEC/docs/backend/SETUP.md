# Setup — Local Dev + Docker

> **Audience:** Engineers setting up the ISGEC backend for the first time.
> **Time to first run:** ~5 minutes (local), ~10 minutes (Docker).

---

## 0. Prerequisites

| Tool | Version | Required |
|---|---|---|
| Python | ≥ 3.11 | yes |
| pip | latest | yes |
| libredwg | ≥ 0.12 (provides `dwg2dxf`) | only for `.dwg` input |
| ODA File Converter | ≥ R2018 | alternative to libredwg |
| Docker + Compose | latest | optional |

The backend uses **Python ≥ 3.11** for `from __future__ import annotations`, `Mapped[...]` typed ORM, and `dict[str, Any]` builtin generics.

---

## 1. Local development setup

### 1.1. Clone

```bash
cd /path/to/the project
cd ISGEC/backend
```

### 1.2. Create venv + install

```bash
python -m venv .venv
source .venv/bin/activate     # Linux/macOS
# .venv\Scripts\activate     # Windows

pip install --upgrade pip
pip install -r requirements.txt
```

### 1.3. Configure `.env`

```bash
cp .env.example .env
# Edit .env:
```

```ini
# ── Server ──────────────────────────────
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8001

# ── Storage ─────────────────────────────
DATA_DIR=./data
UPLOAD_DIR=./uploads
DATABASE_URL=sqlite:///./data/isgec.db
MAX_UPLOAD_MB=100

# ── CORS ────────────────────────────────
CORS_ORIGINS=http://localhost:3001,http://127.0.0.1:3001

# ── LLM (pick one) ──────────────────────
# Default — hosted Google Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT_SEC=20

# OR self-hosted Ollama (zero-API)
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=qwen2.5:14b

# ── Phase 1 tuning ──────────────────────
LABEL_MATCH_RADIUS_MM=800.0
FUZZY_MATCH_THRESHOLD=0.55

# ── DWG → DXF conversion ────────────────
LIBREDWG_BIN=auto              # or /usr/local/bin/dwg2dxf
MAX_INSERT_EXPANSION=50000
```

### 1.4. Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Expected output:

```
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     Application startup complete.
2026-10-16 12:34:56 [INFO] adv: Starting ADV backend v0.1.0
2026-10-16 12:34:56 [INFO] adv:   data_dir    = data
2026-10-16 12:34:56 [INFO] adv:   upload_dir  = data/uploads
2026-10-16 12:34:56 [INFO] adv:   database    = sqlite:///./data/isgec.db
2026-10-16 12:34:56 [INFO] adv:   llm         = gemini
2026-10-16 12:34:56 [INFO] adv:   libredwg    = /usr/bin/dwg2dxf (available=True)
2026-10-16 12:34:56 [INFO] adv:   max_insert_expansion = 50000
```

### 1.5. Verify

```bash
curl http://localhost:8001/api/health
```

```json
{
  "ok": true,
  "version": "0.1.0",
  "llm": {
    "provider": "gemini",
    "ready":    true
  },
  "uptimeSec":     5,
  "dbFile":        "data/isgec.db",
  "projectCount":  0
}
```

Auto-generated docs: **<http://localhost:8001/docs>**

---

## 2. Docker setup

### 2.1. Build + run

```bash
cd ISGEC/
docker compose up --build
```

This builds two containers:
- `isgec-backend` — FastAPI on port 8001
- (Optional) `isgec-frontend` — Next.js on port 3001

### 2.2. Configure env

Either:
- Pass via `.env` in the repo root (compose reads it), OR
- Set in `docker-compose.yml` under `environment:`

### 2.3. Persistent volumes

The compose file mounts:
- `./backend/data:/data` — SQLite + uploads
- `./backend/uploads:/uploads` — uploaded files

These survive container restarts.

### 2.4. Logs

```bash
docker compose logs -f backend
```

---

## 3. Setting up libredwg (for `.dwg` input)

The backend reads `.dxf` natively (via ezdxf). For `.dwg` files (AutoCAD R13–R2018), it shells out to `dwg2dxf` from GNU libredwg.

### Linux (apt)

```bash
sudo apt-get install libredwg-bin
which dwg2dxf     # /usr/bin/dwg2dxf
```

### macOS (homebrew)

```bash
brew install libredwg
which dwg2dxf
```

### From source

```bash
git clone https://github.com/LibreDWG/libredwg.git
cd libredwg
./autogen.sh && ./configure --enable-bindings && make && sudo make install
```

### Alternative: ODA File Converter

If libredwg is unavailable, the **Stage 1** of the ISGEC pipeline (`/ISGEC/A/scripts/clean.py`) supports the ODA File Converter as a fallback. The backend's `dwg_convert.py` only looks for libredwg, so for the **web app** path, install libredwg.

### Verify

```bash
dwg2dxf --help     # should print usage
```

The `/api/health` response surfaces the resolved binary path:

```json
{ "llm": { "provider": "gemini", "ready": true }, ... }
```

To see libredwg resolution specifically, check the startup log:

```
[INFO] adv:   libredwg    = /usr/bin/dwg2dxf (available=True)
```

---

## 4. Setting up Ollama (optional, for zero-API LLM)

```bash
# Install
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull qwen2.5:14b        # 9 GB

# Start server (default port 11434)
ollama serve
```

In `.env`:

```ini
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

Restart the backend. `/api/health` will report `llm.provider="ollama"`, `llm.ready=true`.

### Choosing a model

| Model | VRAM | Notes |
|---|---:|---|
| `qwen2.5:14b` | ~10 GB | Default; good balance |
| `llama3.3:70b` | ~40 GB | Highest quality; needs beefy GPU |
| `deepseek-v3` | varies | Strong reasoning |
| `granite-3.1:8b` | ~6 GB | Fastest; weaker on long context |
| `mistral-large` | ~40 GB | Enterprise-tuned |

---

## 5. Database setup

### Auto-create on startup

Tables are created automatically by `init_db()` in the lifespan handler:

```python
async def lifespan(app: FastAPI):
    init_db()   # ← creates all tables + indexes
    yield
    ...
```

No manual migration step is needed for first run.

### Resetting the database

```bash
rm -rf data/
# Restart — init_db() will recreate everything
```

### Migrations

For schema changes, Alembic is in the dependency list but no migrations are committed. For now, the rule is: change the model → drop the DB → restart.

```bash
rm -f data/isgec.db
uvicorn app.main:app --reload
```

### Seeding demo data

```bash
python scripts/seed_db.py
```

Creates one demo project "TP-104 Mech/Str Review (demo)" with:
- 2 file rows (str.dwg + mech.dwg)
- 2 entities (OP-203 mech + OP-203 str, slightly different size)
- 1 demo issue (SIZE-DELTA, severity=medium)

Idempotent: returns early if any project exists.

---

## 6. Running tests

### All tests

```bash
pytest tests/ -v
```

### With coverage

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

### Specific file

```bash
pytest tests/test_revisions.py -v
pytest tests/test_rules_advanced.py -v
```

### End-to-end (full HTTP surface)

```bash
pytest tests/test_e2e.py -v
```

This spins up a FastAPI TestClient with isolated `tmp_path` data dir, walks upload → list → get → analyze → delete, and asserts the full lifecycle.

---

## 7. Environment variables reference

| Variable | Default | Purpose |
|---|---|---|
| `BACKEND_HOST` | `0.0.0.0` | Bind address |
| `BACKEND_PORT` | `8001` | Bind port |
| `DATA_DIR` | `./data` | SQLite + working files |
| `UPLOAD_DIR` | `./uploads` | Uploaded drawings |
| `DATABASE_URL` | `sqlite:///./data/isgec.db` | SQLAlchemy URL |
| `MAX_UPLOAD_MB` | `100` | Per-file upload cap |
| `CORS_ORIGINS` | `http://localhost:3001,...` | CSV list of allowed origins |
| `LLM_PROVIDER` | `gemini` | `gemini` \| `ollama` |
| `GEMINI_API_KEY` | `""` | Required if `LLM_PROVIDER=gemini` |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model ID |
| `GEMINI_TIMEOUT_SEC` | `20` | LLM call hard timeout |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Required if `LLM_PROVIDER=ollama` |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Ollama model tag |
| `LABEL_MATCH_RADIUS_MM` | `800.0` | (Future) nearest-text-label radius |
| `FUZZY_MATCH_THRESHOLD` | `0.55` | (Future) fuzzy match cutoff |
| `LIBREDWG_BIN` | `auto` | Path to `dwg2dxf` binary |
| `MAX_INSERT_EXPansion` | `50000` | INSERT expansion safety margin |

---

## 8. Troubleshooting

### "Address already in use" on port 8001

Another process is bound to 8001. Either stop it or change `BACKEND_PORT`:

```bash
BACKEND_PORT=8765 uvicorn app.main:app --port 8765
```

### "GEMINI_API_KEY not set"

The `/api/health` returns `llm.ready=false`. Either:
- Set `GEMINI_API_KEY` in `.env` and restart, OR
- Switch to Ollama: `LLM_PROVIDER=ollama`

Without a configured LLM, phase 2 is skipped (no enrichment findings) but phase 1 still produces deterministic rule findings.

### "libredwg binary not found"

DWG uploads will fail (DXF still works). Install libredwg:

```bash
sudo apt-get install libredwg-bin    # Linux
brew install libredwg                # macOS
```

Or pre-convert DWGs to DXF in AutoCAD and upload the DXF instead.

### "Database is locked"

SQLite locks when another process holds a write transaction. The backend uses WAL mode (set on every connection via the `_set_sqlite_pragmas` event listener) to mitigate this. If you still see locks:

```bash
# Check for orphaned write transactions
fuser data/isgec.db       # Linux
lsof data/isgec.db        # macOS
```

### Tables missing after a long-lived deploy

Run the idempotent migration manually:

```python
python -c "from app.db import init_db; init_db()"
```

### Tests failing with "no such column"

DB schema out of sync with models. Drop and recreate:

```bash
rm -f data/isgec.db tests/data/test_*.db
pytest tests/ -v
```

### LLM calls slow / failing

- Check `/api/health` for `llm.ready`
- Increase `GEMINI_TIMEOUT_SEC` for slow networks
- For Ollama: verify `ollama serve` is reachable: `curl http://localhost:11434/api/tags`

### "SQLite version too old"

ezdxf and modern SQLAlchemy need SQLite ≥ 3.35. On old systems:

```bash
sqlite3 --version    # should be ≥ 3.35
```

---

## 9. Production hardening checklist

Before deploying to production:

- [ ] Set `GEMINI_API_KEY` (or switch to Ollama) and verify `llm.ready=true` via `/api/health`
- [ ] Run behind TLS-terminating reverse proxy (nginx, Caddy, ALB)
- [ ] Set `DATA_DIR` to a persistent volume (not container-local)
- [ ] Configure `CORS_ORIGINS` to your frontend's exact origin (no wildcards)
- [ ] Set up log aggregation (loki, ELK, Datadog) — JSON logs work well
- [ ] Set up uptime monitoring (curl `/api/health` every 30s)
- [ ] If using SQLite: mount on SSD, schedule `VACUUM` weekly
- [ ] If using Postgres: connection pooling via `pgbouncer`
- [ ] Rotate `GEMINI_API_KEY` quarterly
- [ ] Document rollback procedure (drop DB, redeploy from git tag)

---

*For the architecture: [`ARCHITECTURE.md`](./ARCHITECTURE.md). For tests: [`TESTS.md`](./TESTS.md).*