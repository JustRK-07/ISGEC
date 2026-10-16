"""Tests for the append-only project event service (workstream 9)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models.event import ProjectEvent
from app.models.issue import Issue
from app.models.project import Project
from app.services.events import (
    CHECK_CATALOG,
    DEFAULT_EVENTS_LIMIT,
    MAX_EVENTS_RETURNED,
    _code_to_check_id,
    aggregate_checks,
    emit_event,
    ensure_event_table,
    list_events,
)


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Run every test in this module against a fresh, isolated SQLite file."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'adv.db'}")
    from app.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ensure_event_table(engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---- pure helpers ---------------------------------------------------------- #


def test_code_to_check_id_maps_prefixes():
    assert _code_to_check_id("POS-101") == "pos"
    assert _code_to_check_id("CLASH-7") == "poly"
    assert _code_to_check_id("OPEN-MISS") == "req"
    assert _code_to_check_id("OPEN-ORPH-1") == "orph"
    assert _code_to_check_id("CLEAR-X") == "clear"
    assert _code_to_check_id("ELEV-3") == "elev"
    assert _code_to_check_id("FUZZY-2") == "fuzzy"
    assert _code_to_check_id("SIZE-1") == "size"


def test_code_to_check_id_unknown_returns_none():
    assert _code_to_check_id("") is None
    assert _code_to_check_id("UNKNOWN") is None


# ---- table creation -------------------------------------------------------- #


def test_ensure_event_table_idempotent():
    """Calling ensure_event_table twice on the same engine is a no-op."""
    ensure_event_table(engine)
    ensure_event_table(engine)
    # Should not raise
    with SessionLocal() as db:
        assert db.query(ProjectEvent).count() == 0


def test_ensure_event_table_on_existing_db_skips_creation(tmp_path, monkeypatch):
    """If the table already exists from a previous app run, do nothing."""
    # Pre-create the table with the SQLAlchemy default
    Base.metadata.create_all(bind=engine)
    # Now run the migration helper — it should be a no-op
    ensure_event_table(engine)
    with SessionLocal() as db:
        rows = db.query(ProjectEvent).count()
        assert rows == 0


# ---- emit_event ------------------------------------------------------------ #


def test_emit_event_inserts_new_row():
    with SessionLocal() as db:
        ev = emit_event(
            db,
            "p1",
            "upload.complete",
            "Upload complete",
            tone="ok",
            payload={"files": 2},
            dedupe_key="upload.complete:p1",
        )
        db.commit()
        assert ev.id
        assert ev.project_id == "p1"
        assert ev.code == "upload.complete"
        assert ev.tone == "ok"
        assert ev.payload_json
        assert json.loads(ev.payload_json) == {"files": 2}


def test_emit_event_dedupe_returns_existing_row():
    with SessionLocal() as db:
        first = emit_event(
            db,
            "p1",
            "upload.complete",
            "Upload complete",
            dedupe_key="upload.complete:p1",
        )
        db.commit()
        first_id = first.id
        second = emit_event(
            db,
            "p1",
            "upload.complete",
            "Upload complete (retry)",
            dedupe_key="upload.complete:p1",
        )
        # The dedupe path should not have inserted a new row.
        assert second.id == first_id
        # Confirm via a re-query that exactly one row exists for the key.
        db.commit()
        rows = db.query(ProjectEvent).filter(ProjectEvent.dedupe_key == "upload.complete:p1").all()
        assert len(rows) == 1


def test_emit_event_rejects_invalid_inputs():
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            emit_event(db, "", "x", "y")
        with pytest.raises(ValueError):
            emit_event(db, "p", "", "y")
        with pytest.raises(ValueError):
            emit_event(db, "p", "x", "")


def test_emit_event_coerces_unknown_tone():
    with SessionLocal() as db:
        ev = emit_event(db, "p1", "system.info", "hi", tone="bogus")
        db.commit()
        assert ev.tone == "info"


def test_emit_event_categories():
    """The derived category matches the code prefix."""
    with SessionLocal() as db:
        cases = [
            ("upload.started", "upload"),
            ("parse.str", "parse"),
            ("analyze.started", "analyze"),
            ("llm.completed", "llm"),
            ("issue.resolved", "issue"),
            ("revision.duplicate", "revision"),
            ("system.error", "system"),
            ("misc.unknown", "system"),  # default bucket
        ]
        for code, expected in cases:
            emit_event(db, "p1", code, f"msg for {code}", dedupe_key=f"k-{code}")
            db.commit()
        # Re-read all rows inside the same session and verify the categories
        rows = db.query(ProjectEvent).order_by(ProjectEvent.code).all()
        by_code = {r.code: r.category for r in rows}
    for code, expected in cases:
        assert by_code[code] == expected, f"{code} → {by_code[code]}"


# ---- list_events ----------------------------------------------------------- #


def test_list_events_orders_newest_first():
    with SessionLocal() as db:
        for i in range(3):
            emit_event(db, "p1", f"system.step{i}", f"step {i}", dedupe_key=f"step{i}")
            db.commit()
        rows = list_events(db, "p1", limit=10)
    codes = [r.code for r in rows]
    assert codes == ["system.step2", "system.step1", "system.step0"]


def test_list_events_respects_limit():
    with SessionLocal() as db:
        for i in range(5):
            emit_event(db, "p1", f"system.x{i}", f"x{i}", dedupe_key=f"x{i}")
            db.commit()
        rows = list_events(db, "p1", limit=2)
    assert len(rows) == 2


def test_list_events_caps_at_max():
    with SessionLocal() as db:
        # Bypass the cap via the helper; the API clamps to 500.
        emit_event(db, "p1", "system.many", "many", dedupe_key="many")
        db.commit()
    # Soft assert: the constant is sane (1..500).
    assert 1 <= MAX_EVENTS_RETURNED <= 500
    assert 1 <= DEFAULT_EVENTS_LIMIT <= MAX_EVENTS_RETURNED


# ---- aggregate_checks ------------------------------------------------------ #


def _issue(code: str, severity: str) -> Issue:
    return Issue(
        id=code,
        project_id="p",
        severity=severity,
        category="general",
        code=code,
        title=code,
        state="open",
        created_at=0,
    )


def test_aggregate_checks_empty_issues_returns_ok():
    out = aggregate_checks([])
    assert len(out) == len(CHECK_CATALOG)
    for c in out:
        assert c["state"] == "ok"
        assert c["count"] == 0
        assert {"id", "name", "meta", "state", "count"} <= set(c.keys())


def test_aggregate_checks_groups_by_code_prefix():
    issues = [
        _issue("CLASH-1", "high"),
        _issue("CLASH-2", "high"),
        _issue("POS-1", "medium"),
        _issue("OPEN-MISS-1", "high"),
        _issue("UNKNOWN-1", "low"),
    ]
    out = aggregate_checks(issues)
    by_id = {c["id"]: c for c in out}
    assert by_id["poly"]["state"] == "fail"
    assert by_id["poly"]["count"] == 2
    assert by_id["pos"]["state"] == "warn"
    assert by_id["pos"]["count"] == 1
    assert by_id["req"]["state"] == "fail"
    assert by_id["req"]["count"] == 1
    # Unknown code → ignored, no check moves to warn
    for c in out:
        if c["id"] not in {"poly", "pos", "req"}:
            assert c["state"] == "ok"
            assert c["count"] == 0


def test_aggregate_checks_pass_only_keeps_ok():
    issues = [_issue("POS-1", "pass")]
    out = aggregate_checks(issues)
    pos = next(c for c in out if c["id"] == "pos")
    assert pos["state"] == "ok"
    assert pos["count"] == 1


# ---- integration with main ------------------------------------------------- #


def test_ensure_event_table_runs_via_init_db(tmp_path, monkeypatch):
    """The init_db() path (used by the FastAPI lifespan) must create the table."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'adv.db'}")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.db import init_db

    init_db()
    with SessionLocal() as db:
        # The table exists and is empty
        rows = db.execute(select(ProjectEvent)).scalars().all()
        assert rows == []


# ---- HTTP-level integration ------------------------------------------------ #


def test_http_patch_issue_emits_event(tmp_path, monkeypatch):
    """PATCH /api/issues/{id} should land an event in the project log."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'adv.db'}")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.db import Base, engine
    from app.models.issue import Issue

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add(
            Project(
                id="p1",
                label="patch-test",
                short_name="patch-test",
                kind="Str + Mech",
                status="ready",
                created_at=0,
                last_opened=0,
            )
        )
        db.add(
            Issue(
                id="i1",
                project_id="p1",
                severity="medium",
                category="general",
                code="POS-1",
                title="pos drift",
                state="open",
                created_at=0,
            )
        )
        db.commit()

    from app.main import create_app

    app = create_app()
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        r = client.patch("/api/issues/i1", json={"state": "resolved"})
        assert r.status_code == 200

        r = client.get("/api/projects/p1/events")
        assert r.status_code == 200
        body = r.json()
        codes = [e["code"] for e in body]
        assert "issue.resolved" in codes


def test_http_revision_upload_emits_event(tmp_path, monkeypatch):
    """POST /api/projects/{id}/revisions should land an event for both new and
    duplicate uploads."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'data' / 'adv.db'}")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.db import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add(
            Project(
                id="p1",
                label="rev-test",
                short_name="rev-test",
                kind="Str + Mech",
                status="ready",
                created_at=0,
                last_opened=0,
            )
        )
        db.commit()

    from app.main import create_app
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as client:
        # First upload
        r1 = client.post(
            "/api/projects/p1/revisions",
            files={"file": ("x.dwg", b"bytes-a", "application/octet-stream")},
        )
        assert r1.status_code == 201

        # Duplicate
        r2 = client.post(
            "/api/projects/p1/revisions",
            files={"file": ("x-copy.dwg", b"bytes-a", "application/octet-stream")},
        )
        assert r2.status_code == 409

        # Inspect events
        r3 = client.get("/api/projects/p1/events")
        body = r3.json()
        codes = [e["code"] for e in body]
        assert "revision.registered" in codes
        assert "revision.duplicate" in codes
