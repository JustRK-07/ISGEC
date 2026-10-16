"""Revision ORM model — new per BACKEND_ARCHITECTURE §1 (Layer 0)."""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Revision(Base):
    __tablename__ = "revisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    family_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    revision_letter: Mapped[str] = mapped_column(String, nullable=False)
    supersedes: Mapped[str | None] = mapped_column(
        ForeignKey("revisions.id", ondelete="SET NULL"), nullable=True
    )
    sha256: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(String, nullable=True)
    uploaded_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
