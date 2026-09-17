"""Disk storage helpers — upload persistence, MIME sniffing, format detection."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.utils.hashing import sha256_hex

ALLOWED_EXTS = {".dwg", ".dxf", ".ifc", ".pdf"}


@dataclass
class StoredFile:
    stored_path: str  # relative to DATA_DIR
    full_path: Path
    sha256: str
    size_bytes: int
    format: str  # extension without leading dot


def _detect_format(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext or "bin"


def persist_upload(
    file_bytes: bytes,
    project_id: str,
    discipline: str,
    original_name: str,
) -> StoredFile:
    """Save uploaded bytes to disk under uploads/<project_id>/<discipline><ext>.

    Layout mirrors the current Node prototype so legacy projects remain readable.
    """
    settings = get_settings()
    project_dir = settings.upload_dir_abs / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(original_name).suffix.lower() or ".bin"
    target = project_dir / f"{discipline}{ext}"
    target.write_bytes(file_bytes)

    # Store a path that's resolvable regardless of whether upload_dir is
    # inside or outside data_dir. We prefer a path relative to data_dir when
    # possible (legacy compatibility); otherwise we use the absolute path.
    try:
        stored = str(target.relative_to(settings.data_dir))
    except ValueError:
        stored = str(target)

    return StoredFile(
        stored_path=stored,
        full_path=target,
        sha256=sha256_hex(file_bytes),
        size_bytes=len(file_bytes),
        format=_detect_format(original_name),
    )


def remove_project_uploads(project_id: str) -> None:
    """Delete every uploaded file for a project (called on DELETE)."""
    settings = get_settings()
    project_dir = settings.upload_dir_abs / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)


def upload_path(project_id: str, filename: str) -> Path:
    """Resolve a stored upload to an absolute Path on disk."""
    return get_settings().upload_dir_abs / project_id / filename
