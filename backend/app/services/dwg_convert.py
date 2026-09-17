"""libredwg subprocess wrapper — converts DWG files to DXF for downstream parsing.

ezdxf's built-in DWG reader (ezdxf 1.4.x) only supports R13/R14/R2000 (AC1012/14/15).
The TP-104 reference files are R2010 (AC1024) — outside that range. GNU libredwg
supports up to R2013. The converter is discovered from ``LIBREDWG_BIN``
or the system ``PATH``.

This module is the only place that shells out to libredwg. ``parse.py`` calls
``convert_dwg_to_dxf(...)`` and treats the result as a normal DXF blob.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def find_libredwg(explicit: str | None = None) -> Path | None:
    """Return the absolute path to the libredwg ``dwg2dxf`` binary, or None.

    Resolution order:
      1. ``explicit`` (typically the ``LIBREDWG_BIN`` env var)
      2. ``dwg2dxf`` resolved from the system ``PATH``

    The returned path is only valid if the file exists and is executable.
    """
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    env_bin = os.environ.get("LIBREDWG_BIN")
    if env_bin:
        candidates.append(env_bin)
    path_bin = shutil.which("dwg2dxf")
    if path_bin:
        candidates.append(path_bin)

    for raw in candidates:
        p = Path(raw).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return p
    return None


def libredwg_available() -> bool:
    """True if the libredwg binary is reachable on this host."""
    return find_libredwg() is not None


def convert_dwg_to_dxf(
    dwg_path: str | Path,
    out_dir: Path | None = None,
    timeout_sec: int = 60,
) -> Path | None:
    """Convert a DWG file to DXF using libredwg.

    Args:
        dwg_path: absolute or upload-dir-relative path to the input DWG.
        out_dir:  directory to write the output DXF into. A new tempdir is
                  created and returned in the path; cleanup is the caller's
                  responsibility. If None, uses the system temp dir.
        timeout_sec: hard timeout for the subprocess.

    Returns:
        Absolute path to the produced DXF file, or ``None`` on any failure
        (binary missing, conversion error, missing output, timeout).
        Never raises.
    """
    bin_path = find_libredwg()
    if bin_path is None:
        logger.warning("libredwg binary not found; cannot convert %s", dwg_path)
        return None

    dwg_p = Path(dwg_path)
    if not dwg_p.is_file():
        logger.warning("DWG input not found: %s", dwg_p)
        return None

    if out_dir is None:
        out_dir = Path(tempfile.mkdtemp(prefix="dwg2dxf_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    out_dxf = out_dir / f"{dwg_p.stem}.dxf"

    # -y : overwrite existing output
    # -o : explicit output path (dwg2dxf defaults to cwd otherwise)
    # NOTE: we deliberately do NOT pass ``-m`` (minimal) because we need the
    # full BLOCKS section to expand INSERT references — Revit 3D exports
    # represent every structural member as an INSERT into a Part-* block,
    # and without the BLOCKS section those INSERTs cannot be expanded.
    args = [str(bin_path), "-y", "-o", str(out_dxf), str(dwg_p)]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("libredwg timed out on %s after %ss", dwg_p, timeout_sec)
        return None
    except OSError as exc:
        logger.warning("libredwg failed to launch: %s", exc)
        return None

    if proc.returncode != 0:
        logger.warning(
            "libredwg exit %d on %s; stderr=%s",
            proc.returncode,
            dwg_p,
            (proc.stderr or "").strip()[:200],
        )
        return None

    if not out_dxf.is_file() or out_dxf.stat().st_size == 0:
        logger.warning("libredwg produced no output for %s", dwg_p)
        return None

    return out_dxf
