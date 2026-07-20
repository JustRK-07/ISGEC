"""Tests for the revision ledger — Layer 0."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models.file import File as FileModel
from app.models.issue import Issue
from app.models.project import Project
from app.models.revision import Revision
from app.services.revisions import (
    DuplicateRevision,
    _next_letter,
    find_by_family,
    find_by_sha,
    normalize_family_id,
    register_revision,
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
    yield
    Base.metadata.drop_all(bind=engine)


# ---- pure helpers ---------------------------------------------------------- #


def test_next_letter_increments_alphabet():
    assert _next_letter("") == "A"
    assert _next_letter("A") == "B"
    assert _next_letter("Y") == "Z"
    assert _next_letter("Z") == "A"  # wraps


def test_normalize_family_id_strips_extension():
    assert normalize_family_id("TP-104 STR GA.dwg") == "tp-104 str ga"
    assert normalize_family_id("plan_rev2.DXF") == "plan"
    assert normalize_family_id("") == "untitled"


def test_normalize_family_id_strips_revision_markers():
    assert normalize_family_id("TP-104 STR GA - Rev B.dwg") == "tp-104 str ga"
    assert normalize_family_id("TP-104 STR GA rev C.dwg") == "tp-104 str ga"
    assert normalize_family_id("plan (B).dwg") == "plan"
    assert normalize_family_id("house_R2.dwg") == "house"


# ---- service-level: in-memory DB ------------------------------------------ #


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        proj = Project(
            id="p1",
            label="test",
            short_name="test",
            rev="A",
            kind="Str + Mech",
            status="ready",
            created_at=1,
            last_opened=1,
        )
        db.add(proj)
        db.commit()
        yield db


def test_first_revision_letter_is_a(db_session):
    rev = register_revision(
        db_session,
        family_id="tp-104 str ga",
        sha256="a" * 64,
        filename="TP-104 STR GA.dwg",
        size_bytes=100,
        project_id="p1",
    )
    assert rev.revision_letter == "A"
    assert rev.supersedes is None


def test_second_revision_in_same_family_increments_letter(db_session):
    register_revision(
        db_session,
        family_id="tp-104 str ga",
        sha256="a" * 64,
        filename="TP-104 STR GA.dwg",
        size_bytes=100,
        project_id="p1",
    )
    rev_b = register_revision(
        db_session,
        family_id="tp-104 str ga",
        sha256="b" * 64,
        filename="TP-104 STR GA - Rev B.dwg",
        size_bytes=120,
        project_id="p1",
    )
    assert rev_b.revision_letter == "B"
    assert rev_b.supersedes is not None  # points at the first revision


def test_duplicate_sha_raises(db_session):
    register_revision(
        db_session,
        family_id="x",
        sha256="f" * 64,
        filename="x.dwg",
        size_bytes=1,
        project_id="p1",
    )
    with pytest.raises(DuplicateRevision) as excinfo:
        register_revision(
            db_session,
            family_id="x",
            sha256="f" * 64,
            filename="x.dwg",
            size_bytes=1,
            project_id="p1",
        )
    assert excinfo.value.revision_id  # has the existing revision id


def test_find_by_sha_returns_existing(db_session):
    rev = register_revision(
        db_session,
        family_id="y",
        sha256="e" * 64,
        filename="y.dwg",
        size_bytes=1,
        project_id="p1",
    )
    found = find_by_sha(db_session, "e" * 64)
    assert found is not None
    assert found.id == rev.id


def test_find_by_family_returns_chain_in_upload_order(db_session):
    register_revision(db_session, family_id="z", sha256="1" * 64,
                       filename="z.dwg", size_bytes=1, project_id="p1")
    register_revision(db_session, family_id="z", sha256="2" * 64,
                       filename="z.dwg", size_bytes=2, project_id="p1")
    register_revision(db_session, family_id="z", sha256="3" * 64,
                       filename="z.dwg", size_bytes=3, project_id="p1")
    chain = find_by_family(db_session, "z")
    assert len(chain) == 3
    letters = [r.revision_letter for r in chain]
    assert letters == ["A", "B", "C"]


# ---- HTTP layer ------------------------------------------------------------ #


def test_http_revision_upload_returns_201():
    """End-to-end: POST /api/projects/{id}/revisions twice."""
    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        # Create a project first (no files)
        proj_resp = client.post(
            "/api/projects",
            files={
                "str": ("s.dwg", b"str-bytes-A", "application/octet-stream"),
                "mech": ("m.dwg", b"mech-bytes-A", "application/octet-stream"),
            },
            data={"label": "Test", "rev": "A"},
        )
        assert proj_resp.status_code == 201, proj_resp.text
        pid = proj_resp.json()["id"]

        # First revision
        r1 = client.post(
            f"/api/projects/{pid}/revisions",
            files={"file": ("TP-104 STR GA.dwg", b"new-str-bytes", "application/octet-stream")},
        )
        assert r1.status_code == 201, r1.text
        body = r1.json()
        assert body["revision_letter"] == "A"
        assert body["supersedes"] is None

        # Duplicate SHA-256 — must return 409 with existing revision id
        r2 = client.post(
            f"/api/projects/{pid}/revisions",
            files={"file": ("TP-104 STR GA copy.dwg", b"new-str-bytes", "application/octet-stream")},
        )
        assert r2.status_code == 409, r2.text
        detail = r2.json()["detail"]
        assert detail["code"] == "DUPLICATE_REVISION"
        assert detail["revision_id"] == body["id"]

        # Different bytes, same logical family — should produce revision B
        r3 = client.post(
            f"/api/projects/{pid}/revisions",
            files={"file": ("TP-104 STR GA rev B.dwg", b"different-bytes", "application/octet-stream")},
        )
        assert r3.status_code == 201, r3.text
        body3 = r3.json()
        assert body3["revision_letter"] == "B"
        assert body3["supersedes"] == body["id"]

        # List revisions
        rl = client.get(f"/api/projects/{pid}/revisions")
        assert rl.status_code == 200
        listed = rl.json()
        assert len(listed) == 2
        assert sorted(r["revision_letter"] for r in listed) == ["A", "B"]
