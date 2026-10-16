"""Tests for the L3 normalization service (canonical schema emitter)."""

import pytest

from app.services import normalize


def _entity(
    id_,
    kind,
    *,
    label=None,
    x=0.0,
    y=0.0,
    w=None,
    h=None,
    sheet="0001",
):
    return {
        "id": id_,
        "project_id": "p",
        "discipline": "mech",
        "sheet": sheet,
        "kind": kind,
        "label": label,
        "x_mm": x,
        "y_mm": y,
        "w_mm": w,
        "h_mm": h,
        "rotation": 0.0,
        "meta": {"layer": "MIXED"},
    }


def test_canonical_schema_validates_empty_drawing():
    """Pydantic should accept an empty NormalizedDrawing."""
    nd = normalize.NormalizedDrawing()
    assert nd.supports == []
    assert nd.openings == []
    assert nd.members == []
    assert nd.tolerance.project_default_mm == 25.0


def test_canonical_schema_rejects_invalid_support_type():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        normalize.Support(id="s1", type="invalid", x_mm=0, y_mm=0)


def test_canonical_schema_rejects_invalid_opening_service():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        normalize.Opening(id="o1", service="garbage", x=0, y=0, w=0, h=0)


@pytest.mark.asyncio
async def test_normalize_falls_back_to_heuristic_when_no_llm_configured(
    monkeypatch,
):
    """With neither Gemini nor Ollama configured, normalize_drawing returns a
    heuristic NormalizedDrawing derived from the parsed entities."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")

    from app.config import get_settings

    get_settings.cache_clear()

    entities = [
        _entity("m1", "opening", label="OP-1", x=1000, y=2000, w=300, h=200),
        _entity("m2", "duct", label="DUCT-A", x=2000, y=1000, w=400, h=300),
        _entity("m3", "beam", label="BM-1", x=500, y=500),
        _entity("m4", "equipment", label="AHU-1", x=3000, y=3000),
        _entity("m5", "pipe", label="P-1", x=4000, y=4000),
    ]

    nd = await normalize.normalize_drawing("mech", entities)
    assert len(nd.openings) == 3  # opening + duct + pipe → all routed to openings
    assert len(nd.members) == 1  # beam
    assert len(nd.supports) == 1  # equipment
    # Opening services are mapped from parser kind
    services = sorted(o.service for o in nd.openings)
    assert services == ["duct", "duct", "pipe"]


@pytest.mark.asyncio
async def test_normalize_handles_empty_entities(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    from app.config import get_settings

    get_settings.cache_clear()

    nd = await normalize.normalize_drawing("str", [])
    assert nd.openings == []
    assert nd.members == []
    assert nd.supports == []
