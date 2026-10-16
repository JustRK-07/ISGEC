"""Seed the database with one synthetic project for development testing."""

from __future__ import annotations

import json
import time
import uuid

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models.entity import Entity
from app.models.file import File
from app.models.issue import Issue
from app.models.project import Project


def main() -> None:
    init_db()

    with SessionLocal() as db:
        existing = db.execute(select(Project)).scalar_one_or_none()
        if existing:
            print("Database already seeded.")
            return

        now = int(time.time() * 1000)
        project = Project(
            id=str(uuid.uuid4()),
            label="TP-104 Mech/Str Review (demo)",
            short_name="TP-104",
            rev="C",
            kind="Str + Mech",
            status="ready",
            created_at=now,
            last_opened=now,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # Two demo files (no actual upload bytes — files table rows only)
        for disc in ("str", "mech"):
            db.add(
                File(
                    id=str(uuid.uuid4()),
                    project_id=project.id,
                    discipline=disc,
                    filename=f"TP-104 {disc.upper()} GA.dwg",
                    format="dwg",
                    size_bytes=3_000_000,
                    sha256="0" * 64,
                    stored_path=f"uploads/{project.id}/{disc}.dwg",
                    parse_status="ok",
                    parse_meta=json.dumps({"kind": "dwg", "parseStatus": "ok"}),
                )
            )

        # Two demo entities
        for disc, x, y, w, h, label in [
            ("mech", 1000, 2000, 300, 200, "OP-203"),
            ("str", 1010, 2010, 305, 200, "OP-203"),
        ]:
            db.add(
                Entity(
                    id=str(uuid.uuid4()),
                    project_id=project.id,
                    discipline=disc,
                    sheet="0001",
                    kind="opening",
                    label=label,
                    x_mm=x,
                    y_mm=y,
                    w_mm=w,
                    h_mm=h,
                    rotation=0.0,
                    meta=json.dumps({"layer": "OPENINGS"}),
                )
            )

        # One demo issue
        db.add(
            Issue(
                id=str(uuid.uuid4()),
                project_id=project.id,
                severity="medium",
                category="size",
                code="SIZE-DELTA",
                title="Demo size mismatch",
                evidence="Δw=5 mm — within ±10 mm tolerance but flagged for visibility.",
                sheet="0001",
                grid="TP104-B/2",
                mech_ref="OP-203",
                str_ref="OP-203",
                formula="|Δw|=5 mm ≤ ±10 mm tolerance",
                result_json=json.dumps({"dw_mm": 5, "dh_mm": 0}),
                state="open",
                assigned=None,
                created_at=now,
            )
        )
        db.commit()
        print(f"✓ Seeded demo project: {project.id}")


if __name__ == "__main__":
    main()
