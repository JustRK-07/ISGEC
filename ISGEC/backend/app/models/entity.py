"""Entity ORM model — port of `entities` table from lib/db.js."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discipline: Mapped[str] = mapped_column(String, nullable=False)
    sheet: Mapped[str] = mapped_column(String, nullable=False, default="default")
    kind: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    x_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    y_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    w_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    h_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rotation: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
