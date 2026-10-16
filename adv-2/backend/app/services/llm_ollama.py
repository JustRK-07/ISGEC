"""Self-hosted Ollama client — implements the brief's zero-API callout.

When `LLM_PROVIDER=ollama`, this module replaces llm_gemini.analyse_drawings().
All inference runs locally against an Ollama server (or any compatible
OpenAI-shape endpoint) — no data leaves the network.

Wired up in `analyze.py` after Phase 5 of the conversion plan.
"""

from __future__ import annotations

import json

import httpx

from app.config import get_settings

SYSTEM_PROMPT = """You are ADV — an AEC QA/QC analyst running on a self-hosted LLM.
Read a Mechanical GA drawing and a Structural GA drawing of the same floor and
identify clashes, missing supports, mismatched elevations, and inconsistencies.

Return ONLY a JSON object with an 'issues' array — no prose, no markdown fences.
Each issue must include severity (high|medium|low|pass), category, code, title,
evidence, sheet, grid, mech_ref, str_ref, formula."""


def ollama_configured() -> bool:
    return bool(get_settings().ollama_base_url)


async def analyse_drawings(
    project_meta: dict, str_meta: dict, mech_meta: dict
) -> list[dict]:
    """POST a prompt to a local Ollama server, return normalized issue dicts."""
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"PROJECT: {project_meta.get('label')} (rev {project_meta.get('rev') or '—'})\n"
        f"STR DRAWING: {str_meta.get('filename')}\n"
        f"  layers: {str_meta.get('layers') or str_meta.get('layerCandidates') or []}\n"
        f"  text:   {(str_meta.get('textLabels') or str_meta.get('elevations') or [])[:20]}\n"
        f"MECH DRAWING: {mech_meta.get('filename')}\n"
        f"  layers: {mech_meta.get('layers') or mech_meta.get('layerCandidates') or []}\n"
        f"  text:   {(mech_meta.get('textLabels') or mech_meta.get('elevations') or [])[:20]}\n"
    )

    body = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=settings.gemini_timeout_sec * 2) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

    raw = data.get("response", "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Ollama returned non-JSON: {raw[:200]}") from e

    issues = parsed.get("issues", [])
    return [
        {
            "severity": str(it.get("severity") or "low").lower(),
            "category": str(it.get("category") or "general").lower(),
            "code": str(it.get("code") or "ADV-0000").upper()[:32],
            "title": str(it.get("title") or "")[:200],
            "evidence": str(it.get("evidence") or "")[:1000],
            "sheet": it.get("sheet"),
            "grid": it.get("grid"),
            "mech_ref": it.get("mech_ref"),
            "str_ref": it.get("str_ref"),
            "formula": it.get("formula"),
        }
        for it in issues
    ]


# --------------------------------------------------------------------------- #
# L3 normalization entry point — emits canonical schema (BACKEND_ARCHITECTURE §4)
# --------------------------------------------------------------------------- #


async def normalize(system: str, prompt: str) -> dict:
    """POST to a local Ollama /api/chat endpoint and return a dict matching
    the canonical schema. Used by services/normalize.py."""
    settings = get_settings()
    if not ollama_configured():
        raise RuntimeError("Ollama not configured — set OLLAMA_BASE_URL")

    body = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
    }
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    async with httpx.AsyncClient(timeout=settings.gemini_timeout_sec * 2) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
    raw = data.get("message", {}).get("content", "{}")
    return json.loads(raw)
