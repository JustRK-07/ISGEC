#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
"""Build TP-104 OVERLAY_2block.dxf — Approach B from the docs.

Structure:
  MECH_DRAWING block (red, ACI 1)
    └─ all MECH entities at original MECH world coords
  STR_DRAWING block (blue, ACI 5)
    └─ all STR entities at original STR world coords (NOT transformed)
  Modelspace:
    INSERT MECH_DRAWING  pos=(0, 0)            xscale=1
    INSERT STR_DRAWING   pos=(208247, -179585) xscale=1.0  ← the transform lives here

The math: when a STR entity at world_STR coord is inside STR_DRAWING placed at
(TX, TY) with xscale=1.0, it renders at:
    world_MECH = TX + 1.0 * world_STR

This uses scale=1.0 in BOTH X and Y. The previous 0.8-scale transform was a
misfit that aligned text labels to within 8 units but left gridline LINEs off
by up to 4217 units. The new 1.0-scale transform gives:
  - All 3 labeled Y axes (TP104-1/2/3) align pixel-perfectly (residual 0)
  - Labeled X axes (TP104-A/B/C/D) align to within 683 units max
"""

import ezdxf
from ezdxf.addons.importer import Importer

MECH = ROOT / "dxf/TP-104 MECH GA_clean3.dxf"
STR   = ROOT / "dxf/TP-104 STR GA_clean3.dxf"
OUT = ROOT / "dxf/TP-104 OVERLAY_2block.dxf"

SCALE = 1.0
TX    = 208247.0
TY    = -179585.0

MECH_COLOR = 1   # red   (ACI 1)
STR_COLOR  = 5   # blue  (ACI 5)

MECH_BLOCK = "MECH_DRAWING"
STR_BLOCK  = "STR_DRAWING"


def main():
    out_doc = ezdxf.readfile(MECH)
    out_msp = out_doc.modelspace()

    # 1. Wrap MECH into MECH_BLOCK (no transform — MECH is at origin)
    if MECH_BLOCK in out_doc.blocks:
        out_doc.blocks.delete_block(MECH_BLOCK, safe=False)
    mech_block = out_doc.blocks.new(name=MECH_BLOCK)
    for e in list(out_msp):
        try:
            out_msp.unlink_entity(e)
            mech_block.add_entity(e)
        except Exception as ex:
            print(f"  warn: could not move {e.dxftype()}: {ex}")

    # 2. Import STR — keep all coords at original STR values, leave INSERT
    #    positions and scales as they are in the source
    str_doc = ezdxf.readfile(STR)
    str_msp = str_doc.modelspace()

    imp = Importer(str_doc, out_doc)
    block_map = {}
    for str_block in list(str_doc.blocks):
        if str_block.name.startswith("*"):
            continue
        new_name = imp.import_block(str_block.name, rename=False)
        block_map[str_block.name] = new_name

    mech_handles = {e.dxf.handle for e in out_msp if e.dxf.hasattr("handle")}
    for entity in list(str_msp):
        try:
            imp.import_entity(entity, target_layout=out_msp)
        except Exception:
            pass

    try:
        imp.finalize()
    except Exception:
        pass

    imported_handles = {e.dxf.handle for e in out_msp
                        if e.dxf.hasattr("handle") and e.dxf.handle not in mech_handles}

    # 3. Wrap STR into STR_BLOCK — DO NOT transform anything
    if STR_BLOCK in out_doc.blocks:
        out_doc.blocks.delete_block(STR_BLOCK, safe=False)
    str_block_layout = out_doc.blocks.new(name=STR_BLOCK)

    # Move imported STR entities into STR_BLOCK (no transform)
    str_entities = [
        e for e in list(out_msp)
        if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles
    ]
    for e in str_entities:
        try:
            out_msp.unlink_entity(e)
            str_block_layout.add_entity(e)
        except Exception:
            pass

    # 4. Recolor MECH layers → red (ACI 1)
    for layer in out_doc.layers:
        try:
            layer.dxf.color = MECH_COLOR
        except Exception:
            pass
    for entity in list(mech_block):
        try:
            if entity.dxf.hasattr("color") and entity.dxf.color in (0, 256, None):
                entity.dxf.color = 256  # ByLayer
        except Exception:
            pass

    # 5. STR layers → blue (ACI 5) with _BLUE_ prefix
    blue_layers = set()
    for e in list(str_block_layout):
        try:
            if e.dxf.hasattr("layer"):
                blue_layers.add(e.dxf.layer)
        except Exception:
            pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                if e.dxf.hasattr("layer"):
                    blue_layers.add(e.dxf.layer)

    BLUE_PREFIX = "_BLUE_"
    existing = {l.dxf.name for l in out_doc.layers}
    renames = {}
    for layer in blue_layers:
        if layer.startswith(BLUE_PREFIX):
            continue
        new_name = BLUE_PREFIX + layer
        renames[layer] = new_name
        if new_name not in existing:
            out_doc.layers.add(name=new_name, color=STR_COLOR)
        else:
            try:
                out_doc.layers.get(name=new_name).dxf.color = STR_COLOR
            except Exception:
                pass

    for e in list(str_block_layout):
        try:
            if e.dxf.hasattr("layer") and e.dxf.layer in renames:
                e.dxf.layer = renames[e.dxf.layer]
            # Force inline colors to ByLayer (256) so the layer's blue color shows
            if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
                e.dxf.color = 256
        except Exception:
            pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                if e.dxf.hasattr("layer") and e.dxf.layer in renames:
                    e.dxf.layer = renames[e.dxf.layer]
                # Force inline colors to ByLayer
                try:
                    if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
                        e.dxf.color = 256
                except Exception:
                    pass

    # 6. Add 2 INSERTs at modelspace — MECH at origin, STR with the transform
    out_msp.add_blockref(MECH_BLOCK, insert=(0.0, 0.0, 0.0))
    out_msp.add_blockref(STR_BLOCK, insert=(TX, TY, 0.0),
                          dxfattribs={"xscale": SCALE, "yscale": SCALE})

    out_doc.saveas(OUT)
    print(f"\nSaved {OUT}")
    print(f"  MECH_DRAWING block: contains all {len(list(mech_block))} MECH entities (red)")
    print(f"  STR_DRAWING block:  contains all {len(list(str_block_layout))} STR modelspace entities (blue)")
    print(f"  Inner STR blocks:   {len(block_map)} (Part-, Bolt-, Connection-, GridLine-) (blue)")
    print(f"  Modelspace: 2 INSERTs")
    print(f"    MECH_DRAWING  pos=(0, 0)            xscale=1")
    print(f"    STR_DRAWING   pos=({TX}, {TY})  xscale={SCALE}")

    import os
    print(f"  Size: {os.path.getsize(OUT) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
