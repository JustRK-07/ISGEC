from __future__ import annotations

import os
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired

from app.services import dwg_convert


def _make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)


def test_find_libredwg_prefers_explicit_binary(tmp_path):
    explicit = tmp_path / "dwg2dxf"
    _make_executable(explicit)

    assert dwg_convert.find_libredwg(str(explicit)) == explicit


def test_convert_rejects_missing_input(tmp_path, monkeypatch):
    binary = tmp_path / "dwg2dxf"
    _make_executable(binary)
    monkeypatch.setenv("LIBREDWG_BIN", str(binary))

    assert dwg_convert.convert_dwg_to_dxf(tmp_path / "missing.dwg") is None


def test_convert_returns_nonempty_output(tmp_path, monkeypatch):
    binary = tmp_path / "dwg2dxf"
    source = tmp_path / "sample.dwg"
    output_dir = tmp_path / "output"
    _make_executable(binary)
    source.write_bytes(b"AC1024")
    monkeypatch.setenv("LIBREDWG_BIN", str(binary))

    def fake_run(args, **kwargs):
        output = Path(args[args.index("-o") + 1])
        output.write_text("0\nEOF\n", encoding="utf-8")
        return CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(dwg_convert.subprocess, "run", fake_run)

    converted = dwg_convert.convert_dwg_to_dxf(source, output_dir)
    assert converted == output_dir / "sample.dxf"
    assert converted.read_text(encoding="utf-8") == "0\nEOF\n"


def test_convert_handles_timeout(tmp_path, monkeypatch):
    binary = tmp_path / "dwg2dxf"
    source = tmp_path / "sample.dwg"
    output_dir = tmp_path / "output"
    _make_executable(binary)
    source.write_bytes(b"AC1024")
    monkeypatch.setenv("LIBREDWG_BIN", str(binary))

    def fake_run(args, **kwargs):
        raise TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(dwg_convert.subprocess, "run", fake_run)

    assert dwg_convert.convert_dwg_to_dxf(source, output_dir, timeout_sec=1) is None
    assert not (output_dir / "sample.dxf").exists()


def test_convert_rejects_failed_or_empty_output(tmp_path, monkeypatch):
    binary = tmp_path / "dwg2dxf"
    source = tmp_path / "sample.dwg"
    _make_executable(binary)
    source.write_bytes(b"AC1024")
    monkeypatch.setenv("LIBREDWG_BIN", str(binary))

    monkeypatch.setattr(
        dwg_convert.subprocess,
        "run",
        lambda args, **kwargs: CompletedProcess(args, 2, "", "bad drawing"),
    )
    assert dwg_convert.convert_dwg_to_dxf(source, tmp_path / "failed") is None

    def empty_run(args, **kwargs):
        Path(args[args.index("-o") + 1]).touch()
        return CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(dwg_convert.subprocess, "run", empty_run)
    assert dwg_convert.convert_dwg_to_dxf(source, tmp_path / "empty") is None
