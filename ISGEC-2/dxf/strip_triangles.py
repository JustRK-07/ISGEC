#!/usr/bin/env python3
"""Strip the orphaned ACM_FILLED_HALF symbol (block A$C2135de20) from the
cleaned MECH DXF.

Why this block is here: this anonymous block is AutoCAD's standard symbol
for a half-section pillow-block / bearing-housing. It contains two SOLID
triangles (yellow on MAIN OBJECT, green on HIDDEN) that fill the half-
section symbol.

Why it can go: the block is only INSERTed once at modelspace at
(220016.4, -163563.7), and that INSERT is completely detached from the
rest of the mechanical geometry — no dimensions, BOM, or other geometry
references it. Looks like leftover symbol-library geometry.

What this does:
  1. Removes the lone A$C2135de20 INSERT at modelspace.
  2. Deletes the now-unreferenced A$C2135de20 block.
  3. Saves as TP-104 MECH GA_clean3.dxf.
  4. Reports before/after entity counts.

Note: the child block A$C34ae56dc is NOT deleted — it's still used by
A$C1f4f58bd and A$Cde9606d0 (other anonymous compound components).
"""

import ezdxf

SRC = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 MECH GA_clean2.dxf"
DST = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 MECH GA_clean3.dxf"

BLOCK_NAME = "A$C2135de20"


def count_modelspace(doc):
    """Return total entity count + per-type breakdown at modelspace."""
    from collections import Counter
    c = Counter()
    for e in doc.modelspace():
        c[e.dxftype()] += 1
    return c


def main():
    print(f"Reading {SRC}")
    doc = ezdxf.readfile(SRC)
    msp = doc.modelspace()

    before = count_modelspace(doc)
    print(f"\nBefore: {sum(before.values())} entities at modelspace")
    print(f"  SOLID:   {before.get('SOLID', 0)}")
    print(f"  INSERT:  {before.get('INSERT', 0)}")
    print(f"  TRACE:   {before.get('TRACE', 0)}")

    # Count target INSERTs before removal
    target_inserts = [e for e in msp
                      if e.dxftype() == "INSERT" and e.dxf.name == BLOCK_NAME]
    print(f"\nFound {len(target_inserts)} INSERT(s) of {BLOCK_NAME} at modelspace:")
    for ins in target_inserts:
        print(f"  pos=({ins.dxf.insert[0]:.2f}, {ins.dxf.insert[1]:.2f})  "
              f"xscale={ins.dxf.xscale}  layer={ins.dxf.layer}")

    # 1. Remove the INSERTs
    for ins in target_inserts:
        msp.unlink_entity(ins)
    print(f"\nRemoved {len(target_inserts)} INSERT(s)")

    # 2. Delete the now-unreferenced block (if it exists)
    if BLOCK_NAME in [b.name for b in doc.blocks]:
        try:
            doc.blocks.delete_block(BLOCK_NAME, safe=False)
            print(f"Deleted block {BLOCK_NAME}")
        except Exception as ex:
            print(f"warn: could not delete block {BLOCK_NAME}: {ex}")
    else:
        print(f"Block {BLOCK_NAME} not found (already gone?)")

    # 3. Save
    doc.saveas(DST)
    print(f"\nSaved {DST}")

    # 4. Verify
    doc2 = ezdxf.readfile(DST)
    after = count_modelspace(doc2)
    print(f"\nAfter: {sum(after.values())} entities at modelspace")
    print(f"  SOLID:   {after.get('SOLID', 0)}")
    print(f"  INSERT:  {after.get('INSERT', 0)}")
    print(f"  TRACE:   {after.get('TRACE', 0)}")

    print(f"\nDelta:")
    print(f"  SOLID:   {before.get('SOLID', 0):>4} -> {after.get('SOLID', 0):>4}  "
          f"({after.get('SOLID', 0) - before.get('SOLID', 0):+d})")
    print(f"  INSERT:  {before.get('INSERT', 0):>4} -> {after.get('INSERT', 0):>4}  "
          f"({after.get('INSERT', 0) - before.get('INSERT', 0):+d})")
    print(f"  TRACE:   {before.get('TRACE', 0):>4} -> {after.get('TRACE', 0):>4}  "
          f"({after.get('TRACE', 0) - before.get('TRACE', 0):+d})")

    import os
    print(f"\nFile size: {os.path.getsize(DST) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
