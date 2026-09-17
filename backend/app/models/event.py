"""ProjectEvent ORM model — append-only audit/activity log.

Per workstream 9, this table captures every meaningful state transition a
project goes through (upload, parse, analyze, LLM, issue patch, revision).
The log is append-only — rows are inserted by the event service and never
updated or deleted through the public API.

Each row carries a stable ``event_id`` (UUID) and an idempotency-friendly
``dedupe_key`` (UNIQUE) so re-emitted events (e.g. on retry) collapse into a
single row. The migration strategy is explicit: see ``app/services/events.py``
for the idempotent SQLite migration (``ensure_event_table`` + ``ensure_indexes``).
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ProjectEvent(Base):
    """Append-only event log row for a project.

    Categories:
        upload     — files persisted
        parse      — file parse/extract result
        analyze    — phase 1 (rules) lifecycle
        llm        — phase 2 (LLM) lifecycle
        issue      — issue state transition (open/resolved/dismissed)
        revision   — revision ledger entry (new/duplicate)
        system     — catch-all (errors, migrations, etc.)
    """

    __tablename__ = "project_events"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_project_events_dedupe_key"),
        Index("ix_project_events_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    # Free-form code within a category (e.g. 'upload.complete', 'parse.ok',
    # 'rules.completed', 'llm.timeout', 'issue.resolved', 'revision.duplicate').
    code: Mapped[str] = mapped_column(String, nullable=False)
    # 'info' | 'ok' | 'warn' | 'fail'
    tone: Mapped[str] = mapped_column(String, nullable=False, default="info")
    # Human-readable one-liner. The frontend renders this directly.
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional JSON blob with extra structured context (sizes, sha, counts, etc.).
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Monotonically increasing timestamp (epoch millis).
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Idempotency key — UNIQUE; same key → same row.
    dedupe_key: Mapped[str] = mapped_column(String, nullable=False)
