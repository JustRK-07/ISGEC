# Rules Engine — All 8 Deterministic Checks

> **Source:** `app/services/rules.py` (624 LOC)
> **Spec:** `BACKEND_ARCHITECTURE.md §5.3` (the design doc this implements)

The rule engine runs **exact math** against the canonical entity schema. Every finding is grounded to a formula. **No confidence percentages** — engineers need auditable numbers, not black-box scores.

---

## 0. Quick reference

| # | Function | Category | Severity | Code prefix | Threshold (default) |
|---|---|---|---|---|---|
| 1 | `check_fuzzy_id` | tag | low | TAG-VERIFY | score ≥ 0.55 to match |
| 2 | `check_position` | position | high (Δ>100mm) / medium | POS-DELTA | ±25 mm Euclidean |
| 3 | `check_size` | size | high (Δ>50mm) / medium | SIZE-DELTA | ±10 mm per axis |
| 4 | `check_polygon_clash` | clash | high | HARD-CLASH | area ≥ 1 mm² |
| 5 | `check_clearance` | clearance | medium | CLEAR-VIOL | ≥ 50 mm required |
| 6 | `check_elevation` | elevation | high (Δ>200mm) / medium | ELEV-DELTA | ±50 mm |
| 7 | `check_missing` | missing | high | OPEN-MISS | required-on-str |
| 8 | `check_orphan` | orphan | medium | OPEN-ORPH | str-only-needs-meet |

All 8 are run by the orchestrator:

```python
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
) -> list[dict]: ...
```

---

## 1. Check 1 — Fuzzy ID Match (TAG-VERIFY)

**Spec:** [`BACKEND_ARCHITECTURE.md §5.3 Check 1`](../reference/BACKEND_ARCHITECTURE.md)

> *"Mechanical and Structural drawings rarely share the same tag for the same physical item. The matching engine combines Levenshtein distance, semantic embeddings, and grid proximity to pair items correctly — even when one side says `F11WE` and the other says `TP4BM101`."*

### Algorithm

```python
def fuzzy_match_pairs(mech_list, str_list, threshold=0.55, grid_scale_mm=1000.0):
    """Return list of (mech_id, str_id, score, band) tuples."""
    n_m, n_s = len(mech_list), len(str_list)
    matrix = [[0.0] * n_s for _ in range(n_m)]
    for i, m in enumerate(mech_list):
        for j, s in enumerate(str_list):
            lev = rapidfuzz.fuzz.ratio(m.tag, s.tag) / 100
            cos  = 1.0   # sentence-transformers not loaded by default
            prox = 1.0 / (1.0 + grid_dist / grid_scale_mm)
            matrix[i][j] = 0.45 * lev + 0.40 * cos + 0.15 * prox

    # Hungarian assignment (or greedy fallback)
    pairs = scipy.optimize.linear_sum_assignment(-matrix)

    for (i, j) in pairs:
        score = matrix[i][j]
        band = "pass" if score >= 0.80 else "verify" if score >= 0.55 else "manual"
        yield (mech_list[i]["id"], str_list[j]["id"], score, band)
```

### Score formula

```
score = 0.45·lev + 0.40·cos + 0.15·prox
```

| Component | Source | Weight | Range |
|---|---|---:|---|
| `lev` | Levenshtein string similarity (`rapidfuzz.fuzz.ratio`) | 0.45 | 0–1 |
| `cos` | Sentence-embedding cosine similarity | 0.40 | 0–1 (placeholder: 1.0) |
| `prox` | Grid-bubble proximity (`1 / (1 + grid_dist/1000)`) | 0.15 | 0–1 |

### Confidence bands

| Band | Score | Action |
|---|---|---|
| `pass` | ≥ 0.80 | Auto-accepted (silent — no finding emitted) |
| `verify` | 0.55–0.80 | `TAG-VERIFY` finding, severity=low |
| `manual` | < 0.55 | Not matched; reviewer pairs manually |

### When does `check_fuzzy_id` emit a finding?

Only when a pair lands in the `verify` band — the rule is intentionally silent for `pass` matches. The output is informational: "this fuzzy pair is suspicious enough to flag for human eyes".

### When does it return nothing?

If both `RapidFuzz` and `scipy` are unavailable, the matrix still computes (using `simple_similarity` fallback), but the assignment falls back to greedy best-first. Findings only emit if score ≥ 0.55.

### Fallback similarity (`simple_similarity`)

Jaccard on 3-grams:

```python
def simple_similarity(a, b):
    a = "".join(ch for ch in (a or "").upper() if ch.isalnum())
    b = "".join(ch for ch in (b or "").upper() if ch.isalnum())
    if not a or not b: return 0.0
    def grams(s): return {s[i:i+3] for i in range(len(s) - 2)}
    inter = len(grams(a) & grams(b))
    union = len(grams(a) | grams(b))
    return inter / union if union else 0.0
```

---

## 2. Check 2 — Position Tolerance (POS-DELTA)

**Spec:** [`BACKEND_ARCHITECTURE.md §5.3 Check 2`](../reference/BACKEND_ARCHITECTURE.md)

### Algorithm

```python
def check_position(mech, str_, tol_mm=25.0) -> Finding | None:
    dx = (mech["x_mm"] or 0) - (str_["x_mm"] or 0)
    dy = (mech["y_mm"] or 0) - (str_["y_mm"] or 0)
    dist = math.hypot(dx, dy)
    if dist > tol_mm:
        return Finding(
            severity="high" if dist > 100 else "medium",
            category="position",
            code="POS-DELTA",
            title=f"Position off by {dist:.0f} mm",
            formula=f"√((Δx={dx:.0f})² + (Δy={dy:.0f})²) = {dist:.0f} mm > ±{tol_mm} mm",
            result={"delta_mm": dist, "dx_mm": dx, "dy_mm": dy},
            ...
        )
```

### Severity tiers

| Δ (mm) | Severity |
|---:|---|
| 0–25 | silent (within) |
| 25–100 | medium |
| > 100 | high |

### Output JSON

```json
{
  "code": "POS-DELTA",
  "title": "Position off by 45 mm",
  "evidence": "Mech at (12000, 6800); Str at (12030, 6567).",
  "formula": "√((Δx=-30)² + (Δy=233)²) = 235 mm > ±25 mm",
  "result": { "delta_mm": 235, "dx_mm": -30, "dy_mm": 233 }
}
```

---

## 3. Check 3 — Size Tolerance (SIZE-DELTA)

**Spec:** [`BACKEND_ARCHITECTURE.md §5.3 Check 3`](../reference/BACKEND_ARCHITECTURE.md)

### Algorithm

```python
def check_size(mech, str_, w_tol_mm=10.0, h_tol_mm=10.0) -> Finding | None:
    dw = (str_["w_mm"] or 0) - (mech["w_mm"] or 0)
    dh = (str_["h_mm"] or 0) - (mech["h_mm"] or 0)
    if abs(dw) > w_tol_mm or abs(dh) > h_tol_mm:
        return Finding(
            severity="high" if abs(dw) > 50 or abs(dh) > 50 else "medium",
            category="size",
            code="SIZE-DELTA",
            title=f"Size mismatch Δw={dw:.0f} mm, Δh={dh:.0f} mm",
            formula=f"|Δw|={abs(dw):.0f} (tol ±{w_tol_mm}), |Δh|={abs(dh):.0f} (tol ±{h_tol_mm})",
            result={"dw_mm": dw, "dh_mm": dh},
            ...
        )
```

### Per-axis tolerance

The check fires on **either axis** exceeding tolerance. Per-axis reporting means an engineer can see which dimension is off.

### Severity tiers

| max(\|Δw\|, \|Δh\|) (mm) | Severity |
|---:|---|
| 0–10 | silent (within) |
| 10–50 | medium |
| > 50 | high |

---

## 4. Check 4 — Polygon-level Clash (HARD-CLASH)

**Spec:** [`BACKEND_ARCHITECTURE.md §5.3 Check 4`](../reference/BACKEND_ARCHITECTURE.md)

> *"Bounding boxes are too coarse. The clash engine converts every footprint and member into polygons … then computes true geometric intersection and clearance distance using Shapely."*

### Algorithm

```python
def check_polygon_clash(entities, min_intersect_area_mm2=1.0) -> list[Finding]:
    if not _HAS_SHAPELY: return []
    mech_polys = [(e, _entity_polygon(e)) for e in entities if e["discipline"] == "mech"]
    str_polys  = [(e, _entity_polygon(e)) for e in entities if e["discipline"] == "str"]
    mech_polys = [(e, p) for e, p in mech_polys if p is not None and not p.is_empty]
    str_polys  = [(e, p) for e, p in str_polys  if p is not None and not p.is_empty]
    if not mech_polys or not str_polys: return []

    tree = STRtree([p for _, p in str_polys])
    findings = []
    for m_ent, m_poly in mech_polys:
        for idx in tree.query(m_poly):
            s_ent, s_poly = str_polys[idx]
            if not m_poly.intersects(s_poly): continue
            inter = m_poly.intersection(s_poly)
            if inter.area < min_intersect_area_mm2: continue
            findings.append(Finding(
                severity="high",
                category="clash",
                code="HARD-CLASH",
                formula=f"area(m ∩ s) = {inter.area:.0f} mm²",
                result={"intersect_area_mm2": inter.area, "wkt": inter.wkt},
                ...
            ))
    return findings
```

### Why polygon, not AABB

A diagonal duct + beam can have **zero AABB overlap** yet physically intersect. Polygon intersection catches it; bounding boxes miss it.

### `_entity_polygon`

Converts a `{x_mm, y_mm, w_mm, h_mm}` dict into an axis-aligned Shapely Polygon (centroid + half-extents):

```python
def _entity_polygon(entity):
    if not _HAS_SHAPELY: return None
    x = entity.get("x_mm"); y = entity.get("y_mm")
    w = entity.get("w_mm") or 0; h = entity.get("h_mm") or 0
    if x is None or y is None: return None
    half_w, half_h = w / 2, h / 2
    return Polygon([
        (x - half_w, y - half_h), (x + half_w, y - half_h),
        (x + half_w, y + half_h), (x - half_w, y + half_h),
    ])
```

### Output JSON

```json
{
  "code": "HARD-CLASH",
  "title": "Hard clash between \"OP-203\" and \"P11\"",
  "evidence": "Polygon intersection area = 12450 mm². ...",
  "formula": "area(m ∩ s) = 12450 mm²",
  "result": {
    "intersect_area_mm2": 12450,
    "wkt": "POLYGON ((12000 6500, 12300 6500, 12300 6700, 12000 6700, 12000 6500))"
  }
}
```

The `wkt` field is the Well-Known Text representation of the intersection polygon — directly renderable in any GIS or mapping library.

---

## 5. Check 5 — Clearance Zone Violation (CLEAR-VIOL)

**Spec:** [`BACKEND_ARCHITECTURE.md §5.3 Check 5`](../reference/BACKEND_ARCHITECTURE.md)

> Example: *"50 mm required, 20 mm provided → flag"*

### Algorithm

```python
def check_clearance(entities, min_clear_mm=50.0) -> list[Finding]:
    if not _HAS_SHAPELY: return []
    mech_polys = ... ; str_polys = ...
    tree = STRtree([p for _, p in str_polys])
    findings = []
    for m_ent, m_poly in mech_polys:
        # Buffer the query geometry by min_clear_mm so the STRtree returns any
        # nearby Str element whose bbox could violate clearance.
        for idx in tree.query(m_poly.buffer(min_clear_mm)):
            s_ent, s_poly = str_polys[idx]
            if m_poly.intersects(s_poly): continue  # hard clash, not clearance
            d = m_poly.distance(s_poly)
            if 0 < d < min_clear_mm:
                findings.append(Finding(
                    severity="medium",
                    category="clearance",
                    code="CLEAR-VIOL",
                    title=f"Clearance {d:.0f} mm below required {min_clear_mm:.0f} mm ...",
                    formula=f"d(m, s) = {d:.0f} mm < {min_clear_mm:.0f} mm required",
                    result={"distance_mm": d, "required_mm": min_clear_mm},
                    ...
                ))
    return findings
```

### Why buffer before STRtree query

A naïve `STRtree.query(m_poly)` only returns polygons whose **bounding boxes** intersect `m_poly`'s bbox — it misses nearby-but-not-overlapping items. Buffering `m_poly` by `min_clear_mm` first ensures we catch anything within the required distance.

### Hard clash vs clearance

If `m_poly.intersects(s_poly)`, that's already caught by **Check 4 (HARD-CLASH)**. Check 5 explicitly skips those (`continue`) to avoid double-reporting.

---

## 6. Check 6 — Elevation / T.O.S. Alignment (ELEV-DELTA)

**Spec:** [`BACKEND_ARCHITECTURE.md §5.3 Check 6`](../reference/BACKEND_ARCHITECTURE.md)

> Example: *"+13.150m required, +13.350m provided → flag"*

### Algorithm

```python
def check_elevation(entities, tol_mm=50.0) -> list[Finding]:
    """Compare T.O.S. elevation between matched openings. Emission: only pairs
    where both sides carry an elevation value."""
    mech_openings = _opening_candidates(entities, "mech")
    str_openings  = _opening_candidates(entities, "str")
    pairs = fuzzy_match_pairs(mech_openings, str_openings, threshold=0.55)
    findings = []
    for mech_id, str_id, _score, _band in pairs:
        m = next(e for e in mech_openings if e["id"] == mech_id)
        s = next(e for e in str_openings  if e["id"] == str_id)
        m_el = _entity_elevation_m(m)
        s_el = _entity_elevation_m(s)
        if m_el is None or s_el is None: continue
        d_mm = abs(m_el - s_el) * 1000
        if d_mm > tol_mm:
            findings.append(Finding(
                severity="high" if d_mm > 200 else "medium",
                category="elevation",
                code="ELEV-DELTA",
                title=f"Elevation mismatch {d_mm:.0f} mm",
                formula=f"|{m_el:.3f} - {s_el:.3f}| · 1000 = {d_mm:.0f} mm > ±{tol_mm} mm",
                result={
                    "mech_elevation_m": m_el,
                    "str_elevation_m":  s_el,
                    "delta_mm":         d_mm,
                },
                ...
            ))
    return findings
```

### Elevation extraction

`_entity_elevation_m(entity)` tries in order:
1. `meta.elevation` (float)
2. `meta.elevation_m` (float)
3. `meta.tos` (string with m suffix)
4. `entity.elevation` (float)
5. `entity.elevation_m` (float)
6. Scan `entity.label` for regex `([+-]?\d{1,2}\.\d{2,3})\s*m`

Returns `float` in **metres** (e.g. `13.150`) or `None`. The check fires only when **both** sides have an elevation value.

### Severity tiers

| Δ (mm) | Severity |
|---:|---|
| 0–50 | silent |
| 50–200 | medium |
| > 200 | high |

---

## 7. Check 7 — Required-but-Missing (OPEN-MISS)

**Spec:** [`BACKEND_ARCHITECTURE.md §5.3 Check 7`](../reference/BACKEND_ARCHITECTURE.md)

> A Mech-required support or opening has no fuzzy match in Str.

### Algorithm

```python
def check_missing(entities, threshold=0.55) -> list[Finding]:
    mech_openings = _opening_candidates(entities, "mech")
    str_openings  = _opening_candidates(entities, "str")
    matched_str_ids: set[str] = set()
    findings: list[Finding] = []

    for m in mech_openings:
        if not m.get("label"): continue
        best, best_score = None, 0.0
        for s in str_openings:
            if not s.get("label") or s["id"] in matched_str_ids: continue
            score = simple_similarity(m["label"], s["label"])
            if score > best_score and score > threshold:
                best_score = score
                best = s
        if best:
            matched_str_ids.add(best["id"])
        elif m.get("kind") in ("opening", "duct"):
            findings.append(Finding(
                severity="high",
                category="missing",
                code="OPEN-MISS",
                title=f'Mech opening "{m["label"]}" has no Str counterpart',
                formula=f'match("{m["label"]}") → none (threshold {threshold})',
                ...
            ))
    return findings
```

### Behavior

- Walks every Mech opening with a label
- Greedily matches against unmatched Str openings (Jaccard 3-gram ≥ threshold)
- Only emits a finding when **no match found AND kind is `opening` or `duct`** (other kinds are silenced to avoid noise)

---

## 8. Check 8 — Provided-but-Orphaned (OPEN-ORPH)

**Spec:** [`BACKEND_ARCHITECTURE.md §5.3 Check 8`](../reference/BACKEND_ARCHITECTURE.md)

> A Str-provided opening has no Mech requirement (engineer added it without consulting Mech — usually wrong).

### Algorithm

```python
def check_orphan(entities, matched_str_ids) -> list[Finding]:
    str_openings = _opening_candidates(entities, "str")
    findings = []
    for s in str_openings:
        if s["id"] not in matched_str_ids and s.get("label"):
            findings.append(Finding(
                severity="medium",
                category="orphan",
                code="OPEN-ORPH",
                title=f'Str opening "{s["label"]}" is not required by Mech',
                formula=f'no mech match for "{s["label"]}"',
                ...
            ))
    return findings
```

### Behavior

- Reads `matched_str_ids` computed by `check_missing` (passed in by the orchestrator)
- Emits a finding for every Str opening that's labeled but not matched by any Mech opening

---

## 9. Orchestrator order

```python
def run_checks(entities, gemini_issues=None, ...):
    findings = []

    # 1. Check 1 — fuzzy (only emits 'verify'-band)
    findings.extend(check_fuzzy_id(entities, threshold=fuzzy_threshold))

    # Build matched set ONCE for Checks 7 & 8
    mech_openings = _opening_candidates(entities, "mech")
    str_openings  = _opening_candidates(entities, "str")
    pairs = fuzzy_match_pairs(mech_openings, str_openings, threshold=fuzzy_threshold)
    matched_str_ids  = {str_id  for _,  str_id, _, _ in pairs}
    matched_mech_ids = {mech_id for mech_id, _, _, _ in pairs}

    # 2. Checks 7 & 8 — opens-vs-str inventory
    findings.extend(check_missing(entities, threshold=fuzzy_threshold))
    findings.extend(check_orphan(entities, matched_str_ids))

    # 3. Checks 2 & 3 — per-paired opening
    for mech_id, str_id, _score, _band in pairs:
        m = next(e for e in mech_openings if e["id"] == mech_id)
        s = next(e for e in str_openings  if e["id"] == str_id)
        for finding in (check_position(m, s, ...), check_size(m, s, ...)):
            if finding is not None:
                findings.append(finding)

    # 4. Check 4 — polygon clash (whole-set, not paired)
    findings.extend(check_polygon_clash(entities, ...))

    # 5. Check 5 — clearance (whole-set)
    findings.extend(check_clearance(entities, ...))

    # 6. Check 6 — elevation (per-paired, must have elevations)
    findings.extend(check_elevation(entities, ...))

    return [f.to_dict() for f in findings]
```

### Why this order

- **Check 1 first** to compute the matched-str set
- **Checks 7 & 8 next** — they consume `matched_str_ids` from Check 1
- **Checks 2 & 3 next** — they iterate over matched pairs
- **Check 4 (clash)** — needs full entity sets, no pairing dependency
- **Check 5 (clearance)** — same
- **Check 6 (elevation)** — iterates pairs, but only emits when both sides have elevation

---

## 10. Output contract

### `Finding.to_dict()`

```python
def to_dict(self) -> dict:
    return {
        "severity":   self.severity,
        "category":   self.category,
        "code":       self.code,
        "title":      self.title,
        "evidence":   self.evidence,
        "sheet":      self.sheet,
        "grid":       self.grid,
        "mech_ref":   self.mech_ref,
        "str_ref":    self.str_ref,
        "formula":    self.formula,
        "result_json": self.result,
    }
```

This is the dict shape that goes into the `issues` table (after Pydantic-ish key renaming by the routers). The reconciliation fingerprint is `(code, sheet, str_ref, mech_ref)`.

---

## 11. Tweakable parameters

All thresholds are exposed as function parameters with sensible defaults:

```python
fuzzy_threshold:    float = 0.55    # minimum score to consider a match
position_tol_mm:    float = 25.0    # max Δ position before flagging
size_w_tol_mm:      float = 10.0    # max Δ width before flagging
size_h_tol_mm:      float = 10.0    # max Δ height before flagging
clearance_mm:       float = 50.0    # required clearance between mech/str
elevation_tol_mm:   float = 50.0    # max Δ elevation before flagging
clash_min_area_mm2: float = 1.0     # min polygon intersection area to flag
```

These can be overridden per-call in `run_checks(...)` or wired to per-project settings in the `Tolerance` table (future work).

---

## 12. Algorithm choices — the non-obvious ones

| Choice | Avoids | Source |
|---|---|---|
| **Shapely polygon intersection (not bounding boxes)** | Diagonal duct + beam has zero AABB overlap yet physically intersects | §5.3 Check 4 |
| **Levenshtein + grid proximity ensemble** | Levenshtein alone fails on `BM-203` vs `TP4BM203` | §5.3 Check 1 |
| **STRtree buffer for clearance query** | Naive `query(poly)` misses nearby items whose bboxes don't intersect | §5.3 Check 5 |
| **Elevation check requires both sides** | Avoids false positives from labels like "13.150" in unrelated contexts | §5.3 Check 6 |
| **Severity tiers based on Δ** | An off-by-100mm position is more severe than off-by-30mm | §5.3 Checks 2, 6 |
| **Check 1 emits only `verify` band** | Don't drown reviewers in "this fuzzy pair is fine" findings | §5.3 Check 1 |
| **Missing/Orphan only fire on labeled entities** | Unlabeled polygons aren't "openings" for inventory purposes | §5.3 Checks 7, 8 |

---

*For service orchestration: [`SERVICES.md`](./SERVICES.md). For data model: [`DATA_MODEL.md`](./DATA_MODEL.md). For the full architecture: [`ARCHITECTURE.md`](./ARCHITECTURE.md).*