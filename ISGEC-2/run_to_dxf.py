#!/usr/bin/env python3
"""run_to_dxf.py — drive the 3 self-contained dirs (A/B/C) and write
outputs into ISGEC/dxf/.

Inputs (already cleaned3, AS-PER-USER):
  /home/.../ISGEC/dxf/TP-104 MECH GA.dxf
  /home/.../ISGEC/dxf/TP-104 STR GA.dxf

Output:
  /home/.../ISGEC/dxf/superimposed.dxf     ← canonical (approach A)
  /home/.../ISGEC/dxf/superimposed_A.dxf
  /home/.../ISGEC/dxf/superimposed_B.dxf
  /home/.../ISGEC/dxf/superimposed_C.dxf

Strategy:
  - For each approach (A/B/C):
      1. Symlink its work/*_clean3.dxf from the user's cleaned DXFs
         (so clean.py doesn't need to re-strip anything).
      2. Skip clean.py + fit.py (use existing transform.json in each dir).
      3. Run only overlay.py.
      4. Copy the produced out/TP-104 OVERLAY_X.dxf to
         dxf/superimposed_X.dxf.
  - Make dxf/superimposed.dxf a copy of the approach-A output
    (most editable — 2,242 entities, no block wrapper).

Run:  python3 run_to_dxf.py [--rewrite-clean]
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ISGEC = Path("/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC")
DXF_DIR = ISGEC / "dxf"

MECH_INPUT = DXF_DIR / "TP-104 MECH GA_clean3.dxf"
STR_INPUT = DXF_DIR / "TP-104 STR GA_clean3.dxf"

APPROACHES = ["A", "B", "C"]


def here(name):
    return ISGEC / name


def clean_work(approach):
    """Wipe the approach's work/ so we can re-link."""
    work = here(approach) / "work"
    for f in work.glob("*"):
        if f.is_file() or f.is_symlink():
            f.unlink()


def link_inputs(approach):
    """Symlink the user's _clean3.dxf files into the approach's work/."""
    work = here(approach) / "work"
    for src in (MECH_INPUT, STR_INPUT):
        dst = work / src.name
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        os.symlink(str(src), str(dst))


def run_overlay_only(approach):
    """Just run the overlay step (skip clean+fit since we already know them)."""
    scripts = here(approach) / "scripts"
    cmd = ["python3", str(scripts / "overlay.py")]
    print(f"\n  → Running {approach}/scripts/overlay.py ...")
    result = subprocess.run(cmd, cwd=str(here(approach)),
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"overlay.py for {approach} failed")
    print(result.stdout)


def copy_to_dxf(approach):
    """Copy the produced DXF to dxf/superimposed_{X}.dxf."""
    src = here(approach) / "out" / f"TP-104 OVERLAY_{approach}.dxf"
    if not src.exists():
        raise FileNotFoundError(src)
    dst = DXF_DIR / f"superimposed_{approach}.dxf"
    shutil.copy2(src, dst)
    size_mb = dst.stat().st_size / 1e6
    print(f"  ✓ {approach}: {src.name} → {dst.name} ({size_mb:.2f} MB)")
    return dst


def make_canonical():
    """Make dxf/superimposed.dxf = approach-A output (most editable)."""
    src = DXF_DIR / "superimposed_A.dxf"
    dst = DXF_DIR / "superimposed.dxf"
    shutil.copy2(src, dst)
    size_mb = dst.stat().st_size / 1e6
    print(f"  ✓ canonical: {dst}  ←  superimposed_A.dxf  ({size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rewrite-clean", action="store_true",
                        help="Re-run clean.py + fit.py + overlay.py (full pipeline)")
    args = parser.parse_args()

    print("═" * 70)
    print("  DRIVE A/B/C → produce dxf/superimposed.dxf")
    print("═" * 70)
    print(f"\n  Inputs:")
    print(f"    {MECH_INPUT}  ({MECH_INPUT.stat().st_size / 1e6:.2f} MB)")
    print(f"    {STR_INPUT}  ({STR_INPUT.stat().st_size / 1e6:.2f} MB)")
    print(f"\n  Output:")
    print(f"    {DXF_DIR / 'superimposed.dxf'}")

    # Confirm inputs exist
    if not MECH_INPUT.exists():
        print(f"  ✗ Missing: {MECH_INPUT}")
        return 1
    if not STR_INPUT.exists():
        print(f"  ✗ Missing: {STR_INPUT}")
        return 1

    for approach in APPROACHES:
        print(f"\n{'─' * 70}")
        print(f"  Approach {approach}")
        print(f"{'─' * 70}")

        if args.rewrite_clean:
            print(f"  Full pipeline (clean + fit + overlay) ...")
            subprocess.run(["./run.sh"], cwd=str(here(approach)), check=True)
        else:
            clean_work(approach)
            link_inputs(approach)
            print(f"  Linked cleaned inputs into {approach}/work/")
            run_overlay_only(approach)

        copy_to_dxf(approach)

    # Canonical = A
    print(f"\n{'─' * 70}")
    print(f"  Canonical superimposed.dxf")
    print(f"{'─' * 70}")
    make_canonical()

    print(f"\n{'═' * 70}")
    print(f"  ✓ DONE")
    print(f"{'═' * 70}")
    print(f"\n  Files produced under {DXF_DIR}/:")
    for fname in ("superimposed.dxf", "superimposed_A.dxf",
                  "superimposed_B.dxf", "superimposed_C.dxf"):
        p = DXF_DIR / fname
        if p.exists():
            print(f"    {p.name:35s} {p.stat().st_size / 1e6:>6.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
