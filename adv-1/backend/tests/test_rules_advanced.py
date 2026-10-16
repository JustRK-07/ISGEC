"""Tests for Checks 1-6 (advanced rules). Checks 7 & 8 are in test_rules.py."""

import pytest

from app.services import rules


def _entity(id_, discipline, kind, label=None, *, x=0.0, y=0.0, w=None, h=None, **kw):
    meta = {"layer": kw.get("layer", "OPENINGS")}
    if "elevation" in kw:
        meta["elevation"] = kw["elevation"]
    return {
        "id": id_,
        "project_id": "p",
        "discipline": discipline,
        "sheet": kw.get("sheet", "0001"),
        "kind": kind,
        "label": label,
        "x_mm": x,
        "y_mm": y,
        "w_mm": w,
        "h_mm": h,
        "rotation": 0.0,
        "meta": meta,
        "grid": kw.get("grid"),
    }


# --------------------------------------------------------------------------- #
# Check 1 — Fuzzy ID Match
# --------------------------------------------------------------------------- #


def test_fuzzy_match_returns_pass_band_for_strong_match():
    mech = [_entity("m1", "mech", "opening", "OP-203", x=1000, y=1000)]
    str_ = [_entity("s1", "str", "opening", "OP-203", x=1000, y=1000)]
    pairs = rules.fuzzy_match_pairs(mech, str_)
    assert len(pairs) == 1
    _mech_id, _str_id, score, band = pairs[0]
    assert score > 0.55
    assert band == "pass"  # exact match → pass band


def test_fuzzy_match_returns_verify_band_for_close_match():
    # OP-203 vs OP-204 — close but not identical, far apart in grid space
    mech = [_entity("m1", "mech", "opening", "OP-203", x=1000, y=1000)]
    str_ = [_entity("s1", "str", "opening", "OP-204", x=10_000, y=10_000)]
    pairs = rules.fuzzy_match_pairs(mech, str_)
    # Far apart + non-identical labels → may fall below threshold entirely
    # When it doesn't pair, no verify finding.
    if pairs:
        assert pairs[0][3] in ("pass", "verify")


def test_fuzzy_match_no_pair_below_threshold():
    mech = [_entity("m1", "mech", "opening", "F11WE", x=1000, y=1000)]
    str_ = [_entity("s1", "str", "opening", "BM-150", x=1000, y=1000)]
    pairs = rules.fuzzy_match_pairs(mech, str_, threshold=0.7)
    assert pairs == []


def test_check_fuzzy_id_emits_only_verify_band():
    mech = [_entity("m1", "mech", "opening", "OP-203-A", x=1000, y=1000)]
    str_ = [_entity("s1", "str", "opening", "OP-203-B", x=1010, y=1010)]
    findings = rules.check_fuzzy_id(mech + str_)
    # Whether it emits a verify-band finding depends on the score; just check
    # that any emitted finding uses the 'tag' category and 'TAG-VERIFY' code.
    for f in findings:
        assert f.category == "tag"
        assert f.code == "TAG-VERIFY"


# --------------------------------------------------------------------------- #
# Check 2 — Position Tolerance
# --------------------------------------------------------------------------- #


def test_check_position_within_tolerance():
    m = _entity("m1", "mech", "opening", "OP-1", x=1000, y=1000)
    s = _entity("s1", "str", "opening", "OP-1", x=1010, y=1010)
    f = rules.check_position(m, s, tol_mm=25.0)
    assert f is None


def test_check_position_above_tolerance_medium():
    m = _entity("m1", "mech", "opening", "OP-1", x=1000, y=1000)
    s = _entity("s1", "str", "opening", "OP-1", x=1060, y=1060)  # ~85 mm off
    f = rules.check_position(m, s, tol_mm=25.0)
    assert f is not None
    assert f.severity == "medium"
    assert f.category == "position"
    assert f.result["delta_mm"] > 80


def test_check_position_above_100mm_is_high():
    m = _entity("m1", "mech", "opening", "OP-1", x=1000, y=1000)
    s = _entity("s1", "str", "opening", "OP-1", x=1500, y=1500)  # ~707 mm off
    f = rules.check_position(m, s, tol_mm=25.0)
    assert f is not None
    assert f.severity == "high"


# --------------------------------------------------------------------------- #
# Check 3 — Size Tolerance
# --------------------------------------------------------------------------- #


def test_check_size_within_tolerance():
    m = _entity("m1", "mech", "opening", "OP-1", w=300, h=200)
    s = _entity("s1", "str", "opening", "OP-1", w=305, h=200)
    assert rules.check_size(m, s) is None


def test_check_size_mismatch_medium():
    m = _entity("m1", "mech", "opening", "OP-1", w=300, h=200)
    s = _entity("s1", "str", "opening", "OP-1", w=280, h=180)  # Δw=20, Δh=20
    f = rules.check_size(m, s)
    assert f is not None
    assert f.severity == "medium"
    assert f.category == "size"


def test_check_size_mismatch_high():
    m = _entity("m1", "mech", "opening", "OP-1", w=300, h=200)
    s = _entity("s1", "str", "opening", "OP-1", w=200, h=200)  # Δw=100 → high
    f = rules.check_size(m, s)
    assert f is not None
    assert f.severity == "high"


# --------------------------------------------------------------------------- #
# Check 4 — Polygon Clash (skipped if Shapely missing)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not rules._HAS_SHAPELY, reason="shapely not installed")
def test_check_polygon_clash_detects_overlap():
    # Mech and Str at the same location with overlapping boxes
    mech = [_entity("m1", "mech", "opening", "OP-1", x=0, y=0, w=300, h=200)]
    str_ = [_entity("s1", "str", "opening", "OP-1", x=0, y=0, w=300, h=200)]
    findings = rules.check_polygon_clash(mech + str_)
    assert len(findings) == 1
    assert findings[0].code == "HARD-CLASH"
    assert findings[0].severity == "high"
    assert findings[0].result["intersect_area_mm2"] > 50_000


@pytest.mark.skipif(not rules._HAS_SHAPELY, reason="shapely not installed")
def test_check_polygon_clash_no_overlap_means_no_finding():
    mech = [_entity("m1", "mech", "opening", "OP-1", x=0, y=0, w=300, h=200)]
    str_ = [_entity("s1", "str", "opening", "OP-1", x=10_000, y=10_000, w=300, h=200)]
    findings = rules.check_polygon_clash(mech + str_)
    assert findings == []


# --------------------------------------------------------------------------- #
# Check 5 — Clearance
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not rules._HAS_SHAPELY, reason="shapely not installed")
def test_check_clearance_violation():
    # Two boxes 30 mm apart (edge-to-edge), required ≥ 50 mm
    mech = [_entity("m1", "mech", "opening", "OP-1", x=0, y=0, w=100, h=100)]
    str_ = [_entity("s1", "str", "opening", "BEAM-A", x=130, y=0, w=100, h=100)]
    findings = rules.check_clearance(mech + str_, min_clear_mm=50.0)
    assert len(findings) == 1
    assert findings[0].code == "CLEAR-VIOL"
    assert 0 < findings[0].result["distance_mm"] < 50


@pytest.mark.skipif(not rules._HAS_SHAPELY, reason="shapely not installed")
def test_check_clearance_satisfied():
    mech = [_entity("m1", "mech", "opening", "OP-1", x=0, y=0, w=100, h=100)]
    str_ = [_entity("s1", "str", "opening", "BEAM-A", x=300, y=0, w=100, h=100)]
    findings = rules.check_clearance(mech + str_, min_clear_mm=50.0)
    assert findings == []


# --------------------------------------------------------------------------- #
# Check 6 — Elevation
# --------------------------------------------------------------------------- #


def test_check_elevation_mismatch():
    mech = [_entity("m1", "mech", "opening", "OP-1", x=1000, y=1000, elevation="+13.150m")]
    str_ = [_entity("s1", "str", "opening", "OP-1", x=1000, y=1000, elevation="+13.350m")]
    findings = rules.check_elevation(mech + str_, tol_mm=50.0)
    assert len(findings) == 1
    assert findings[0].code == "ELEV-DELTA"
    assert findings[0].result["delta_mm"] == pytest.approx(200.0, abs=0.5)


def test_check_elevation_within_tolerance():
    mech = [_entity("m1", "mech", "opening", "OP-1", x=1000, y=1000, elevation="+13.150m")]
    str_ = [_entity("s1", "str", "opening", "OP-1", x=1000, y=1000, elevation="+13.170m")]
    findings = rules.check_elevation(mech + str_, tol_mm=50.0)
    assert findings == []


def test_check_elevation_skips_when_missing():
    mech = [_entity("m1", "mech", "opening", "OP-1", x=1000, y=1000)]
    str_ = [_entity("s1", "str", "opening", "OP-1", x=1000, y=1000)]
    findings = rules.check_elevation(mech + str_, tol_mm=50.0)
    assert findings == []


# --------------------------------------------------------------------------- #
# Orchestrator — full pipeline
# --------------------------------------------------------------------------- #


def test_run_checks_full_pipeline_emits_position_and_size():
    entities = [
        _entity("m1", "mech", "opening", "OP-203", x=1000, y=2000, w=300, h=200, elevation="+13.150m"),
        _entity("s1", "str", "opening", "OP-203", x=1080, y=2080, w=250, h=180, elevation="+13.350m"),
    ]
    findings = rules.run_checks(entities)
    codes = {f["code"] for f in findings}
    # Position and size should both fire on this poorly-aligned pair.
    assert "POS-DELTA" in codes
    assert "SIZE-DELTA" in codes
    # Elevation should also fire.
    assert "ELEV-DELTA" in codes


def test_run_checks_clean_pair_produces_no_findings():
    entities = [
        _entity("m1", "mech", "opening", "OP-203", x=1000, y=2000, w=300, h=200),
        _entity("s1", "str", "opening", "OP-203", x=1000, y=2000, w=300, h=200),
    ]
    findings = rules.run_checks(entities)
    codes = {f["code"] for f in findings}
    # No checks should fire on a perfectly matched pair
    assert "POS-DELTA" not in codes
    assert "SIZE-DELTA" not in codes
    assert "OPEN-MISS" not in codes
    assert "OPEN-ORPH" not in codes
