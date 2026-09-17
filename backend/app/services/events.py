"""Append-only project event service (workstream 9).

Public surface:

    emit_event(db, project_id, code, message, *, tone, payload, dedupe_key)
        Idempotent insert. Returns the ProjectEvent row (existing or new).

    list_events(db, project_id, limit=200)
        Most-recent first, bounded by ``limit`` (max 500).

    ensure_event_table(engine)
        Idempotent SQLite migration. Creates the table + indexes if missing;
        safe to call on every startup. Reflects existing tables to avoid the
        "table already exists" race.

The dedupe key is mandatory and should be a stable hash of the underlying
event source (e.g. ``f"upload:{sha256}"``). Re-emitting the same key returns
the original row instead of growing the log.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models.event import ProjectEvent

# Hard cap on the events list returned to the UI. The full log can be much
# larger — but the frontend only renders a bounded scroll.
MAX_EVENTS_RETURNED = 500
DEFAULT_EVENTS_LIMIT = 200

_VALID_TONES = {"info", "ok", "warn", "fail"}


def _coerce_tone(tone: str | None) -> str:
    if not tone:
        return "info"
    tone = tone.lower()
    return tone if tone in _VALID_TONES else "info"


def _now_ms() -> int:
    return int(time.time() * 1000)


def ensure_event_table(engine: Engine) -> None:
    """Create the ``project_events`` table + indexes if they do not exist.

    The check uses SQLAlchemy ``inspect()`` so it's safe to call repeatedly
    against a pre-existing SQLite database (the project shipped with a DB
    from before this column existed).
    """
    insp = inspect(engine)
    if "project_events" in insp.get_table_names():
        return
    from app.db import Base

    Base.metadata.create_all(bind=engine, tables=[ProjectEvent.__table__])


def emit_event(
    db: Session,
    project_id: str,
    code: str,
    message: str,
    *,
    tone: str = "info",
    payload: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    created_at: int | None = None,
) -> ProjectEvent:
    """Insert a new event row. If ``dedupe_key`` matches an existing row,
    return that row instead of creating a duplicate.

    Caller is responsible for ``db.commit()`` — keeps the existing pattern
    where routers/services batch their writes.
    """
    if not project_id:
        raise ValueError("project_id is required")
    if not code:
        raise ValueError("code is required")
    if not message:
        raise ValueError("message is required")

    if dedupe_key:
        existing = db.execute(
            select(ProjectEvent).where(ProjectEvent.dedupe_key == dedupe_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    row = ProjectEvent(
        id=str(uuid.uuid4()),
        project_id=project_id,
        category=_derive_category(code),
        code=code,
        tone=_coerce_tone(tone),
        message=message,
        payload_json=json.dumps(payload, separators=(",", ":")) if payload else None,
        created_at=created_at if created_at is not None else _now_ms(),
        dedupe_key=dedupe_key or f"{project_id}:{code}:{uuid.uuid4()}",
    )
    db.add(row)
    db.flush()
    return row


def list_events(
    db: Session, project_id: str, limit: int = DEFAULT_EVENTS_LIMIT
) -> list[ProjectEvent]:
    """Return up to ``limit`` events for the project, newest first."""
    bounded = max(1, min(int(limit), MAX_EVENTS_RETURNED))
    return list(
        db.execute(
            select(ProjectEvent)
            .where(ProjectEvent.project_id == project_id)
            .order_by(ProjectEvent.created_at.desc(), ProjectEvent.id.desc())
            .limit(bounded)
        ).scalars()
    )


# --------------------------------------------------------------------------- #
# Check aggregation — computes deterministic-rule outcomes from issue rows.
# --------------------------------------------------------------------------- #


# (id, name, meta) tuples match the prototype's CHECKS list. The state/count
# is derived from the issue rows so a real run produces real numbers.
CHECK_CATALOG: list[dict[str, str]] = [
    {
        "id": "fuzzy",
        "name": "Fuzzy ID match",
        "meta": "Levenshtein + sentence-transformer + grid proximity",
    },
    {
        "id": "pos",
        "name": "Position tolerance",
        "meta": "Euclidean · default ±25 mm",
    },
    {
        "id": "size",
        "name": "Size tolerance",
        "meta": "Per-axis · default ±25 mm",
    },
    {
        "id": "poly",
        "name": "Polygon clash",
        "meta": "Shapely polygon intersection",
    },
    {
        "id": "clear",
        "name": "Clearance zone",
        "meta": "Min. distance threshold per service type",
    },
    {
        "id": "elev",
        "name": "Elevation alignment",
        "meta": "T.O.S. drift · default ±50 mm",
    },
    {
        "id": "req",
        "name": "Required-not-missing",
        "meta": "Required element not present on partner sheet",
    },
    {
        "id": "orph",
        "name": "Orphan-provided",
        "meta": "Provided element not required",
    },
]


# Mapping from issue code prefix → check id. Each deterministic rule
# prefixes its findings so we can group by check here.
_CODE_TO_CHECK: list[tuple[str, str]] = [
    ("FUZZY", "fuzzy"),
    ("POS", "pos"),
    ("SIZE", "size"),
    ("CLASH", "poly"),
    ("POLY", "poly"),
    ("CLEAR", "clear"),
    ("ELEV", "elev"),
    ("OPEN-MISS", "req"),
    ("OPEN-ORPH", "orph"),
]


def _code_to_check_id(code: str) -> str | None:
    upper = (code or "").upper()
    for prefix, check_id in _CODE_TO_CHECK:
        if upper.startswith(prefix):
            return check_id
    return None


def aggregate_checks(issues: list) -> list[dict[str, Any]]:
    """Compute a CHECKS-shaped list (id, name, meta, state, count) from
    the issues that exist for the project. ``state`` is one of
    ``"ok" | "warn" | "fail"`` — derived from severities, not invented.
    """
    counts: dict[str, dict[str, int]] = {
        c["id"]: {"fail": 0, "warn": 0, "ok": 0} for c in CHECK_CATALOG
    }

    for it in issues:
        check_id = _code_to_check_id(getattr(it, "code", "") or "")
        if not check_id:
            continue
        sev = (getattr(it, "severity", "") or "").lower()
        if sev == "high":
            counts[check_id]["fail"] += 1
        elif sev in ("medium", "low"):
            counts[check_id]["warn"] += 1
        elif sev == "pass":
            counts[check_id]["ok"] += 1

    out: list[dict[str, Any]] = []
    for c in CHECK_CATALOG:
        b = counts[c["id"]]
        if b["fail"] > 0:
            state = "fail"
            count = b["fail"]
        elif b["warn"] > 0:
            state = "warn"
            count = b["warn"]
        else:
            state = "ok"
            count = b["ok"]
        out.append(
            {
                "id": c["id"],
                "name": c["name"],
                "meta": c["meta"],
                "state": state,
                "count": count,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _derive_category(code: str) -> str:
    head = (code or "").split(".", 1)[0].lower()
    mapping = {
        "upload": "upload",
        "parse": "parse",
        "rules": "analyze",
        "analyze": "analyze",
        "llm": "llm",
        "ai": "llm",
        "issue": "issue",
        "revision": "revision",
        "system": "system",
    }
    return mapping.get(head, "system")


def _event_to_dict(row: ProjectEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "projectId": row.project_id,
        "category": row.category,
        "code": row.code,
        "tone": row.tone,
        "message": row.message,
        "payload": json.loads(row.payload_json) if row.payload_json else None,
        "createdAt": row.created_at,
    }
