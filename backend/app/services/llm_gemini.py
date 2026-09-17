"""Google Gemini client — port of lib/gemini.js using google-genai SDK."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings


# Structured-output schema we ask Gemini to satisfy. Pydantic v2 generates
# the JSON schema dict for us, so the LLM call uses the same model as the
# internal validation.
class IssueFromLLM(BaseModel):
    severity: str = Field(pattern=r"^(high|medium|low|pass)$")
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


SYSTEM_PROMPT = """You are ADV — an AEC QA/QC analyst. You read a Mechanical GA drawing and a
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

Return ONLY a JSON object with an 'issues' array — no prose, no markdown fences."""


def gemini_configured() -> bool:
    return bool(get_settings().gemini_api_key)


def _build_user_prompt(project_meta: dict, str_meta: dict, mech_meta: dict) -> str:
    from datetime import datetime

    return f"""PROJECT
  label:  {project_meta.get('label')}
  rev:    {project_meta.get('rev') or '—'}
  created: {datetime.fromtimestamp(project_meta['createdAt'] / 1000).isoformat()}

STRUCTURAL DRAWING ({str_meta.get('filename')})
  format:  {str_meta.get('format')}
  size:    {str_meta.get('sizeBytes')} bytes
  parse:   {str_meta.get('parseStatus')} ({str_meta.get('kind')})
  layers:  {json.dumps(str_meta.get('layers') or str_meta.get('layerCandidates') or [])}
  text:    {json.dumps((str_meta.get('textLabels') or str_meta.get('elevations') or [])[:20])}
  header:  {json.dumps(str_meta.get('header') or {})}

MECHANICAL DRAWING ({mech_meta.get('filename')})
  format:  {mech_meta.get('format')}
  size:    {mech_meta.get('sizeBytes')} bytes
  parse:   {mech_meta.get('parseStatus')} ({mech_meta.get('kind')})
  layers:  {json.dumps(mech_meta.get('layers') or mech_meta.get('layerCandidates') or [])}
  text:    {json.dumps((mech_meta.get('textLabels') or mech_meta.get('elevations') or [])[:20])}
  header:  {json.dumps(mech_meta.get('header') or {})}

Identify clashes, missing supports, and inconsistencies between the two drawings.
Emit a JSON object: {{"issues": [...]}}."""


async def analyse_drawings(
    project_meta: dict,
    str_meta: dict,
    mech_meta: dict,
) -> list[dict]:
    """Call Gemini with a hard timeout. Returns a list of normalized issue dicts."""
    settings = get_settings()
    if not gemini_configured():
        raise RuntimeError("GEMINI_API_KEY not set — configure .env first")

    # Lazy import so the module loads even when the SDK isn't installed
    try:
        from google import genai  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError("google-genai SDK not installed") from e

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = _build_user_prompt(project_meta, str_meta, mech_meta)

    async def _call() -> Any:
        return await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_model,
            contents=prompt,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "response_schema": IssuesResponse.model_json_schema(),
                "temperature": 0.2,
            },
        )

    result = await asyncio.wait_for(_call(), timeout=settings.gemini_timeout_sec)
    text = result.text

    parsed_dict: dict[str, Any]
    try:
        parsed_dict = json.loads(text)
    except json.JSONDecodeError:
        cleaned = text.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        parsed_dict = json.loads(cleaned)

    issues = parsed_dict.get("issues", [])
    if not isinstance(issues, list):
        raise RuntimeError("Gemini response is not a list of issues")

    normalized: list[dict] = []
    for it in issues:
        normalized.append(
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
        )
    return normalized


# --------------------------------------------------------------------------- #
# L3 normalization entry point — emits canonical schema (BACKEND_ARCHITECTURE §4)
# --------------------------------------------------------------------------- #


async def normalize(system: str, prompt: str, schema: type[BaseModel]) -> dict:
    """Call Gemini with the canonical schema as response_schema. Returns a
    plain dict (callers validate into the Pydantic model)."""
    import asyncio

    settings = get_settings()
    if not gemini_configured():
        raise RuntimeError("GEMINI_API_KEY not set — configure .env first")

    try:
        from google import genai  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError("google-genai SDK not installed") from e

    client = genai.Client(api_key=settings.gemini_api_key)

    def _call() -> Any:
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "response_schema": schema.model_json_schema(),
                "temperature": 0.1,
            },
        )

    result = await asyncio.wait_for(asyncio.to_thread(_call), timeout=settings.gemini_timeout_sec)
    text = result.text
    return json.loads(text)
