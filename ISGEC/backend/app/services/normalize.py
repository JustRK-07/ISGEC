"""Layer 3 — Semantic Normalization (BACKEND_ARCHITECTURE §4).

The deterministic rules in `services/rules.py` work on raw extracted entities.
The L3 layer collapses firm-specific naming chaos into a single canonical schema
(Support | Opening | Member | Tolerance). Downstream consumers (the rule
engine, the UI inspector, the audit log) read from this canonical form.

The actual LLM call is delegated to `services/llm_gemini.py` (hosted) or
`services/llm_ollama.py` (self-hosted, zero-API). Both clients return the same
dict shape so callers don't care which is active.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.services import llm_gemini, llm_ollama


# --------------------------------------------------------------------------- #
# Canonical schema (BACKEND_ARCHITECTURE §4.2)
# --------------------------------------------------------------------------- #


class Support(BaseModel):
    id: str
    type: str = Field(pattern=r"^(restraint|anchor|guide|saddle)$")
    grid: str | None = None
    x_mm: float
    y_mm: float
    load_kg: float | None = None
    fluid: str | None = None


class Opening(BaseModel):
    id: str
    service: str = Field(pattern=r"^(duct|pipe|cable-tray|sleeve|trench)$")
    grid: str | None = None
    x: float
    y: float
    w: float
    h: float
    elevation: float | None = None


class Member(BaseModel):
    id: str
    type: str = Field(pattern=r"^(beam|column|brace|truss|joist)$")
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
    supports: list[Support] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    members: list[Member] = Field(default_factory=list)
    tolerance: Tolerance = Field(default_factory=Tolerance)


SYSTEM_PROMPT = """You are ADV — an AEC drawing normalizer running on a {provider} LLM.

Read the supplied DWG entity metadata (layers, text labels, geometry in mm) and
emit a JSON object matching the canonical schema:
{{
  "supports":  [{{"id": "...", "type": "restraint|anchor|guide|saddle", "grid": "...", "x_mm": ..., "y_mm": ..., "load_kg": ..., "fluid": "..."}}],
  "openings":  [{{"id": "...", "service": "duct|pipe|cable-tray|sleeve|trench", "grid": "...", "x": ..., "y": ..., "w": ..., "h": ..., "elevation": ...}}],
  "members":   [{{"id": "...", "type": "beam|column|brace|truss|joist", "section": "...", "grid_start": "...", "grid_end": "...", "profile": {{...}}}}],
  "tolerance": {{"project_default_mm": 25, "opening_size_mm": 10, "position_mm": 25, "elevation_mm": 50, "clearance_mm": 50}}
}}

Rules:
- Collapse firm-specific tags (F11WE, TP4BM101, M-OP-203, etc.) onto the canonical taxonomy.
- Coordinates are in mm (already converted from $INSUNITS).
- If you cannot ground a value, omit it (use null, don't invent).
- Return ONLY the JSON object — no prose, no markdown fences."""


def _build_user_prompt(
    discipline: str, entities: list[dict], meta: dict[str, Any]
) -> str:
    """Compose the per-drawing user prompt.

    `entities` should be the normalized entity rows (already produced by
    services/parse.dxf_to_entities). Only relevant fields are forwarded —
    we don't ship the full `meta` JSON to the LLM.
    """
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
        for e in entities[:200]  # cap to keep prompt bounded
    ]
    return (
        f"Discipline: {discipline}\n"
        f"File metadata: {meta}\n"
        f"Entities (count={len(entities)}):\n"
        f"{light}\n\n"
        f"Emit the canonical schema."
    )


async def normalize_drawing(
    discipline: str,
    entities: list[dict],
    file_meta: dict[str, Any] | None = None,
    *,
    max_retries: int = 2,
) -> NormalizedDrawing:
    """Call the configured LLM and return a validated NormalizedDrawing.

    Falls back to a heuristic-only NormalizedDrawing derived from the parsed
    entities when no LLM is configured — useful for dev environments without
    Gemini keys or local Ollama.
    """
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
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue

    if last_error is not None:
        # Fall back to heuristic — better than nothing for dev.
        return _heuristic_normalize(discipline, entities)


def _other_provider(current: str) -> str:
    return "ollama" if current == "gemini" else "gemini"


async def _call_provider(provider: str, system: str, prompt: str) -> dict:
    """Dispatch to the active provider. Returns a dict matching NormalizedDrawing."""
    if provider == "ollama":
        if not llm_ollama.ollama_configured():
            raise RuntimeError("Ollama not configured")
        # The Ollama client returns a list of issues-shaped dicts; we don't
        # reuse it here — Ollama normalisation talks to a different endpoint
        # (/api/chat with format=json) configured for the canonical schema.
        return await llm_ollama.normalize(system=system, prompt=prompt)

    if not llm_gemini.gemini_configured():
        raise RuntimeError("Gemini not configured")
    return await llm_gemini.normalize(system=system, prompt=prompt, schema=NormalizedDrawing)


# --------------------------------------------------------------------------- #
# Heuristic fallback — emit a canonical schema from already-classified entities
# without consulting an LLM. Used when neither provider is configured.
# --------------------------------------------------------------------------- #


# Map our parser's `kind` → canonical schema element
_KIND_TO_SERVICE = {
    "duct": "duct",
    "pipe": "pipe",
    "opening": "duct",  # default opening to duct service
}
_KIND_TO_MEMBER = {
    "beam": "beam",
    "column": "column",
}


def _heuristic_normalize(discipline: str, entities: list[dict]) -> NormalizedDrawing:
    supports: list[Support] = []
    openings: list[Opening] = []
    members: list[Member] = []
    for e in entities:
        kind = e.get("kind")
        x = e.get("x_mm")
        y = e.get("y_mm")
        if x is None or y is None:
            continue
        if kind in _KIND_TO_SERVICE:
            openings.append(
                Opening(
                    id=e.get("id") or "",
                    service=_KIND_TO_SERVICE[kind],
                    grid=e.get("sheet"),
                    x=x,
                    y=y,
                    w=e.get("w_mm") or 0.0,
                    h=e.get("h_mm") or 0.0,
                )
            )
        elif kind in _KIND_TO_MEMBER:
            members.append(
                Member(
                    id=e.get("id") or "",
                    type=_KIND_TO_MEMBER[kind],
                )
            )
        elif kind == "equipment":
            supports.append(
                Support(
                    id=e.get("id") or "",
                    type="restraint",
                    grid=e.get("sheet"),
                    x_mm=x,
                    y_mm=y,
                )
            )
    return NormalizedDrawing(
        supports=supports,
        openings=openings,
        members=members,
    )
