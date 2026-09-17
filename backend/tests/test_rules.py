"""Unit tests for the rule engine — Checks 7 & 8 (port from lib/rules.js)."""

from app.services.rules import (
    check_missing,
    check_orphan,
    run_checks,
    simple_similarity,
)


def _entity(id_: str, discipline: str, kind: str, label: str | None, **kw) -> dict:
    return {
        "id": id_,
        "project_id": "p",
        "discipline": discipline,
        "sheet": "0001",
        "kind": kind,
        "label": label,
        "x_mm": kw.get("x_mm", 0.0),
        "y_mm": kw.get("y_mm", 0.0),
        "w_mm": kw.get("w_mm"),
        "h_mm": kw.get("h_mm"),
        "rotation": 0.0,
        "meta": {"layer": "OPENINGS"},
    }


def test_simple_similarity_identical():
    assert simple_similarity("F11WE", "F11WE") == 1.0


def test_simple_similarity_close():
    # OP-203 vs OP-203-A share many 3-grams; similarity > 0.4
    score = simple_similarity("OP-203", "OP-203-A")
    assert 0.4 < score < 1.0


def test_simple_similarity_unrelated():
    assert simple_similarity("F11WE", "BM-150") < 0.2


def test_check_missing_flags_unmatched_mech_opening():
    entities = [
        _entity("m1", "mech", "opening", "OP-203"),
        _entity("s1", "str", "opening", "BM-150"),
    ]
    findings = check_missing(entities)
    assert len(findings) == 1
    assert findings[0].code == "OPEN-MISS"
    assert findings[0].mech_ref == "OP-203"


def test_check_missing_does_not_flag_when_match_exists():
    entities = [
        _entity("m1", "mech", "opening", "OP-203"),
        _entity("s1", "str", "opening", "OP-203"),
    ]
    findings = check_missing(entities)
    assert findings == []


def test_check_orphan_flags_unmatched_str_opening():
    entities = [
        _entity("m1", "mech", "opening", "OP-203"),
        _entity("s1", "str", "opening", "OP-203"),
        _entity("s2", "str", "opening", "EXTRA-1"),
    ]
    matched = {"s1"}
    findings = check_orphan(entities, matched)
    assert len(findings) == 1
    assert findings[0].code == "OPEN-ORPH"
    assert findings[0].str_ref == "EXTRA-1"


def test_run_checks_full_pipeline():
    entities = [
        _entity("m1", "mech", "opening", "OP-203", x_mm=1000, y_mm=2000, w_mm=300, h_mm=200),
        _entity("s1", "str", "opening", "OP-203", x_mm=1010, y_mm=2010, w_mm=305, h_mm=200),
    ]
    findings = run_checks(entities)
    # Matched — should not produce OPEN-MISS or OPEN-ORPH
    codes = {f["code"] for f in findings}
    assert "OPEN-MISS" not in codes
    assert "OPEN-ORPH" not in codes
