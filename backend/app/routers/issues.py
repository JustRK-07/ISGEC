"""Issue update router — PATCH /api/issues/{id}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.issue import Issue
from app.schemas.issue import IssuePatch
from app.services.events import emit_event

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.patch("/{issue_id}")
def patch_issue(
    issue_id: str, body: IssuePatch, db: Session = Depends(get_db)
) -> dict:
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    previous_state = issue.state
    if body.state is not None:
        issue.state = body.state
    if body.assigned is not None:
        issue.assigned = body.assigned
    if issue.state != previous_state:
        emit_event(
            db,
            issue.project_id,
            f"issue.{issue.state}",
            f"Issue {issue.code} marked {issue.state}.",
            tone="ok" if issue.state == "resolved" else "info",
            payload={"issueId": issue.id, "previousState": previous_state, "state": issue.state},
        )
    db.commit()

    return {
        "ok": True,
        "id": issue.id,
        "state": issue.state,
        "assigned": issue.assigned,
    }
