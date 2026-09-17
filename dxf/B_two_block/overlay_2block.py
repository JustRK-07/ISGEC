#!/usr/bin/env python3
"""Approach B — 2-block overlay.

Wraps each drawing in its own block, then places two INSERTs at modelspace.
The transform lives in the STR_DRAWING INSERT's (insert, xscale, yscale),
not in the entity coordinates — so geometry stays at its source coords
and you can move/scale the whole STR layer visually with one click.

Structure:
  MECH_DRAWING block (red, ACI 1)
    └─ all MECH entities at original MECH world coords
  STR_DRAWING block (blue, ACI 5)
    └─ all STR entities at original STR world coords (NOT transformed)
  Modelspace:
    INSERT MECH_DRAWING  pos=(0, 0)            xscale=1
    INSERT STR_DRAWING   pos=(tx, ty)          xscale=sx, yscale=sy

Editability: MEDIUM. Click the STR INSERT to grab/move the whole layer;
double-click to enter STR_DRAWING and edit individual entities.

Prerequisite: run fit_transform.py first to produce transform.json.
"""

import json
import os
from pathlib import Path

import ezdxf
from ezdxf.addons.importer import Importer

HERE = Path(__file__).resolve().parent
MECH = HERE.parent / "TP-104 MECH GA_clean3.dxf"
STR = HERE.parent / "TP-104 STR GA_clean3.dxf"
TRANSFORM = HERE.parent / "A_per_entity" / "transform.json"  # shared
OUT = HERE / "TP-104 OVERLAY_B.dxf"

MECH_COLOR = 1   # red
STR_COLOR = 5    # blue
BLUE_PREFIX = "_BLUE_"
MECH_BLOCK = "MECH_DRAWING"
STR_BLOCK = "STR_DRAWING"


def load_transform():
    with open(TRANSFORM) as f:
        t = json.load(f)
    return t["scale_x"], t["scale_y"], t["tx"], t["ty"]


def main():
    print("=" * 70)
    print("Approach B — 2-block overlay (MECH_DRAWING + STR_DRAWING)")
    print("=" * 70)

    sx, sy, tx, ty = load_transform()
    print(f"Transform from {TRANSFORM.name}:")
    print(f"  INSERT STR_DRAWING pos=({tx:.4f}, {ty:.4f})  scale=({sx}, {sy})")

    out_doc = ezdxf.readfile(str(MECH))
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

    # 2. Import STR — keep all coords at original STR values
    str_doc = ezdxf.readfile(str(STR))
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

    # 3. Wrap imported STR entities into STR_BLOCK (no transform)
    if STR_BLOCK in out_doc.blocks:
        out_doc.blocks.delete_block(STR_BLOCK, safe=False)
    str_block_layout = out_doc.blocks.new(name=STR_BLOCK)
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

    # 4. Recolor MECH layers → red
    for layer in out_doc.layers:
        try:
            layer.dxf.color = MECH_COLOR
        except Exception:
            pass
    for entity in list(mech_block):
        try:
            if entity.dxf.hasattr("color") and entity.dxf.color in (0, 256, None):
                entity.dxf.color = 256
        except Exception:
            pass

    # 5. STR layers → blue with _BLUE_ prefix
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
            if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
                e.dxf.color = 256
        except Exception:
            pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                if e.dxf.hasattr("layer") and e.dxf.layer in renames:
                    e.dxf.layer = renames[e.dxf.layer]
                try:
                    if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
                        e.dxf.color = 256
                except Exception:
                    pass

    # 6. Add 2 INSERTs at modelspace
    out_msp.add_blockref(MECH_BLOCK, insert=(0.0, 0.0, 0.0))
    out_msp.add_blockref(STR_BLOCK, insert=(tx, ty, 0.0),
                          dxfattribs={"xscale": sx, "yscale": sy})

    out_doc.saveas(str(OUT))
    print(f"\n✓ Saved {OUT.name}")
    print(f"  MECH_DRAWING block: {len(list(mech_block))} MECH entities (red)")
    print(f"  STR_DRAWING block:  {len(list(str_block_layout))} STR entities (blue)")
    print(f"  Inner STR blocks:   {len(block_map)} (blue)")
    print(f"  Modelspace: 2 INSERTs")
    print(f"    MECH_DRAWING  pos=(0, 0)         xscale=1")
    print(f"    STR_DRAWING   pos=({tx:.4f}, {ty:.4f})  xscale={sx}  yscale={sy}")
    print(f"  Size: {os.path.getsize(OUT) / 1e6:.2f} MB")
    print(f"  Editability: MEDIUM — click STR_DRAWING to grab the whole layer")


if __name__ == "__main__":
    main()
