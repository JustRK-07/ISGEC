# Verification Reference

Two scripts verify the 3 pipelines:

## `verify_all.py` — structural / alignment audit

Wipes every approach's `work/`, `out/`, `transform.json`, then runs
`./run.sh` (clean → fit → overlay) on each in `A/`, `B/`, `C/`. Reads
back the produced DXFs and checks structural expectations:

| Approach | Modelspace | Wrapper INSERTs | TP104-A residual |
|---|---:|---|---:|
| A | ~2,242 entities | (none) | < 0.001 DXF units |
| B | 2 INSERTs | MECH_DRAWING + STR_DRAWING | < 0.001 DXF units |
| C | 1 INSERT | OVERLAY_DRAWING | < 0.001 DXF units |

**Run**
```bash
cd ISGEC/
python3 verify_all.py 3    # iterate up to 3 times
```

Pass output looks like:
```
╔═══════════════════════════════════════════════════════════════╗
║  End-to-end verification — iteration 1/3
╚═══════════════════════════════════════════════════════════════╝

──────────────────────────────────────────────────────────────────────
  APPROACH A
──────────────────────────────────────────────────────────────────────
  Wiped. Running ./run.sh ...
  ✓ STEP 1 (CLEAN): MECH 2242 entities, 7 grid labels retained
  ✓ STEP 2 (FIT): scale_x=1.000000 scale_y=1.000000 tx=208379.8605 ty=-179584.5241  max_residual=0.0004
  ✓ STEP 3 (OVERLAY): TP-104 OVERLAY_A.dxf (18.43 MB)
  ✓ PASS
  ✓ STRUCTURAL: 2,242 modelspace entities, 0 wrappers
  ✓ ALIGNMENT: TP104-A residual = 0.0004
   ... (B, C similar)

✓ ALL APPROACHES PASS on iteration 1
```

---

## `check_overlap.py` — pixel-level overlap check

Renders each overlay at 4000 × 2000 pixels cropped to the conveyor
area (`X_MIN=200000..320000`, `Y_MIN=-200000..-140000`), then:

1. Builds `red_mask` (MECH) and `blue_mask` (STR) numpy arrays from
   pixel RGB.
2. Computes bounding boxes for red and blue regions.
3. Checks: blue INSIDE red bbox (✓ means STR sits on the MECH
   structural area, not far away).
4. Checks: centroid distance < 5000 DXF units.
5. Checks: pixel overlap > 1000 px (means STR beams actually cross
   MECH geometry, not just disjoint).

**Run**
```bash
cd ISGEC/
python3 check_overlap.py
```

Pass output looks like:
```
  Approach A:
    MECH  red pixels:     45,123
    STR   blue pixels:    44,682
    Overlap (red+blue same px): 41,852
    MECH bbox: X=200023..319999  Y=-199998..-140024
    STR  bbox: X=200023..319999  Y=-199998..-140024
    Centroid distance: 0 DXF units
    Blue INSIDE red bbox: ✓ YES
    ✓ PASS: STR sits on MECH, beams overlap, distance 0u

  Approach B:
    MECH  red pixels:     45,120
    STR   blue pixels:    44,717
    ...

  ✓ ALL APPROACHES OVERLAP PROPERLY
```

> **Note**: Approach A's red/blue pixel counts here are dominated by
> MECH entities that were originally red and STR entities that were
> originally blue in the source drawings. Most MECH entities are also
> red, gray, or magenta (17 unique layer colors); the red_mask catches
> only the originally-red ones. To see all entity colors, render with
> `render_all.py` or `render_structure.py` instead.

---

## `render_all.py` — visual side-by-side

Renders each overlay's actual DXF colors (no red/blue forcing, no
masks) and composes side-by-side into `render/isgec_all.png`.

**Run**
```bash
python3 render_all.py
```

## `render_structure.py` — show wrapper INSERTs

Same render, but draws lime `X` markers on the wrapper INSERTs so you
can see **where each approach's wrapper entity sits**. This makes the
structural difference between A (no X), B (2 X), and C (1 X) visible.

**Run**
```bash
python3 render_structure.py
```

Outputs `render/REAL_A.png`, `render/REAL_B.png`, `render/REAL_C.png`,
and `render/real_all.png` (composite).
