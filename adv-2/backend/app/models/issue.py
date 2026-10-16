"""Issue ORM model — port of `issues` table from lib/db.js."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.project import Project


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 'high' | 'medium' | 'low' | 'pass'
    severity: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    sheet: Mapped[str | None] = mapped_column(String, nullable=True)
    grid: Mapped[str | None] = mapped_column(String, nullable=True)
    mech_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    str_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'open' | 'resolved' | 'dismissed'
    state: Mapped[str] = mapped_column(String, nullable=False, default="open")
    assigned: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="issues")
