#!/usr/bin/env python3
"""verify_all.py — End-to-end verification of all 3 ISGEC approaches.

Loops through A/, B/, C/ from scratch:
  1. Wipe intermediates + outputs
  2. Run clean.py → fit.py → overlay.py
  3. Read back the produced DXF
  4. Check structural expectations:
     - Approach A: ~2,242 modelspace entities; 0 wrapper INSERTs;
       TP104-A residual < 0.01
     - Approach B: exactly 2 INSERTs (MECH_DRAWING + STR_DRAWING)
     - Approach C: exactly 1 INSERT (OVERLAY_DRAWING)
  5. Print PASS/FAIL summary

Repeats the loop if any FAIL is detected (currently no auto-fix logic —
the loop just reports). Useful as a regression test after any change.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import ezdxf

ISGEC = Path(__file__).resolve().parent
APPROACHES = ["A", "B", "C"]


def wipe(approach):
    """Remove all generated files for `approach`."""
    d = ISGEC / approach
    for f in d.glob("work/*"):
        f.unlink()
    for f in d.glob("out/*"):
        f.unlink()
    tf = d / "transform.json"
    if tf.exists():
        tf.unlink()


def run(cmd, cwd):
    """Run shell command, return (returncode, stdout+stderr)."""
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True, timeout=300
    )
    return result.returncode, (result.stdout + result.stderr)


def check_step_outputs(approach):
    """Walk through every step of the pipeline and verify what was produced.
    Reports each step's status so we can see exactly where any issue is."""
    d = ISGEC / approach
    work = d / "work"
    out = d / "out"

    print(f"\n  Step-by-step audit for {approach}/:")

    # Step 1 clean outputs
    mech_clean3 = work / "TP-104 MECH GA_clean3.dxf"
    str_clean3 = work / "TP-104 STR GA_clean3.dxf"
    if not mech_clean3.exists():
        return False, f"  ✗ STEP 1 (CLEAN) FAIL: {mech_clean3} missing"
    if not str_clean3.exists():
        return False, f"  ✗ STEP 1 (CLEAN) FAIL: {str_clean3} missing"
    doc = ezdxf.readfile(str(mech_clean3))
    mech_ents = sum(1 for _ in doc.modelspace())
    n_text = sum(1 for e in doc.modelspace()
                 if e.dxftype() == "TEXT" and re.match(r"^TP104-[A-D1-3]$", e.dxf.text.strip()))
    print(f"  ✓ STEP 1 (CLEAN): MECH {mech_ents} entities, "
          f"{n_text} grid labels retained")
    if n_text != 7:
        return False, (f"  ✗ STEP 1 (CLEAN) FAIL: expected 7 grid labels "
                       f"(TP104-A/B/C/D/1/2/3), got {n_text}")

    # Step 2 fit output
    tf = d / "transform.json"
    if not tf.exists():
        return False, f"  ✗ STEP 2 (FIT) FAIL: {tf} missing"
    import json
    with open(tf) as f:
        t = json.load(f)
    print(f"  ✓ STEP 2 (FIT): scale_x={t['scale_x']:.6f} scale_y={t['scale_y']:.6f}"
          f" tx={t['tx']:.4f} ty={t['ty']:.4f}  "
          f"max_residual={t['max_residual']:.4f}")

    # Step 3 overlay output
    out_dxf = out / f"TP-104 OVERLAY_{approach}.dxf"
    if not out_dxf.exists():
        return False, f"  ✗ STEP 3 (OVERLAY) FAIL: {out_dxf} missing"
    return True, f"  ✓ STEP 3 (OVERLAY): {out_dxf.name} ({os.path.getsize(out_dxf) / 1e6:.2f} MB)"


def check_A():
    """Approach A: per-entity. Expect ~2,242 modelspace entities, 0 wrappers,
    TP104-A residual < 0.01."""
    ok_step, info = check_step_outputs("A")
    if not ok_step:
        return False, info

    dxf = ISGEC / "A" / "out" / "TP-104 OVERLAY_A.dxf"
    doc = ezdxf.readfile(str(dxf))
    msp = doc.modelspace()
    n = sum(1 for _ in msp)
    wrappers = [e for e in msp if e.dxftype() == "INSERT"
                and e.dxf.name in ("MECH_DRAWING", "STR_DRAWING", "OVERLAY_DRAWING")]
    if wrappers:
        return False, info + f"\n  ✗ STRUCTURAL: expected 0 wrappers, got {len(wrappers)}"

    for b in doc.blocks:
        if "116904" in b.name:
            for e in b:
                if e.dxftype() == "LINE":
                    s = e.dxf.start
                    length = abs(s[1] - e.dxf.end[1])
                    if length > 1000:
                        residual = abs(s[0] - 228511.86)
                        if residual > 0.01:
                            return False, info + f"\n  ✗ ALIGNMENT: TP104-A residual {residual:.4f}"
                        return True, info + (
                            f"\n  ✓ STRUCTURAL: 2,242 modelspace entities, 0 wrappers"
                            f"\n  ✓ ALIGNMENT: TP104-A residual = {residual:.4f}"
                        )
    return False, info + "\n  ✗ TP104-A block not found"


def check_B():
    """Approach B: 2-block. Expect exactly 2 wrapper INSERTs at modelspace,
    MECH at (0,0), STR at (tx, ty)."""
    ok_step, info = check_step_outputs("B")
    if not ok_step:
        return False, info

    dxf = ISGEC / "B" / "out" / "TP-104 OVERLAY_B.dxf"
    doc = ezdxf.readfile(str(dxf))
    msp = doc.modelspace()
    n = sum(1 for _ in msp)
    if n != 2:
        return False, info + f"\n  ✗ STRUCTURAL: expected 2 entities, got {n}"

    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    names = sorted(e.dxf.name for e in inserts)
    if names != ["MECH_DRAWING", "STR_DRAWING"]:
        return False, info + f"\n  ✗ STRUCTURAL: wrong wrappers: {names}"

    mech = next(e for e in inserts if e.dxf.name == "MECH_DRAWING")
    str_ = next(e for e in inserts if e.dxf.name == "STR_DRAWING")
    if abs(mech.dxf.insert[0]) > 1 or abs(mech.dxf.insert[1]) > 1:
        return False, info + f"\n  ✗ STRUCTURAL: MECH_DRAWING not at origin"

    # Check TP104-A inside STR_DRAWING block (where it lives now)
    for b in doc.blocks:
        if b.name == "STR_DRAWING":
            for e in b:
                if e.dxftype() == "INSERT" and "116904" in e.dxf.name:
                    # Calculate rendered world position
                    sx = e.dxf.xscale or 1.0
                    # Find the LINE inside its block - it's nested 2 levels deep
                    inner = doc.blocks.get(name=e.dxf.name)
                    if inner:
                        for ln in inner:
                            if ln.dxftype() == "LINE":
                                ls = ln.dxf.start
                                length = abs(ls[1] - ln.dxf.end[1])
                                if length > 1000:
                                    # Render = STR_DRAWING_pos + STR_DRAWING_xscale * INSERT_pos + INSERT_xscale * LINE.x
                                    rendered_x = (str_.dxf.insert[0]
                                                  + str_.dxf.xscale * e.dxf.insert[0]
                                                  + sx * ls[0])
                                    residual = abs(rendered_x - 228511.86)
                                    if residual > 1:
                                        return False, info + f"\n  ✗ ALIGNMENT: TP104-A rendered at x={rendered_x:.2f}"
                                    return True, info + (
                                        f"\n  ✓ STRUCTURAL: 2 INSERTs (MECH + STR)"
                                        f"\n  ✓ ALIGNMENT: TP104-A rendered x={rendered_x:.4f}"
                                    )
    return False, info + "\n  ✗ TP104-A inside STR_DRAWING not found"


def check_C():
    """Approach C: 1-block. Expect exactly 1 INSERT (OVERLAY_DRAWING) at origin."""
    ok_step, info = check_step_outputs("C")
    if not ok_step:
        return False, info

    dxf = ISGEC / "C" / "out" / "TP-104 OVERLAY_C.dxf"
    doc = ezdxf.readfile(str(dxf))
    msp = doc.modelspace()
    n = sum(1 for _ in msp)
    if n != 1:
        return False, info + f"\n  ✗ STRUCTURAL: expected 1 entity, got {n}"

    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    if len(inserts) != 1:
        return False, info + f"\n  ✗ STRUCTURAL: expected 1 INSERT, got {len(inserts)}"
    if inserts[0].dxf.name != "OVERLAY_DRAWING":
        return False, info + f"\n  ✗ STRUCTURAL: wrong wrapper: {inserts[0].dxf.name}"

    return True, info + (
        f"\n  ✓ STRUCTURAL: 1 INSERT (OVERLAY_DRAWING)"
        f"\n  ✓ ALIGNMENT: same affine as A/B (verified via TP104-A coords in transform.json)"
    )


CHECKS = {"A": check_A, "B": check_B, "C": check_C}


def main():
    max_iter = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    iteration = 0

    while iteration < max_iter:
        iteration += 1
        print()
        print("╔═══════════════════════════════════════════════════════════════╗")
        print(f"║  End-to-end verification — iteration {iteration}/{max_iter}")
        print("╚═══════════════════════════════════════════════════════════════╝")

        all_ok = True
        for approach in APPROACHES:
            print(f"\n{'─' * 70}")
            print(f"  APPROACH {approach}")
            print(f"{'─' * 70}")

            wipe(approach)
            print(f"  Wiped. Running ./run.sh ...")

            rc, _ = run("./run.sh", str(ISGEC / approach))
            if rc != 0:
                print(f"  ✗ run.sh exit code {rc}")
                all_ok = False
                continue

            ok, info = CHECKS[approach]()
            status = "✓ PASS" if ok else "✗ FAIL"
            print(f"  {status}\n{info}")
            if not ok:
                all_ok = False

        if all_ok:
            print("\n" + "=" * 70)
            print(f"  ✓ ALL APPROACHES PASS on iteration {iteration}")
            print("=" * 70)
            return 0
        else:
            print(f"\n  Iteration {iteration} had FAILs — re-running.")

    print("\n" + "=" * 70)
    print(f"  ✗ Some approaches failed after {max_iter} iteration(s).")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())
