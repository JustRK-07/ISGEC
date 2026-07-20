"""Project ORM model — port of `projects` table from lib/db.js."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.issue import Issue


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str] = mapped_column(String, nullable=False)
    rev: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="Str + Mech")
    # 'processing' | 'ready' | 'error'
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_opened: Mapped[int] = mapped_column(BigInteger, nullable=False)

    files: Mapped[list["File"]] = relationship(
        "File", back_populates="project", cascade="all, delete-orphan"
    )
    issues: Mapped[list["Issue"]] = relationship(
        "Issue", back_populates="project", cascade="all, delete-orphan"
    )

    @property
    def created_at_dt(self) -> datetime:
        return datetime.fromtimestamp(self.created_at / 1000)

    @property
    def last_opened_dt(self) -> datetime:
        return datetime.fromtimestamp(self.last_opened / 1000)
