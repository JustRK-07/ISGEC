"""Deterministic rule engine — port of lib/rules.js + expansion to all 8 checks.

Per BACKEND_ARCHITECTURE §5, eight checks run against the parsed entities:

  1. Fuzzy ID Match            (Levenshtein + semantic + grid proximity)
  2. Position Tolerance        (Euclidean)
  3. Size Tolerance            (per-axis)
  4. Polygon-level Clash       (Shapely)
  5. Clearance Zone            (Shapely distance)
  6. Elevation / T.O.S.        (|Δm|·1000)
  7. Required-but-Missing      (port of lib/rules.js)
  8. Provided-but-Orphaned     (port of lib/rules.js)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

# --------------------------------------------------------------------------- #
# Optional / lazy imports for heavy libraries. Tests work without them.
# --------------------------------------------------------------------------- #

try:
    from rapidfuzz import fuzz as _rf_fuzz  # type: ignore[import-not-found]

    _HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover - exercised only when lib missing
    _HAS_RAPIDFUZZ = False

try:
    from shapely.geometry import Polygon as _Polygon  # type: ignore[import-not-found]
    from shapely.strtree import STRtree as _STRtree  # type: ignore[import-not-found]

    _HAS_SHAPELY = True
except ImportError:  # pragma: no cover
    _HAS_SHAPELY = False

try:
    import numpy as np  # type: ignore[import-not-found]
    from scipy.optimize import linear_sum_assignment  # type: ignore[import-not-found]

    _HAS_SCIPY = True
except ImportError:  # pragma: no cover
    _HAS_SCIPY = False


# --------------------------------------------------------------------------- #
# Finding record
# --------------------------------------------------------------------------- #


@dataclass
class Finding:
    severity: str  # 'high' | 'medium' | 'low' | 'pass'
    category: str  # 'clash' | 'missing' | 'orphan' | 'clearance' | 'elevation' | 'size' | 'position' | 'tag' | 'general'
    code: str
    title: str
    evidence: str | None = None
    sheet: str | None = None
    grid: str | None = None
    mech_ref: str | None = None
    str_ref: str | None = None
    formula: str | None = None
    result: dict | None = None

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "code": self.code,
            "title": self.title,
            "evidence": self.evidence,
            "sheet": self.sheet,
            "grid": self.grid,
            "mech_ref": self.mech_ref,
            "str_ref": self.str_ref,
            "formula": self.formula,
            "result_json": self.result,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def simple_similarity(a: str, b: str) -> float:
    """Jaccard similarity on 3-grams (port of simpleSimilarity in lib/rules.js)."""
    a = "".join(ch for ch in (a or "").upper() if ch.isalnum())
    b = "".join(ch for ch in (b or "").upper() if ch.isalnum())
    if not a or not b:
        return 0.0

    def grams(s: str) -> set[str]:
        return {s[i : i + 3] for i in range(len(s) - 2)}

    a_set = grams(a)
    b_set = grams(b)
    inter = len(a_set & b_set)
    union = len(a_set | b_set)
    return inter / union if union else 0.0


def _opening_candidates(entities: Iterable[dict], discipline: str) -> list[dict]:
    return [
        e
        for e in entities
        if e.get("discipline") == discipline
        and e.get("kind") in ("opening", "duct", "pipe")
    ]


def _entity_polygon(entity: dict):
    """Convert an entity's mm bbox into a Shapely Polygon (axis-aligned)."""
    if not _HAS_SHAPELY:
        return None
    x = entity.get("x_mm")
    y = entity.get("y_mm")
    w = entity.get("w_mm") or 0
    h = entity.get("h_mm") or 0
    if x is None or y is None:
        return None
    half_w, half_h = w / 2, h / 2
    return _Polygon(
        [
            (x - half_w, y - half_h),
            (x + half_w, y - half_h),
            (x + half_w, y + half_h),
            (x - half_w, y + half_h),
        ]
    )


def _entity_elevation_m(entity: dict) -> float | None:
    """Extract elevation (metres) from an entity's meta JSON or label."""
    meta = entity.get("meta") or {}
    candidates = [
        meta.get("elevation"),
        meta.get("elevation_m"),
        meta.get("tos"),
        entity.get("elevation"),
        entity.get("elevation_m"),
    ]
    import re

    elev_re = re.compile(r"([\+\-]?\d{1,2}\.\d{2,3})\s*m", re.I)
    for cand in candidates:
        if cand is None:
            continue
        if isinstance(cand, (int, float)):
            return float(cand)
        if isinstance(cand, str):
            m = elev_re.search(cand)
            if m:
                return float(m.group(1))
    # Fallback: scan the label
    label = entity.get("label")
    if isinstance(label, str):
        m = elev_re.search(label)
        if m:
            return float(m.group(1))
    return None


# --------------------------------------------------------------------------- #
# Check 7 — Required-but-Missing (port from lib/rules.js)
# --------------------------------------------------------------------------- #


def check_missing(entities: list[dict], threshold: float = 0.55) -> list[Finding]:
    mech_openings = _opening_candidates(entities, "mech")
    str_openings = _opening_candidates(entities, "str")
    matched_str_ids: set[str] = set()
    findings: list[Finding] = []

    for m in mech_openings:
        if not m.get("label"):
            continue
        best, best_score = None, 0.0
        for s in str_openings:
            if not s.get("label") or s["id"] in matched_str_ids:
                continue
            score = simple_similarity(m["label"], s["label"])
            if score > best_score and score > threshold:
                best_score = score
                best = s
        if best:
            matched_str_ids.add(best["id"])
        elif m.get("kind") in ("opening", "duct"):
            findings.append(
                Finding(
                    severity="high",
                    category="missing",
                    code="OPEN-MISS",
                    title=f'Mech opening "{m["label"]}" has no Str counterpart',
                    evidence=(
                        f"Required by Mech on layer {m.get('meta', {}).get('layer', '?')}; "
                        f"no structural opening with a matching tag found in the Str drawing."
                    ),
                    sheet=m.get("sheet"),
                    mech_ref=m.get("label"),
                    formula=f'match("{m["label"]}") → none (threshold {threshold})',
                )
            )
    return findings


# --------------------------------------------------------------------------- #
# Check 8 — Provided-but-Orphaned (port from lib/rules.js)
# --------------------------------------------------------------------------- #


def check_orphan(entities: list[dict], matched_str_ids: set[str]) -> list[Finding]:
    str_openings = _opening_candidates(entities, "str")
    findings: list[Finding] = []
    for s in str_openings:
        if s["id"] not in matched_str_ids and s.get("label"):
            findings.append(
                Finding(
                    severity="medium",
                    category="orphan",
                    code="OPEN-ORPH",
                    title=f'Str opening "{s["label"]}" is not required by Mech',
                    evidence=(
                        f"Opening exists in Str (layer {s.get('meta', {}).get('layer', '?')}) "
                        f"but no Mech element references it."
                    ),
                    sheet=s.get("sheet"),
                    str_ref=s.get("label"),
                    formula=f'no mech match for "{s["label"]}"',
                )
            )
    return findings


# --------------------------------------------------------------------------- #
# Check 1 — Fuzzy ID Match (Levenshtein + grid proximity, Hungarian assignment)
# Per BACKEND_ARCHITECTURE §5.3 Check 1.
# --------------------------------------------------------------------------- #


def fuzzy_match_pairs(
    mech_list: list[dict],
    str_list: list[dict],
    threshold: float = 0.55,
    grid_scale_mm: float = 1000.0,
) -> list[tuple[str, str, float, str]]:
    """Return list of (mech_id, str_id, score, band) pairs.

    Score = 0.45 * lev + 0.40 * cos + 0.15 * prox  (cos falls back to 1.0
    when sentence-transformers is not available — i.e. dev mode without the
    heavy model). Band is 'pass' | 'verify' | 'manual'.

    Hungarian assignment via scipy.optimize.linear_sum_assignment when
    available; otherwise greedy best-first (fine for small N).
    """
    if not mech_list or not str_list:
        return []

    # Build score matrix
    n_m, n_s = len(mech_list), len(str_list)
    matrix = [[0.0] * n_s for _ in range(n_m)]
    for i, m in enumerate(mech_list):
        for j, s in enumerate(str_list):
            m_tag = m.get("label") or ""
            s_tag = s.get("label") or ""
            lev = (_rf_fuzz.ratio(m_tag, s_tag) / 100.0) if _HAS_RAPIDFUZZ else simple_similarity(m_tag, s_tag)
            cos = 1.0  # placeholder — sentence-transformers not loaded by default
            # grid proximity — closer = better (0..1)
            dx = (m.get("x_mm") or 0) - (s.get("x_mm") or 0)
            dy = (m.get("y_mm") or 0) - (s.get("y_mm") or 0)
            grid_dist = math.hypot(dx, dy)
            prox = 1.0 / (1.0 + grid_dist / grid_scale_mm)
            matrix[i][j] = 0.45 * lev + 0.40 * cos + 0.15 * prox

    # Assignment
    pairs: list[tuple[int, int]] = []
    if _HAS_SCIPY:
        # linear_sum_assignment minimizes cost → minimise -score
        cost = np.array([[-matrix[i][j] for j in range(n_s)] for i in range(n_m)])
        rows, cols = linear_sum_assignment(cost)
        pairs = list(zip(rows.tolist(), cols.tolist()))
    else:
        # Greedy: pick highest-scoring pair, remove both, repeat
        candidates = [
            (matrix[i][j], i, j)
            for i in range(n_m)
            for j in range(n_s)
            if matrix[i][j] >= threshold
        ]
        candidates.sort(reverse=True)
        used_m, used_s = set(), set()
        for score, i, j in candidates:
            if i in used_m or j in used_s:
                continue
            pairs.append((i, j))
            used_m.add(i)
            used_s.add(j)

    out: list[tuple[str, str, float, str]] = []
    for i, j in pairs:
        score = matrix[i][j]
        if score < threshold:
            continue
        band = "pass" if score >= 0.80 else "verify"
        out.append((mech_list[i]["id"], str_list[j]["id"], score, band))
    return out


def check_fuzzy_id(entities: list[dict], threshold: float = 0.55) -> list[Finding]:
    """Emit a 'tag' finding whenever a fuzzy match lands in the 'verify' band
    (not pure 'pass'). The 'pass' band is silent — those are auto-accepted."""
    mech_openings = _opening_candidates(entities, "mech")
    str_openings = _opening_candidates(entities, "str")
    pairs = fuzzy_match_pairs(mech_openings, str_openings, threshold=threshold)
    findings: list[Finding] = []
    for mech_id, str_id, score, band in pairs:
        if band != "verify":
            continue
        m = next(e for e in mech_openings if e["id"] == mech_id)
        s = next(e for e in str_openings if e["id"] == str_id)
        findings.append(
            Finding(
                severity="low",
                category="tag",
                code="TAG-VERIFY",
                title=f'Fuzzy match "{m.get("label")}" ↔ "{s.get("label")}" needs review',
                evidence=(
                    f"Score {score:.2f} — between Pass (≥0.80) and Manual (<0.55). "
                    f"Reviewer should confirm the pairing."
                ),
                sheet=m.get("sheet"),
                mech_ref=m.get("label"),
                str_ref=s.get("label"),
                formula=(
                    f"0.45·lev + 0.40·cos + 0.15·prox = {score:.2f}"
                ),
                result={"score": score, "band": band},
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# Check 2 — Position Tolerance (Euclidean)
# --------------------------------------------------------------------------- #


def check_position(
    mech: dict, str_: dict, tol_mm: float = 25.0
) -> Finding | None:
    dx = (mech.get("x_mm") or 0) - (str_.get("x_mm") or 0)
    dy = (mech.get("y_mm") or 0) - (str_.get("y_mm") or 0)
    dist = math.hypot(dx, dy)
    if dist > tol_mm:
        return Finding(
            severity="high" if dist > 100 else "medium",
            category="position",
            code="POS-DELTA",
            title=f"Position off by {dist:.0f} mm",
            evidence=(
                f"Mech at ({mech.get('x_mm', 0):.0f}, {mech.get('y_mm', 0):.0f}); "
                f"Str at ({str_.get('x_mm', 0):.0f}, {str_.get('y_mm', 0):.0f})."
            ),
            sheet=mech.get("sheet"),
            mech_ref=mech.get("label"),
            str_ref=str_.get("label"),
            formula=f"√((Δx={dx:.0f})² + (Δy={dy:.0f})²) = {dist:.0f} mm > ±{tol_mm} mm",
            result={"delta_mm": dist, "dx_mm": dx, "dy_mm": dy},
        )
    return None


# --------------------------------------------------------------------------- #
# Check 3 — Size Tolerance (per-axis)
# --------------------------------------------------------------------------- #


def check_size(
    mech: dict,
    str_: dict,
    w_tol_mm: float = 10.0,
    h_tol_mm: float = 10.0,
) -> Finding | None:
    dw = (str_.get("w_mm") or 0) - (mech.get("w_mm") or 0)
    dh = (str_.get("h_mm") or 0) - (mech.get("h_mm") or 0)
    if abs(dw) > w_tol_mm or abs(dh) > h_tol_mm:
        return Finding(
            severity="high" if abs(dw) > 50 or abs(dh) > 50 else "medium",
            category="size",
            code="SIZE-DELTA",
            title=f"Size mismatch Δw={dw:.0f} mm, Δh={dh:.0f} mm",
            evidence=(
                f"Mech requires {mech.get('w_mm', 0):.0f}×{mech.get('h_mm', 0):.0f}; "
                f"Str provides {str_.get('w_mm', 0):.0f}×{str_.get('h_mm', 0):.0f}."
            ),
            sheet=mech.get("sheet"),
            mech_ref=mech.get("label"),
            str_ref=str_.get("label"),
            formula=f"|Δw|={abs(dw):.0f} (tol ±{w_tol_mm}), |Δh|={abs(dh):.0f} (tol ±{h_tol_mm})",
            result={"dw_mm": dw, "dh_mm": dh},
        )
    return None


# --------------------------------------------------------------------------- #
# Check 4 — Polygon-level Clash (Shapely)
# Per BACKEND_ARCHITECTURE §5.3 Check 4.
# --------------------------------------------------------------------------- #


def check_polygon_clash(
    entities: list[dict],
    min_intersect_area_mm2: float = 1.0,
) -> list[Finding]:
    if not _HAS_SHAPELY:
        return []
    mech_polys = [(e, _entity_polygon(e)) for e in entities if e.get("discipline") == "mech"]
    str_polys = [(e, _entity_polygon(e)) for e in entities if e.get("discipline") == "str"]
    mech_polys = [(e, p) for e, p in mech_polys if p is not None and not p.is_empty]
    str_polys = [(e, p) for e, p in str_polys if p is not None and not p.is_empty]
    if not mech_polys or not str_polys:
        return []

    tree = _STRtree([p for _, p in str_polys])
    findings: list[Finding] = []
    for m_ent, m_poly in mech_polys:
        candidates = tree.query(m_poly)
        for idx in candidates:
            s_ent, s_poly = str_polys[idx]
            if not m_poly.intersects(s_poly):
                continue
            inter = m_poly.intersection(s_poly)
            if inter.area < min_intersect_area_mm2:
                continue
            findings.append(
                Finding(
                    severity="high",
                    category="clash",
                    code="HARD-CLASH",
                    title=f'Hard clash between "{m_ent.get("label") or m_ent["id"]}" and "{s_ent.get("label") or s_ent["id"]}"',
                    evidence=(
                        f"Polygon intersection area = {inter.area:.0f} mm². "
                        f"Per BACKEND_ARCHITECTURE §5.3 Check 4, polygon-level "
                        f"intersection (not AABB) is used to catch diagonal overlaps."
                    ),
                    sheet=m_ent.get("sheet"),
                    grid=m_ent.get("grid"),
                    mech_ref=m_ent.get("label") or m_ent["id"],
                    str_ref=s_ent.get("label") or s_ent["id"],
                    formula=f"area(m ∩ s) = {inter.area:.0f} mm²",
                    result={
                        "intersect_area_mm2": inter.area,
                        "wkt": inter.wkt,
                    },
                )
            )
    return findings


# --------------------------------------------------------------------------- #
# Check 5 — Clearance Zone Violation (Shapely distance)
# Per BACKEND_ARCHITECTURE §5.3 Check 5.
# --------------------------------------------------------------------------- #


def check_clearance(
    entities: list[dict],
    min_clear_mm: float = 50.0,
) -> list[Finding]:
    if not _HAS_SHAPELY:
        return []
    mech_polys = [(e, _entity_polygon(e)) for e in entities if e.get("discipline") == "mech"]
    str_polys = [(e, _entity_polygon(e)) for e in entities if e.get("discipline") == "str"]
    mech_polys = [(e, p) for e, p in mech_polys if p is not None and not p.is_empty]
    str_polys = [(e, p) for e, p in str_polys if p is not None and not p.is_empty]
    if not mech_polys or not str_polys:
        return []

    tree = _STRtree([p for _, p in str_polys])
    findings: list[Finding] = []
    for m_ent, m_poly in mech_polys:
        # Buffer the query geometry by min_clear_mm so the STRtree returns any
        # nearby Str element whose bbox could violate clearance.
        for idx in tree.query(m_poly.buffer(min_clear_mm)):
            s_ent, s_poly = str_polys[idx]
            if m_poly.intersects(s_poly):
                continue  # hard clash, not a clearance violation
            d = m_poly.distance(s_poly)
            if 0 < d < min_clear_mm:
                findings.append(
                    Finding(
                        severity="medium",
                        category="clearance",
                        code="CLEAR-VIOL",
                        title=(
                            f'Clearance {d:.0f} mm below required {min_clear_mm:.0f} mm '
                            f'between "{m_ent.get("label") or m_ent["id"]}" and '
                            f'"{s_ent.get("label") or s_ent["id"]}"'
                        ),
                        evidence=(
                            f"Mech ↔ Str distance {d:.0f} mm; required ≥ {min_clear_mm:.0f} mm."
                        ),
                        sheet=m_ent.get("sheet"),
                        grid=m_ent.get("grid"),
                        mech_ref=m_ent.get("label") or m_ent["id"],
                        str_ref=s_ent.get("label") or s_ent["id"],
                        formula=f"d(m, s) = {d:.0f} mm < {min_clear_mm:.0f} mm required",
                        result={"distance_mm": d, "required_mm": min_clear_mm},
                    )
                )
    return findings


# --------------------------------------------------------------------------- #
# Check 6 — Elevation / T.O.S. Alignment
# Per BACKEND_ARCHITECTURE §5.3 Check 6.
# --------------------------------------------------------------------------- #


def check_elevation(
    entities: list[dict],
    tol_mm: float = 50.0,
) -> list[Finding]:
    """Compare T.O.S. elevation between matched openings. Emission: only pairs
    where both sides carry an elevation value."""
    mech_openings = _opening_candidates(entities, "mech")
    str_openings = _opening_candidates(entities, "str")
    pairs = fuzzy_match_pairs(mech_openings, str_openings, threshold=0.55)
    findings: list[Finding] = []
    for mech_id, str_id, _score, _band in pairs:
        m = next(e for e in mech_openings if e["id"] == mech_id)
        s = next(e for e in str_openings if e["id"] == str_id)
        m_el = _entity_elevation_m(m)
        s_el = _entity_elevation_m(s)
        if m_el is None or s_el is None:
            continue
        d_mm = abs(m_el - s_el) * 1000
        if d_mm > tol_mm:
            findings.append(
                Finding(
                    severity="high" if d_mm > 200 else "medium",
                    category="elevation",
                    code="ELEV-DELTA",
                    title=f"Elevation mismatch {d_mm:.0f} mm",
                    evidence=(
                        f"Mech requires +{m_el:.3f} m; Str provides +{s_el:.3f} m."
                    ),
                    sheet=m.get("sheet"),
                    grid=m.get("grid"),
                    mech_ref=m.get("label"),
                    str_ref=s.get("label"),
                    formula=f"|{m_el:.3f} - {s_el:.3f}| · 1000 = {d_mm:.0f} mm > ±{tol_mm} mm",
                    result={
                        "mech_elevation_m": m_el,
                        "str_elevation_m": s_el,
                        "delta_mm": d_mm,
                    },
                )
            )
    return findings


# --------------------------------------------------------------------------- #
# Orchestrator — runs all 8 checks and returns findings as dicts.
# --------------------------------------------------------------------------- #


def run_checks(
    entities: list[dict],
    gemini_issues: list[dict] | None = None,
    fuzzy_threshold: float = 0.55,
    position_tol_mm: float = 25.0,
    size_w_tol_mm: float = 10.0,
    size_h_tol_mm: float = 10.0,
    clearance_mm: float = 50.0,
    elevation_tol_mm: float = 50.0,
    clash_min_area_mm2: float = 1.0,
) -> list[dict]:
    """Run all deterministic checks. Returns a list of issue dicts ready for DB."""
    gemini_issues = gemini_issues or []
    findings: list[Finding] = []

    # Check 1 — fuzzy match (only emits 'verify'-band findings)
    findings.extend(check_fuzzy_id(entities, threshold=fuzzy_threshold))

    # Build the matched set once for Checks 7 & 8
    mech_openings = _opening_candidates(entities, "mech")
    str_openings = _opening_candidates(entities, "str")
    pairs = fuzzy_match_pairs(mech_openings, str_openings, threshold=fuzzy_threshold)
    matched_str_ids = {str_id for _, str_id, _, _ in pairs}
    matched_mech_ids = {mech_id for mech_id, _, _, _ in pairs}

    # Checks 7 & 8
    findings.extend(check_missing(entities, threshold=fuzzy_threshold))
    findings.extend(check_orphan(entities, matched_str_ids))

    # Checks 2 & 3 — paired per matched opening
    for mech_id, str_id, _score, _band in pairs:
        m = next(e for e in mech_openings if e["id"] == mech_id)
        s = next(e for e in str_openings if e["id"] == str_id)
        for finding in (
            check_position(m, s, tol_mm=position_tol_mm),
            check_size(m, s, w_tol_mm=size_w_tol_mm, h_tol_mm=size_h_tol_mm),
        ):
            if finding is not None:
                findings.append(finding)

    # Check 4 — polygon clash
    findings.extend(check_polygon_clash(entities, min_intersect_area_mm2=clash_min_area_mm2))

    # Check 5 — clearance
    findings.extend(check_clearance(entities, min_clear_mm=clearance_mm))

    # Check 6 — elevation
    findings.extend(check_elevation(entities, tol_mm=elevation_tol_mm))

    # Sanity — suppress unused warning; matched_mech_ids retained for future
    # use when we add a Check 7 variant for unmatched mech elements.
    _ = matched_mech_ids

    return [f.to_dict() for f in findings]
