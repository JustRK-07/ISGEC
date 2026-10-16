# LLM Integration — Gemini + Ollama

> **Source:** `app/services/llm_gemini.py` (190 LOC), `app/services/llm_ollama.py` (111 LOC), `app/services/normalize.py` (236 LOC)
> **Spec:** `BACKEND_ARCHITECTURE.md §4` (Layer 3 Semantic Normalization)

This service supports **two LLM providers** — the hosted Google Gemini (default) and a self-hosted Ollama (zero-API on-prem). The provider is selected via the `LLM_PROVIDER` env var.

---

## 0. Why a local LLM (not a hosted API)

Per the security brief and FAQ #8 in `WEBSITE_CONTENT_BRIEF.md`:

> **No drawing data ever leaves your infrastructure.** All LLM inference runs locally on your hardware — Ollama, vLLM, or llama.cpp serving an open-weight model. No tokens, no rate limits, no API keys, no telemetry to third parties. Models are swappable (Qwen, Llama, DeepSeek, Mistral, Granite).

| Property | How it's achieved |
|---|---|
| **Zero third-party API calls** | Inference runs on local GPU/CPU only |
| **No API key, no quota, no telemetry** | No outbound HTTP to OpenAI/Anthropic/Google |
| **Swappable model** | Orchestration layer is model-agnostic; only the prompt + schema change |
| **Structured output is enforced, not hoped for** | JSON-schema / response_schema masks non-conforming tokens at sampling time |
| **Model can be fine-tuned later without code changes** | Same client interface |

The hosted Gemini path is preserved for **development convenience** — engineers can iterate without standing up Ollama. Production deployments are expected to set `LLM_PROVIDER=ollama`.

---

## 1. Configuration (`app/config.py`)

```python
# LLM provider: 'gemini' (default) or 'ollama' (zero-API)
llm_provider: str = Field(default="gemini")

gemini_api_key: str = ""
gemini_model: str = "gemini-2.5-flash"
gemini_timeout_sec: int = 20

ollama_base_url: str = "http://localhost:11434"
ollama_model: str = "qwen2.5:14b"
```

Set `LLM_PROVIDER=ollama` in `.env` to swap.

---

## 2. Gemini client — `app/services/llm_gemini.py`

### Public API

```python
def gemini_configured() -> bool:
    return bool(get_settings().gemini_api_key)

async def analyse_drawings(
    project_meta: dict,
    str_meta: dict,
    mech_meta: dict,
) -> list[dict]:
    """Call Gemini with a hard timeout. Returns a list of normalized issue dicts."""

async def normalize(
    system: str,
    prompt: str,
    schema: type[BaseModel],
) -> dict:
    """Call Gemini with the canonical schema as response_schema. Returns a plain
    dict (callers validate into the Pydantic model)."""
```

### Pydantic schema

```python
class IssueFromLLM(BaseModel):
    severity: Literal["high", "medium", "low", "pass"]
    category: str
    code: str
    title: str
    evidence: str
    sheet: str | None = None
    grid: str | None = None
    mech_ref: str | None = None
    str_ref: str | None = None
    formula: str | None = None

class IssuesResponse(BaseModel):
    issues: list[IssueFromLLM]
```

### SYSTEM_PROMPT (analyse_drawings)

```
You are ADV — an AEC QA/QC analyst. You read a Mechanical GA drawing and a
Structural GA drawing of the same floor and identify clashes, missing supports,
mismatched elevations, and inconsistencies between them.

You never invent data. If you cannot ground a finding in the supplied metadata,
you do not report it.

Severity rules:
- 'high'   : hard clash, missing primary support, or off-by-tolerance (>100mm) opening size/position
- 'medium' : clearance violation, orphan opening, or off-by-tolerance (>25mm and ≤100mm)
- 'low'    : cosmetic / tagging / convention mismatch
- 'pass'   : representative "all-good" baseline check (return at least 1 pass per drawing pair)

Every finding must include:
- 'severity', 'category', 'code' (short identifier like WBE-B46, OPEN-MISS, ELEV-DELTA),
  'title' (one-line), 'evidence' (1-2 sentences grounded in supplied metadata),
  'sheet' and 'grid' when applicable, 'mech_ref' / 'str_ref' tags, and a 'formula'
  (the deterministic check that confirms the finding).

Return ONLY a JSON object with an 'issues' array — no prose, no markdown fences.
```

### User prompt structure

```
PROJECT
  label:  <label>
  rev:    <rev or '—'>
  created: <ISO timestamp>

STRUCTURAL DRAWING (<filename>)
  format:  <dwg/dxf/...>
  size:    <bytes>
  parse:   <status> (<kind>)
  layers:  <top-60 layer counts>
  text:    <first 20 text labels or elevations>
  header:  <$INSUNITS and other headers>

MECHANICAL DRAWING (<filename>)
  ... (same shape)

Identify clashes, missing supports, and inconsistencies between the two drawings.
Emit a JSON object: {"issues": [...]}.
```

### Call structure

```python
import asyncio
from google import genai

client = genai.Client(api_key=settings.gemini_api_key)

async def _call():
    return await asyncio.to_thread(
        client.models.generate_content,
        model=settings.gemini_model,            # default: 'gemini-2.5-flash'
        contents=prompt,
        config={
            "system_instruction":   SYSTEM_PROMPT,
            "response_mime_type":   "application/json",
            "response_schema":      IssuesResponse.model_json_schema(),
            "temperature":          0.2,
        },
    )

result = await asyncio.wait_for(_call(), timeout=settings.gemini_timeout_sec)
text = result.text
parsed_dict = json.loads(text)
issues = parsed_dict.get("issues", [])
```

### Response normalization

```python
for it in issues:
    normalized.append({
        "severity":  str(it.get("severity") or "low").lower(),
        "category":  str(it.get("category") or "general").lower(),
        "code":      str(it.get("code") or "ADV-0000").upper()[:32],
        "title":     str(it.get("title") or "")[:200],
        "evidence":  str(it.get("evidence") or "")[:1000],
        "sheet":     it.get("sheet"),
        "grid":      it.get("grid"),
        "mech_ref":  it.get("mech_ref"),
        "str_ref":   it.get("str_ref"),
        "formula":   it.get("formula"),
    })
```

### `normalize()` (canonical schema path)

```python
async def normalize(system: str, prompt: str, schema: type[BaseModel]) -> dict:
    result = await asyncio.wait_for(
        asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_model,
            contents=prompt,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "response_schema":    schema.model_json_schema(),
                "temperature":        0.1,
            },
        ),
        timeout=settings.gemini_timeout_sec,
    )
    return json.loads(result.text)
```

`response_schema = schema.model_json_schema()` is the structured-output enforcement — Gemini's sampling masks any token that wouldn't produce valid JSON matching the schema.

---

## 3. Ollama client — `app/services/llm_ollama.py`

### Public API

```python
def ollama_configured() -> bool:
    return bool(get_settings().ollama_base_url)

async def analyse_drawings(
    project_meta: dict,
    str_meta: dict,
    mech_meta: dict,
) -> list[dict]:
    """POST a prompt to a local Ollama server, return normalized issue dicts."""

async def normalize(system: str, prompt: str) -> dict:
    """POST to a local Ollama /api/chat endpoint and return a dict matching
    the canonical schema. Used by services/normalize.py."""
```

### SYSTEM_PROMPT

```
You are ADV — an AEC QA/QC analyst running on a self-hosted LLM.
Read a Mechanical GA drawing and a Structural GA drawing of the same floor and
identify clashes, missing supports, mismatched elevations, and inconsistencies.

Return ONLY a JSON object with an 'issues' array — no prose, no markdown fences.
Each issue must include severity (high|medium|low|pass), category, code, title,
evidence, sheet, grid, mech_ref, str_ref, formula.
```

### `analyse_drawings` call structure

```python
url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
body = {
    "model":  settings.ollama_model,   # default: 'qwen2.5:14b'
    "prompt": prompt,
    "stream": False,
    "format": "json",                  # forces JSON output
}

async with httpx.AsyncClient(timeout=settings.gemini_timeout_sec * 2) as client:
    resp = await client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()

raw = data.get("response", "{}")
parsed = json.loads(raw)
issues = parsed.get("issues", [])
```

**Note**: The Ollama client uses `httpx` with **2× timeout** (40s by default) because the round-trip is synchronous from Ollama's perspective — Gemini has `asyncio.to_thread` to push to a thread.

### `normalize` call structure

```python
url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
body = {
    "model": settings.ollama_model,
    "messages": [
        {"role": "system", "content": system},
        {"role": "user",   "content": prompt},
    ],
    "stream": False,
    "format": "json",
}
# POST and parse data["message"]["content"]
```

Uses `/api/chat` instead of `/api/generate` because the normalize flow expects separate system + user messages.

### Recommended Ollama models

| Model | Size | Notes |
|---|---:|---|
| `qwen2.5:14b` | 9 GB | Default; strong structured output |
| `llama3.3:70b` | 40 GB | High quality, slow on modest hardware |
| `deepseek-v3` | varies | Strong reasoning, supports GBNF grammar |
| `mistral-large` | 70 GB | Enterprise-tuned |
| `granite-3.1:8b` | 5 GB | IBM, fast, weaker on long context |

Pick whatever runs on your hardware. The orchestration layer doesn't care.

### Optional: GBNF grammar

For production deployments that need stricter output, use Ollama's `grammar` field instead of `format: "json"`:

```python
body = {
    "model": settings.ollama_model,
    "prompt": prompt,
    "format": schema.model_json_schema(),  # JSON Schema as grammar
    "stream": False,
}
```

This gives the same structured-output enforcement as Gemini's `response_schema`.

---

## 4. Normalization orchestration — `app/services/normalize.py`

The dispatch layer that decides which provider to call.

### Canonical Pydantic models

```python
class Support(BaseModel):
    id: str
    type: Literal["restraint", "anchor", "guide", "saddle"]
    grid: str | None = None
    x_mm: float
    y_mm: float
    load_kg: float | None = None
    fluid: str | None = None

class Opening(BaseModel):
    id: str
    service: Literal["duct", "pipe", "cable-tray", "sleeve", "trench"]
    grid: str | None = None
    x: float; y: float; w: float; h: float
    elevation: float | None = None

class Member(BaseModel):
    id: str
    type: Literal["beam", "column", "brace", "truss", "joist"]
    section: str | None = None
    grid_start: str | None = None
    grid_end: str | None = None
    profile: dict[str, Any] | None = None

class Tolerance(BaseModel):
    project_default_mm: float = 25.0
    opening_size_mm: float = 10.0
    position_mm: float = 25.0
    elevation_mm: float = 50.0
    clearance_mm: float = 50.0

class NormalizedDrawing(BaseModel):
    supports: list[Support]   = Field(default_factory=list)
    openings: list[Opening]   = Field(default_factory=list)
    members: list[Member]     = Field(default_factory=list)
    tolerance: Tolerance      = Field(default_factory=Tolerance)
```

### Dispatch logic

```python
async def normalize_drawing(
    discipline: str,
    entities: list[dict],
    file_meta: dict | None = None,
    *,
    max_retries: int = 2,
) -> NormalizedDrawing:
    settings = get_settings()
    file_meta = file_meta or {}
    prompt = _build_user_prompt(discipline, entities, file_meta)
    system = SYSTEM_PROMPT.format(provider=settings.llm_provider)

    # Try the configured provider, then the other one, then heuristic fallback.
    last_error: Exception | None = None
    for provider in (settings.llm_provider, _other_provider(settings.llm_provider)):
        try:
            raw = await _call_provider(provider, system, prompt)
            return NormalizedDrawing.model_validate(raw)
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        return _heuristic_normalize(discipline, entities)


def _other_provider(current: str) -> str:
    return "ollama" if current == "gemini" else "gemini"


async def _call_provider(provider: str, system: str, prompt: str) -> dict:
    if provider == "ollama":
        if not llm_ollama.ollama_configured():
            raise RuntimeError("Ollama not configured")
        return await llm_ollama.normalize(system=system, prompt=prompt)

    if not llm_gemini.gemini_configured():
        raise RuntimeError("Gemini not configured")
    return await llm_gemini.normalize(system=system, prompt=prompt, schema=NormalizedDrawing)
```

### User prompt (capped at 200 entities)

```python
def _build_user_prompt(discipline, entities, meta):
    light = [
        {
            "id": e.get("id"),
            "kind": e.get("kind"),
            "label": e.get("label"),
            "sheet": e.get("sheet"),
            "x_mm": e.get("x_mm"),
            "y_mm": e.get("y_mm"),
            "w_mm": e.get("w_mm"),
            "h_mm": e.get("h_mm"),
            "layer": (e.get("meta") or {}).get("layer"),
        }
        for e in entities[:200]   # cap to keep prompt bounded
    ]
    return (
        f"Discipline: {discipline}\n"
        f"File metadata: {meta}\n"
        f"Entities (count={len(entities)}):\n"
        f"{light}\n\n"
        f"Emit the canonical schema."
    )
```

The 200-entity cap is the most important knob — a project can have 56k+ entities (TP-104 has 56,574), and sending them all to the LLM blows the context window. Sampling 200 keeps prompts manageable.

### Heuristic fallback

When neither Gemini nor Ollama is configured, `_heuristic_normalize` builds a `NormalizedDrawing` from the parser's `kind` field:

```python
_KIND_TO_SERVICE = {"duct": "duct", "pipe": "pipe", "opening": "duct"}
_KIND_TO_MEMBER  = {"beam": "beam", "column": "column"}

def _heuristic_normalize(discipline, entities) -> NormalizedDrawing:
    supports, openings, members = [], [], []
    for e in entities:
        kind = e.get("kind")
        x, y = e.get("x_mm"), e.get("y_mm")
        if x is None or y is None: continue
        if kind in _KIND_TO_SERVICE:
            openings.append(Opening(...))
        elif kind in _KIND_TO_MEMBER:
            members.append(Member(...))
        elif kind == "equipment":
            supports.append(Support(...))
    return NormalizedDrawing(supports=supports, openings=openings, members=members)
```

Useful for **dev environments** without API keys. Production must use a configured provider.

---

## 5. Phase 2 orchestration — `services/analyze.py:run_phase_2`

```python
async def run_phase_2(db, project_id):
    state = _STATE.get(project_id, AnalysisState())
    ...
    if not _llm_available():
        state.llm_status = "skipped"
        # emit "llm.skipped" event
        return

    state.llm_status = "running"
    emit_event("llm.started", f"Calling LLM ({settings.llm_provider}) for enrichment.")

    try:
        if settings.llm_provider == "ollama":
            coro = llm_ollama.analyse_drawings(project_meta, str_meta, mech_meta)
        else:
            coro = llm_gemini.analyse_drawings(project_meta, str_meta, mech_meta)

        llm_findings = await asyncio.wait_for(
            coro, timeout=settings.gemini_timeout_sec,
        )
    except asyncio.TimeoutError:
        llm_findings = [{ "code": "AI-TIMEOUT", "title": "LLM analysis timed out", ... }]
        state.llm_error = f"LLM timed out after {settings.gemini_timeout_sec}s"
    except Exception as exc:
        llm_findings = [{ "code": "AI-UNAVAIL", "title": "LLM analysis unavailable", ... }]
        state.llm_error = str(exc)

    _persist_issues_reconciling(db, project_id, llm_findings, source="llm")
    emit_event("llm.completed" or "llm.failed")
    ...
```

### Behaviour on each path

| Outcome | Event | LLM finding emitted? |
|---|---|---|
| LLM not configured | `llm.skipped` | no |
| 20s timeout | `llm.failed` (tone=`fail`) | yes (`AI-TIMEOUT`, severity=low) |
| LLM returns malformed | `llm.failed` | yes (`AI-UNAVAIL`, severity=low) |
| LLM returns valid | `llm.completed` (tone=`ok`) | yes (LLM's findings, reconciled) |

LLM findings are persisted via `_persist_issues_reconciling` — user state (`resolved`, `dismissed`) is preserved across re-analysis.

---

## 6. Tool-calling

The agent uses tool-calling for two side tasks (per `BACKEND_ARCHITECTURE §4.6`):

- "Look up section library for ISMC150" → returns `depth=150, flange_w=75, mass_kgm=14.9` from a local YAML/JSON library
- "Resolve elevation string `+13.150m`" → returns `13.150` as float

The actual tool-calling plumbing lives in the LLM client (Gemini's function-calling or Ollama's tool API). It's not exposed as a separate Python API in this codebase yet — it's invoked implicitly through the system prompt when needed.

---

## 7. Failure modes and recovery

| Failure | Detection | Recovery |
|---|---|---|
| `GEMINI_API_KEY` unset | `gemini_configured() → False` | `_llm_available() → False`, phase 2 skipped |
| `OLLAMA_BASE_URL` unset | `ollama_configured() → False` | same |
| Gemini quota exceeded | Exception in `asyncio.to_thread` | Emit `AI-UNAVAIL` finding |
| Ollama unreachable | `httpx.ConnectError` | same |
| LLM timeout (20s) | `asyncio.TimeoutError` | Emit `AI-TIMEOUT` finding |
| LLM returns invalid JSON | `json.JSONDecodeError` | Tries markdown fence strip fallback |
| LLM returns wrong schema | `pydantic.ValidationError` | `normalize_drawing` tries other provider, then heuristic |

---

## 8. Switching providers at runtime

```bash
# In .env:
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

Restart the FastAPI process. No code changes. The `analyze.py` orchestrator reads `settings.llm_provider` at request time and dispatches accordingly.

The two providers are not interchangeable in the strict sense — Gemini's `response_schema` enforcement is stricter than Ollama's `format: "json"` flag, so Ollama responses occasionally need retry-and-heuristic fallback. Both paths converge on the same Pydantic validation downstream.

---

## 9. What's not in the codebase yet

- **Live LLM-driven issue generation** — currently `_call_provider` returns a `NormalizedDrawing`, not raw issues. The 8 deterministic checks still do most of the heavy lifting; the LLM is consulted for borderline cases and supplementary insight.
- **Prompt Lab / Rule Builder** — referenced in the marketing brief as a "no-code required" way to add custom rules. Not implemented in this service.
- **Vision path for scanned drawings** — referenced as a secondary path for legacy paper-only archives. Out of v1 scope.

---

*For orchestration: [`SERVICES.md`](./SERVICES.md). For the full pipeline: [`ARCHITECTURE.md`](./ARCHITECTURE.md).*