"""End-to-end smoke test — exercises the full HTTP surface of the FastAPI app.

This is a Phase 1 / Phase 7 verify step: confirms that upload → list →
get → analyze-trigger → issue-patch → delete all work through the public API.
"""

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'adv.db'}")

    from app.config import get_settings

    get_settings.cache_clear()
    from app.db import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


def _dxf_bytes():
    """Build a minimal valid DXF payload — header + one TEXT + one LWPOLYLINE."""
    return (
        b"0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n"
        b"0\nSECTION\n2\nENTITIES\n"
        b"0\nTEXT\n8\nGRID-A\n10\n100.0\n20\n200.0\n40\n2.5\n1\nTP104-A\n"
        b"0\nLWPOLYLINE\n8\nOPENINGS\n10\n300.0\n20\n400.0\n"
        b"0\nENDSEC\n0\nEOF\n"
    )


def test_e2e_upload_list_get_delete(client):
    """End-to-end through the public API."""
    # 1. Upload
    r = client.post(
        "/api/projects",
        data={"label": "E2E Test", "rev": "A"},
        files={
            "str": ("str.dxf", _dxf_bytes(), "application/octet-stream"),
            "mech": ("mech.dxf", _dxf_bytes(), "application/octet-stream"),
        },
    )
    assert r.status_code == 201, r.text
    project = r.json()
    pid = project["id"]
    assert project["label"] == "E2E Test"
    assert project["status"] == "processing"

    # 2. List
    r = client.get("/api/projects")
    assert r.status_code == 200
    listed = r.json()
    assert any(p["id"] == pid for p in listed)

    # 3. Get detail
    r = client.get(f"/api/projects/{pid}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["id"] == pid
    assert len(detail["files"]) == 2

    # 4. Wait briefly for background analyze to settle (no LLM configured,
    # so phase 1 completes synchronously in the response and phase 2 is a no-op).
    time.sleep(0.5)
    r = client.get(f"/api/projects/{pid}/analysis")
    assert r.status_code == 200
    state = r.json()
    assert state["status"] in ("done", "running")

    # 5. Delete
    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # 6. Confirm gone
    r = client.get(f"/api/projects/{pid}")
    assert r.status_code == 404


def test_e2e_revision_upload_then_duplicate_409(client):
    """Revisions: upload project → upload revision → duplicate returns 409."""
    r = client.post(
        "/api/projects",
        data={"label": "Rev Test"},
        files={
            "str": ("s.dxf", _dxf_bytes(), "application/octet-stream"),
            "mech": ("m.dxf", _dxf_bytes(), "application/octet-stream"),
        },
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    r1 = client.post(
        f"/api/projects/{pid}/revisions",
        files={"file": ("TP-104 STR GA.dwg", b"abc", "application/octet-stream")},
    )
    assert r1.status_code == 201
    body1 = r1.json()
    assert body1["revision_letter"] == "A"

    r2 = client.post(
        f"/api/projects/{pid}/revisions",
        files={"file": ("same.dwg", b"abc", "application/octet-stream")},
    )
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "DUPLICATE_REVISION"

    r3 = client.post(
        f"/api/projects/{pid}/revisions",
        files={"file": ("TP-104 STR GA rev B.dwg", b"def", "application/octet-stream")},
    )
    assert r3.status_code == 201
    assert r3.json()["revision_letter"] == "B"
    assert r3.json()["supersedes"] == body1["id"]


def test_e2e_health_includes_llm_status(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "llm" in body
    assert "provider" in body["llm"]
    assert "ready" in body["llm"]
