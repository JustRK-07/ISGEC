"""Two-phase analyze orchestrator — port of lib/analyze.js.

Phase 1 (sync, fast): parse files → run deterministic rules → persist + mark ready.
Phase 2 (async, slow): call LLM with hard timeout → persist any new LLM issues.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.file import File
from app.models.issue import Issue
from app.services import llm_gemini, llm_ollama, parse, rules

logger = logging.getLogger(__name__)


@dataclass
class AnalysisState:
    status: str = "idle"  # 'idle' | 'running' | 'done' | 'error'
    phase: str | None = None  # 'rules' | 'llm'
    started_at: int | None = None
    finished_at: int | None = None
    error: str | None = None
    summary: dict[str, int] | None = None
    issue_count: int | None = None
    llm_status: str | None = None  # 'pending' | 'running' | 'done' | 'failed' | 'skipped'
    llm_error: str | None = None


# In-process state map. Fine for single-process v1; replace with Redis when
# the FastAPI app moves to multi-worker.
_STATE: dict[str, AnalysisState] = {}


def get_analysis_state(project_id: str) -> AnalysisState:
    return _STATE.get(project_id, AnalysisState())


def _summarize(issues: list[dict]) -> dict[str, int]:
    summary = {"pass": 0, "warn": 0, "fail": 0}
    for it in issues:
        sev = it.get("severity")
        if sev == "high":
            summary["fail"] += 1
        elif sev in ("medium", "low"):
            summary["warn"] += 1
        elif sev == "pass":
            summary["pass"] += 1
    return summary


def _find_file(files: list[File], discipline: str) -> File | None:
    for f in files:
        if f.discipline == discipline:
            return f
    return None


def _ensure_parsed(file_row: File, data_dir: Path) -> parse.ParsedDrawing:
    """Run the file parser + persist file-level metadata if it changed."""
    stored_path = Path(file_row.stored_path)
    # If the stored path is absolute, use it as-is; otherwise resolve
    # relative to the data_dir (legacy layout).
    full_path = stored_path if stored_path.is_absolute() else (data_dir / stored_path)
    parsed = parse.parse_file(full_path, file_row.filename)
    prev_meta = json.loads(file_row.parse_meta) if file_row.parse_meta else {}

    if (
        prev_meta.get("entityCount") != parsed.entity_count
        or prev_meta.get("headerUnits") != parsed.header.get("$INSUNITS")
    ):
        meta = {
            "kind": parsed.kind,
            "parseStatus": parsed.parse_status or ("ok" if parsed.ok else "failed"),
            "error": parsed.error,
            "entityCount": parsed.entity_count,
            "layers": parsed.layers,
            "textLabels": parsed.text_labels,
            "headerUnits": parsed.header.get("$INSUNITS"),
            "header": parsed.header,
            "parseMeta": parsed.parse_meta,
            "magicBytes": parsed.parse_meta.get("magicBytes"),
            "dwgVersion": parsed.parse_meta.get("dwgVersion"),
            "layerCandidates": parsed.parse_meta.get("layerCandidates"),
            "elevations": parsed.parse_meta.get("elevations"),
            "pipes": parsed.parse_meta.get("pipes"),
        }
        file_row.parse_meta = json.dumps(meta)
        file_row.parse_status = meta["parseStatus"]
        file_row.parse_error = meta["error"]
    return parsed


def _persist_entities(db: Session, project_id: str, entities: list[dict]) -> None:
    """Replace the project's entity rows with the freshly parsed set."""
    from app.models.entity import Entity  # local import — model file added in Phase 2

    db.query(Entity).filter(Entity.project_id == project_id).delete()
    db.flush()
    for ent in entities:
        db.add(Entity(**ent))
    db.commit()


def _persist_issues(db: Session, project_id: str, findings: list[dict]) -> None:
    from app.models.issue import Issue

    db.query(Issue).filter(Issue.project_id == project_id).delete()
    db.flush()
    now = int(time.time() * 1000)
    for finding in findings:
        db.add(
            Issue(
                id=str(uuid.uuid4()),
                project_id=project_id,
                severity=finding["severity"],
                category=finding["category"],
                code=finding["code"],
                title=finding["title"],
                evidence=finding.get("evidence"),
                sheet=finding.get("sheet"),
                grid=finding.get("grid"),
                mech_ref=finding.get("mech_ref"),
                str_ref=finding.get("str_ref"),
                formula=finding.get("formula"),
                result_json=json.dumps(finding.get("result_json")),
                state="open",
                assigned=None,
                created_at=now,
            )
        )
    db.commit()


async def run_phase_1(db: Session, project_id: str) -> dict:
    settings = get_settings()
    _STATE[project_id] = AnalysisState(
        status="running", phase="rules", started_at=int(time.time() * 1000)
    )

    from app.models.project import Project

    project = db.get(Project, project_id)
    if not project:
        raise RuntimeError("Project not found")
    project.status = "processing"
    db.commit()

    files = db.query(File).filter(File.project_id == project_id).all()
    str_file = _find_file(files, "str")
    mech_file = _find_file(files, "mech")
    if not str_file or not mech_file:
        raise RuntimeError("Project is missing STR or MECH file")

    data_dir = settings.data_dir
    str_parsed = _ensure_parsed(str_file, data_dir)
    mech_parsed = _ensure_parsed(mech_file, data_dir)
    db.commit()

    all_entities = [
        *parse.dxf_to_entities(str_parsed, "str", project_id, lambda: str(uuid.uuid4())),
        *parse.dxf_to_entities(mech_parsed, "mech", project_id, lambda: str(uuid.uuid4())),
    ]
    if all_entities:
        _persist_entities(db, project_id, all_entities)

    findings = rules.run_checks(entities=all_entities, gemini_issues=[])
    if findings:
        _persist_issues(db, project_id, findings)

    summary = _summarize(findings)
    project.status = "ready"
    db.commit()

    _STATE[project_id] = AnalysisState(
        status="done",
        phase="rules",
        finished_at=int(time.time() * 1000),
        summary=summary,
        issue_count=len(findings),
        llm_status=("pending" if _llm_available() else "skipped"),
    )
    return {"findings": findings, "summary": summary}


async def run_phase_2(db: Session, project_id: str) -> None:
    """Slow phase: call LLM with hard timeout, append any new issues."""
    from app.models.issue import Issue
    from app.models.project import Project

    settings = get_settings()
    state = _STATE.get(project_id, AnalysisState())

    project = db.get(Project, project_id)
    if not project:
        return

    files = db.query(File).filter(File.project_id == project_id).all()
    str_file = _find_file(files, "str")
    mech_file = _find_file(files, "mech")
    if not str_file or not mech_file or not _llm_available():
        _STATE[project_id] = AnalysisState(**{**state.__dict__, "llm_status": "skipped"})
        return

    state.llm_status = "running"
    _STATE[project_id] = state

    def _meta(file_row: File) -> dict:
        meta = json.loads(file_row.parse_meta) if file_row.parse_meta else {}
        return {
            **meta,
            "filename": file_row.filename,
            "format": file_row.format,
            "sizeBytes": file_row.size_bytes,
            "parseStatus": file_row.parse_status,
            "kind": meta.get("kind", "unknown"),
            "header": meta.get("header"),
        }

    try:
        if settings.llm_provider == "ollama":
            coro = llm_ollama.analyse_drawings(
                project_meta={
                    "label": project.label,
                    "rev": project.rev,
                    "createdAt": project.created_at,
                },
                str_meta=_meta(str_file),
                mech_meta=_meta(mech_file),
            )
        else:
            coro = llm_gemini.analyse_drawings(
                project_meta={
                    "label": project.label,
                    "rev": project.rev,
                    "createdAt": project.created_at,
                },
                str_meta=_meta(str_file),
                mech_meta=_meta(mech_file),
            )

        llm_findings = await asyncio.wait_for(
            coro, timeout=settings.gemini_timeout_sec
        )
    except asyncio.TimeoutError:
        llm_findings = [
            {
                "severity": "low",
                "category": "general",
                "code": "AI-TIMEOUT",
                "title": "LLM analysis timed out",
                "evidence": (
                    f"LLM call exceeded {settings.gemini_timeout_sec}s budget. "
                    "Deterministic rule engine results are still shown above."
                ),
                "formula": None,
                "sheet": None,
                "grid": None,
                "mech_ref": None,
                "str_ref": None,
            }
        ]
        state.llm_error = f"LLM timed out after {settings.gemini_timeout_sec}s"
    except Exception as exc:  # noqa: BLE001
        logger.exception("[llm] %s", project_id)
        llm_findings = [
            {
                "severity": "low",
                "category": "general",
                "code": "AI-UNAVAIL",
                "title": "LLM analysis unavailable",
                "evidence": str(exc)[:200],
                "formula": None,
                "sheet": None,
                "grid": None,
                "mech_ref": None,
                "str_ref": None,
            }
        ]
        state.llm_error = str(exc)

    # Append LLM issues (don't clobber the deterministic set)
    now = int(time.time() * 1000)
    for finding in llm_findings:
        db.add(
            Issue(
                id=str(uuid.uuid4()),
                project_id=project_id,
                severity=finding["severity"],
                category=finding["category"],
                code=finding["code"],
                title=finding["title"],
                evidence=finding.get("evidence"),
                sheet=finding.get("sheet"),
                grid=finding.get("grid"),
                mech_ref=finding.get("mech_ref"),
                str_ref=finding.get("str_ref"),
                formula=finding.get("formula"),
                result_json=None,
                state="open",
                assigned=None,
                created_at=now,
            )
        )
    db.commit()

    # Recompute summary across all issues
    all_issues = [
        {
            "severity": row.severity,
            "category": row.category,
            "code": row.code,
        }
        for row in db.query(Issue).filter(Issue.project_id == project_id).all()
    ]
    summary = _summarize(all_issues)
    state.llm_status = "failed" if state.llm_error else "done"
    state.llm_error = state.llm_error
    state.finished_at = int(time.time() * 1000)
    state.summary = summary
    state.issue_count = len(all_issues)
    _STATE[project_id] = state


def _llm_available() -> bool:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return llm_ollama.ollama_configured()
    return llm_gemini.gemini_configured()


async def run_analysis(db: Session, project_id: str) -> dict:
    """Run the full two-phase pipeline. Phase 2 is fire-and-forget."""
    try:
        await run_phase_1(db, project_id)
    except Exception as exc:  # noqa: BLE001
        from app.models.project import Project

        project = db.get(Project, project_id)
        if project:
            project.status = "error"
            db.commit()
        _STATE[project_id] = AnalysisState(status="error", error=str(exc))
        raise

    # Fire phase 2 in the background — caller doesn't await it
    asyncio.create_task(run_phase_2(db, project_id))
    return {"status": "done", "phase": "rules"}
