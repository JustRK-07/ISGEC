"""Layer 0 — Ingestion & Revision Lock (BACKEND_ARCHITECTURE §1).

The revision ledger is a Git-like DAG of every uploaded DWG. Two rules:

1. A given SHA-256 may only exist once — re-uploading the same bytes returns
   the existing revision (no duplicates).
2. When a new file with the same `family_id` is uploaded and differs from the
   previous revision, the new one increments the `revision_letter` (A → B → C)
   and points `supersedes` at its predecessor.
"""

from __future__ import annotations

import re
import string
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.revision import Revision


class DuplicateRevision(Exception):
    """Raised when an uploaded file's SHA-256 already exists in the ledger."""

    def __init__(self, revision_id: str):
        super().__init__(f"Revision already ingested: {revision_id}")
        self.revision_id = revision_id


def _next_letter(current: str) -> str:
    """Increment a revision letter A → B → … → Z."""
    if not current or current not in string.ascii_uppercase:
        return "A"
    idx = string.ascii_uppercase.index(current)
    return string.ascii_uppercase[(idx + 1) % 26]


def _latest_letter_for_family(db: Session, family_id: str) -> str | None:
    row = db.execute(
        select(Revision)
        .where(Revision.family_id == family_id)
        .order_by(Revision.uploaded_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return row.revision_letter if row else None


def find_by_sha(db: Session, sha256: str) -> Revision | None:
    return db.execute(
        select(Revision).where(Revision.sha256 == sha256)
    ).scalar_one_or_none()


def find_by_family(db: Session, family_id: str) -> list[Revision]:
    rows = db.execute(
        select(Revision)
        .where(Revision.family_id == family_id)
        .order_by(Revision.uploaded_at.asc())
    ).scalars().all()
    return list(rows)


def normalize_family_id(name: str) -> str:
    """Strip extension + lower-case a family id.

    Examples:
        'TP-104 STR GA.dwg'           → 'tp-104 str ga'
        'TP-104 STR GA - Rev B.dwg'   → 'tp-104 str ga'
        'plan_rev2.DXF'               → 'plan'
        'TP-104 STR GA rev C.dwg'     → 'tp-104 str ga'

    The family_id is a logical grouping; revision_letter differentiates
    revisions within it. We strip common revision markers so renames like
    "Rev B" / "rev2" don't accidentally start a new family.
    """
    base = re.sub(r"\.[A-Za-z0-9]+$", "", name)
    # Strip common revision markers: 'Rev A', 'rev 2', '_rev3', '-R4', '(C)'
    base = re.sub(r"[\s_\-]*r?ev[\s_\-]*[a-z0-9]+", " ", base, flags=re.I)
    base = re.sub(r"[\s_\-]*r\d+", " ", base, flags=re.I)
    base = re.sub(r"\([a-z0-9]+\)", " ", base, flags=re.I)
    base = re.sub(r"\s+", " ", base).strip()
    return base.lower() or "untitled"


def register_revision(
    db: Session,
    *,
    family_id: str,
    sha256: str,
    filename: str,
    size_bytes: int,
    project_id: str,
    uploaded_by: str | None = None,
) -> Revision:
    """Idempotent insert. Raises DuplicateRevision if SHA-256 already known."""
    existing = find_by_sha(db, sha256)
    if existing:
        raise DuplicateRevision(existing.id)

    previous_letter = _latest_letter_for_family(db, family_id)
    new_letter = _next_letter(previous_letter or "")

    previous = (
        db.execute(
            select(Revision)
            .where(Revision.family_id == family_id)
            .order_by(Revision.uploaded_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    )

    rev = Revision(
        id=str(uuid.uuid4()),
        family_id=family_id,
        revision_letter=new_letter,
        supersedes=previous.id if previous else None,
        sha256=sha256,
        filename=filename,
        size_bytes=size_bytes,
        uploaded_by=uploaded_by,
        uploaded_at=int(__import__("time").time() * 1000),
        project_id=project_id,
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)
    return rev
