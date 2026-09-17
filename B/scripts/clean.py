#!/usr/bin/env python3
"""clean.py — Step 1 of the overlay pipeline.

Takes the source DWG/DXF for both MECH and STR drawings and produces
cleaned DXFs ready for gridline fitting.

Pipeline:
  1. DWG → DXF (if input is DWG; uses ezdxf if input is already DXF)
  2. Strip annotations:  DIMENSION, MTEXT, LEADER, ATTRIB, MLEADER
                          (KEPT: TP104-* grid labels)
  3. Strip markers:      LWPOLYLINE hexagons on layer BOX (MECH only),
                          anonymous marker blocks not used by kept geometry
  4. Strip triangles:    orphan A$C2135de20 (ACM_FILLED_HALF) block + its 6
                          SOLID triangles (MECH only)
  5. Save as <work>/<base>_clean3.dxf

Runs entirely with self-locating paths — works from any clone of ISGEC/.

Usage:
  python3 scripts/clean.py
"""

import os
import re
import sys
from collections import Counter
from pathlib import Path

import ezdxf

# ---- Self-locating paths ---------------------------------------------------
HERE = Path(__file__).resolve().parent
APPROACH_DIR = HERE.parent
WORK = APPROACH_DIR / "work"
INPUT = APPROACH_DIR / "input"

# DWG or DXF under input/ → output under work/
MECH_SRC = INPUT / "TP-104 MECH GA.dwg"
STR_SRC = INPUT / "TP-104 STR GA.dwg"

MECH_DXF = WORK / "TP-104 MECH GA.dxf"
STR_DXF = WORK / "TP-104 STR GA.dxf"

MECH_CLEAN_DXF = WORK / "TP-104 MECH GA_clean.dxf"
STR_CLEAN_DXF = WORK / "TP-104 STR GA_clean.dxf"

MECH_CLEAN3_DXF = WORK / "TP-104 MECH GA_clean3.dxf"
STR_CLEAN3_DXF = WORK / "TP-104 STR GA_clean3.dxf"

# ---- Detection of inputs ---------------------------------------------------
GRID_RE = re.compile(r"^\s*TP104-[A-D1-3]\s*$")

# In MECH: centerline layers that carry gridline LINEs.
GRID_LAYERS_MECH = {"CEN", "CENETR LINE", "CENTER", "PHANTOM",
                    "PANTHOM", "HIDDEN", "HIDDDEN"}
# Anonymous blocks that are KEPT (still used by other compound blocks).
KEEP_ANON_BLOCKS = set()  # populated dynamically
# Orphan blocks to ALWAYS remove (we know they're safe).
ORPHAN_BLOCKS_MECH = {"A$C2135de20"}  # AutoCAD ACM_FILLED_HALF symbol


def _find_dxf_for_dwg(dwg_path):
    """If input is .dwg, convert via ezdxf.addons.odafc if available.
    Otherwise, raise. Returns path to .dxf file."""
    if dwg_path.suffix.lower() == ".dxf":
        return dwg_path
    if dwg_path.suffix.lower() != ".dwg":
        raise ValueError(f"Expected .dwg or .dxf, got {dwg_path}")

    try:
        from ezdxf.addons import odafc
        if odafc.is_installed():
            dxf_out = dwg_path.with_suffix(".dxf")
            print(f"  Converting {dwg_path.name} → {dxf_out.name} (ODA File Converter)")
            odafc.convert(str(dwg_path), str(dxf_out))
            return dxf_out
    except ImportError:
        pass

    raise RuntimeError(
        f"DWG→DXF conversion needed for {dwg_path.name} but no ODA File "
        f"Converter found. Either install ODAFC or convert externally first."
    )


def _ensure_dxf(src):
    """Return a DXF path for the given source (DWG or DXF).

    Resolution order (first existing wins):
      1. <INPUT>/<base>.dwg        — symlink to ../dwg/<base>.dwg (preferred)
      2. <INPUT>/<base>.dxf        — alternate extension in input/
      3. ../../dxf/<base>_clean3.dxf  — already-cleaned DXF (reuse if present)
      4. ../../dxf/<base>.dxf         — raw prototype DXF
      5. ../../dwg/<base>.dwg         — original DWG at top level

    If a .dwg candidate is selected but DWG→DXF conversion is unavailable,
    we skip to the next candidate (so we don't fail loudly just because
    ODA isn't installed — we'll happily use the already-cleaned DXF).
    """
    # src is <ISGEC>/<APPROACH>/input/<file>
    # parent.parent.parent = ISGEC/
    isgec_root = src.parent.parent.parent
    proto_dxf = isgec_root / "dxf"
    proto_dwg = isgec_root / "dwg"

    if src.suffix.lower() == ".dwg":
        candidates = [
            src,                                          # 1. <INPUT>/<base>.dwg
            src.with_suffix(".dxf"),                      # 2. <INPUT>/<base>.dxf
            proto_dxf / f"{src.stem}_clean3.dxf",         # 3. dxf/<base>_clean3.dxf
            proto_dxf / f"{src.stem}.dxf",                # 4. dxf/<base>.dxf
        ]
    else:
        candidates = [
            src,                                          # 1. <INPUT>/<base>.dxf
            proto_dxf / f"{src.stem}_clean3.dxf",         # 2. dxf/<base>_clean3.dxf
            proto_dxf / f"{src.stem}.dxf",                # 3. dxf/<base>.dxf
            proto_dwg / f"{src.stem}.dwg",                # 4. dwg/<base>.dwg
        ]

    for cand in candidates:
        if not cand.exists():
            continue
        # If candidate is .dwg, try to convert; skip silently on failure
        if cand.suffix.lower() == ".dwg":
            try:
                return _find_dxf_for_dwg(cand)
            except RuntimeError:
                continue
        return cand  # .dxf directly

    raise FileNotFoundError(
        f"No usable input found for {src.stem}.\n"
        f"Tried: {candidates}\n"
        f"Place a DWG (with ODA File Converter) or DXF in {INPUT}/"
    )


# ---- Step 2: strip annotations ---------------------------------------------
ANNOT_TYPES = {"DIMENSION", "MTEXT", "LEADER", "MLEADER", "ATTRIB"}


def strip_annotations(doc, *, is_mech):
    """Remove annotation entities (DIMENSION/MTEXT/LEADER/ATTRIB/MLEADER)
    from the entire document, EXCEPT for TP104-* grid labels.

    Returns (removed_count, kept_grid_labels).
    """
    msp = doc.modelspace()
    removed = 0
    kept_grid = 0

    def should_keep(entity):
        # Keep TP104-* TEXT entities (we still need them for the fit step)
        if entity.dxftype() == "TEXT":
            try:
                if GRID_RE.match(entity.dxf.text.strip()):
                    return True
            except Exception:
                pass
        return False

    # Strip from modelspace
    targets = [e for e in msp if e.dxftype() in ANNOT_TYPES and not should_keep(e)]
    for e in targets:
        try:
            msp.delete_entity(e)
            removed += 1
        except Exception:
            pass

    # Strip annotations INSIDE blocks too (except grid labels)
    for block in list(doc.blocks):
        if block.name.startswith("*"):
            continue
        for e in list(block):
            if e.dxftype() in ANNOT_TYPES and not should_keep(e):
                try:
                    block.delete_entity(e)
                    removed += 1
                except Exception:
                    pass

    # Strip WIPEOUT entities anywhere (they're background masks = always annotation)
    for block in list(doc.blocks):
        if block.name.startswith("*"):
            continue
        for e in list(block):
            if e.dxftype() == "WIPEOUT":
                try:
                    block.delete_entity(e)
                    removed += 1
                except Exception:
                    pass
    for e in list(msp):
        if e.dxftype() == "WIPEOUT":
            try:
                msp.delete_entity(e)
                removed += 1
            except Exception:
                pass

    # Count grid labels
    for t in msp:
        if t.dxftype() == "TEXT" and should_keep(t):
            kept_grid += 1
    for block in doc.blocks:
        if block.name.startswith("*"):
            continue
        for e in block:
            if e.dxftype() == "TEXT" and should_keep(e):
                kept_grid += 1

    return removed, kept_grid


# ---- Step 3: strip markers (MECH only) -------------------------------------
def strip_markers(doc, *, is_mech):
    """Remove marker shapes from the drawing.
    - LWPOLYLINE hexagons on layer BOX (MECH)
    - Anonymous marker blocks not used by kept geometry
    """
    removed_polys = 0
    removed_blocks = 0
    msp = doc.modelspace()

    if is_mech:
        for e in list(msp):
            if e.dxftype() == "LWPOLYLINE" and "BOX" in (e.dxf.layer or "").upper():
                # 6-vertex hexagons (vertices include closing vertex)
                n = sum(1 for _ in e.vertices())
                if n in (5, 6, 7):
                    try:
                        msp.delete_entity(e)
                        removed_polys += 1
                    except Exception:
                        pass

    # Remove orphan anonymous blocks
    referenced = set()
    def walk(e):
        if e.dxftype() == "INSERT":
            referenced.add(e.dxf.name)
    for e in msp:
        walk(e)
    for block in doc.blocks:
        if block.name.startswith("*"):
            continue
        for e in block:
            walk(e)

    candidates = []
    for b in doc.blocks:
        if b.name.startswith("*"):
            continue
        # Don't touch user-named blocks (Part-, Bolt-, GridLine-, etc.)
        if not re.match(r"^A\$C[0-9a-fA-F]+$", b.name):
            continue
        if b.name in referenced:
            continue
        candidates.append(b.name)

    for name in candidates:
        try:
            doc.blocks.delete_block(name, safe=False)
            removed_blocks += 1
        except Exception:
            pass

    return removed_polys, removed_blocks, len(referenced)


# ---- Step 4: strip triangles (MECH only) -----------------------------------
def strip_triangles(doc, *, is_mech):
    """Remove the orphan ACM_FILLED_HALF symbol (block A$C2135de20).
    The block contains 6 SOLID triangles — 2 from MAIN OBJECT view
    (yellow) and 4 from HIDDEN view (green)."""
    if not is_mech:
        return 0, 0

    msp = doc.modelspace()
    block_name = "A$C2135de20"

    insert_removed = 0
    for ins in list(msp):
        if ins.dxftype() == "INSERT" and ins.dxf.name == block_name:
            try:
                msp.unlink_entity(ins)
                insert_removed += 1
            except Exception:
                pass

    block_removed = 0
    if block_name in [b.name for b in doc.blocks]:
        try:
            doc.blocks.delete_block(block_name, safe=False)
            block_removed = 1
        except Exception:
            pass

    return insert_removed, block_removed


# ---- Per-file pipeline ------------------------------------------------------
def process_one(label, src_path, dx_clean_path, dx_clean3_path, *, is_mech):
    print(f"\n── {label} ({src_path.name}) ──")

    # DWG → DXF (or use existing DXF)
    if src_path.suffix.lower() == ".dwg":
        src_dxf = _ensure_dxf(src_path)
        # Copy/link intermediate DXF to work/<base>.dxf
        import shutil
        shutil.copyfile(str(src_dxf), str(dx_clean_path.with_name(
            src_path.stem + ".dxf")))
        src_dxf = dx_clean_path.with_name(src_path.stem + ".dxf")
    else:
        src_dxf = src_path
        import shutil
        shutil.copyfile(str(src_path), str(dx_clean_path.with_name(
            src_path.stem + ".dxf")))
        src_dxf = dx_clean_path.with_name(src_path.stem + ".dxf")

    doc = ezdxf.readfile(str(src_dxf))
    msp = doc.modelspace()

    before = sum(1 for _ in msp)
    print(f"  Before: {before} modelspace entities")

    # Step 2: annotations
    removed_ann, kept_grids = strip_annotations(doc, is_mech=is_mech)
    print(f"  Step 2 — annotations removed: {removed_ann}  "
          f"(grid labels kept: {kept_grids})")

    # Save as _clean.dxf
    doc.saveas(str(dx_clean_path))

    # Step 3 + 4: markers + triangles
    doc = ezdxf.readfile(str(dx_clean_path))
    removed_poly, removed_block, ref_count = strip_markers(doc, is_mech=is_mech)
    print(f"  Step 3 — markers: {removed_poly} hexagon(s), "
          f"{removed_block} orphan block(s) removed "
          f"(referenced blocks: {ref_count})")

    removed_ins, removed_tri_block = strip_triangles(doc, is_mech=is_mech)
    print(f"  Step 4 — triangles: {removed_ins} INSERT(s), "
          f"{removed_tri_block} block removed")

    # Final save as _clean3.dxf
    doc.saveas(str(dx_clean3_path))

    # Verify
    doc2 = ezdxf.readfile(str(dx_clean3_path))
    after = sum(1 for _ in doc2.modelspace())
    types = Counter(e.dxftype() for e in doc2.modelspace())
    print(f"\n  Final: {after} modelspace entities")
    for t, n in sorted(types.items(), key=lambda kv: -kv[1]):
        print(f"    {t:>15}: {n}")
    print(f"  Saved: {dx_clean3_path.name}  "
          f"({os.path.getsize(dx_clean3_path) / 1e6:.2f} MB)")


def main():
    print("=" * 70)
    print("Step 1: CLEAN — DWG→DXF, strip annotations/markers/triangles")
    print("=" * 70)

    WORK.mkdir(parents=True, exist_ok=True)
    if not INPUT.exists():
        INPUT.mkdir(parents=True, exist_ok=True)

    # Process MECH and STR
    try:
        process_one("MECH", MECH_SRC, MECH_CLEAN_DXF, MECH_CLEAN3_DXF,
                     is_mech=True)
    except Exception as ex:
        print(f"  ERROR processing MECH: {ex}")
        sys.exit(1)

    try:
        process_one("STR", STR_SRC, STR_CLEAN_DXF, STR_CLEAN3_DXF,
                     is_mech=False)
    except Exception as ex:
        print(f"  ERROR processing STR: {ex}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("Cleaned DXFs ready:")
    print(f"  {MECH_CLEAN3_DXF}")
    print(f"  {STR_CLEAN3_DXF}")
    print("=" * 70)
    print("\nNext: run scripts/fit.py to derive transform.json")


if __name__ == "__main__":
    main()
