"""Issue update router — PATCH /api/issues/{id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.issue import Issue
from app.schemas.issue import IssuePatch

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.patch("/{issue_id}")
def patch_issue(
    issue_id: str, body: IssuePatch, db: Session = Depends(get_db)
) -> dict:
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if body.state is not None:
        issue.state = body.state
    if body.assigned is not None:
        issue.assigned = body.assigned
    db.commit()

    return {
        "ok": True,
        "id": issue.id,
        "state": issue.state,
        "assigned": issue.assigned,
    }
