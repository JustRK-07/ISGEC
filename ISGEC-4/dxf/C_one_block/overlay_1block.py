#!/usr/bin/env python3
"""Approach C — 1-block overlay.

Imports STR into MECH and applies the transform to every STR entity,
then wraps EVERYTHING (MECH + transformed STR) into a single OVERLAY_DRAWING
block. Modelspace contains exactly one INSERT at the origin.

Structure:
  OVERLAY_DRAWING block
    ├─ all MECH entities (red)
    └─ all STR entities transformed to MECH coords (blue)
  Modelspace:
    INSERT OVERLAY_DRAWING  pos=(0, 0)  xscale=1

Editability: LOW. The whole overlay is one block; you'd double-click into
the block to edit individual entities. Useful when you want the overlay
to move as a single unit (one-click grab, no per-layer fiddling).

Prerequisite: run fit_transform.py first to produce transform.json.
"""

import json
import os
from pathlib import Path

import ezdxf
from ezdxf.addons.importer import Importer

# Reuse Approach A's helpers so all 3 overlays stay consistent
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "A_per_entity"))
from overlay import transform_entity_inplace, prescale_entity, STR_PREFIX  # noqa: E402

HERE = Path(__file__).resolve().parent
MECH = HERE.parent / "TP-104 MECH GA_clean3.dxf"
STR = HERE.parent / "TP-104 STR GA_clean3.dxf"
TRANSFORM = HERE / "transform.json"
OUT = HERE / "TP-104 OVERLAY_C.dxf"

MECH_COLOR = 1   # red
STR_COLOR = 5    # blue
OVERLAY_BLOCK = "OVERLAY_DRAWING"


def load_transform():
    with open(TRANSFORM) as f:
        t = json.load(f)
    return t["scale_x"], t["scale_y"], t["tx"], t["ty"]


def main():
    print("=" * 70)
    print("Approach C — 1-block overlay (MECH + STR → OVERLAY_DRAWING)")
    print("=" * 70)

    ax, ay, bx, by = load_transform()
    print(f"Transform from {TRANSFORM.name}:")
    print(f"  x_m = {ax:.6f} · x_s + {bx:.4f}")
    print(f"  y_m = {ay:.6f} · y_s + {by:.4f}")

    out_doc = ezdxf.readfile(str(MECH))
    out_msp = out_doc.modelspace()

    str_doc = ezdxf.readfile(str(STR))
    str_msp = str_doc.modelspace()

    # Step 1: Import all STR blocks (prefixed)
    imp = Importer(str_doc, out_doc)
    block_map = {}
    for str_block in list(str_doc.blocks):
        if str_block.name.startswith("*"):
            continue
        target = STR_PREFIX + str_block.name
        if target in out_doc.blocks:
            try:
                out_doc.blocks.delete_block(target, safe=False)
            except Exception:
                pass
        new_name = imp.import_block(str_block.name, rename=False)
        if new_name != target:
            try:
                block_obj = out_doc.blocks.get(name=new_name)
                if block_obj is not None:
                    block_obj.rename(target)
                    new_name = target
            except Exception:
                pass
        block_map[str_block.name] = new_name
    print(f"Imported {len(block_map)} STR blocks (prefixed with {STR_PREFIX!r})")

    # Step 2: Import STR top-level entities
    mech_handles = {e.dxf.handle for e in out_msp if e.dxf.hasattr("handle")}
    for entity in list(str_msp):
        try:
            imp.import_entity(entity, target_layout=out_msp)
        except Exception as ex:
            print(f"  warn: import_entity({entity.dxftype()}) failed: {ex}")

    try:
        imp.finalize()
    except Exception:
        pass

    imported_handles = {e.dxf.handle for e in out_msp
                        if e.dxf.hasattr("handle") and e.dxf.handle not in mech_handles}
    print(f"Imported {len(imported_handles)} STR entities at modelspace")

    # Step 3: Pre-scale block contents (undo source's 0.8 scale at INSERT
    # level) then transform every entity by the affine.
    #
    # Same architecture as Approach A. In source STR, every INSERT is at
    # (971.5, 4264.2) with xscale=0.8; the visible geometry is INSERT_pos +
    # xscale * block_content. We bake xscale into the block contents,
    # snap each INSERT to (0,0) with xscale=1, then apply the affine to
    # everything to land it in MECH coords.

    print("Pre-scaling block contents + transforming STR entities...")
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                if e.dxftype() == "INSERT":
                    src_block_name = e.dxf.name
                    if src_block_name in out_doc.blocks:
                        block = out_doc.blocks.get(name=src_block_name)
                        sx = e.dxf.xscale or 1.0
                        sy = e.dxf.yscale if e.dxf.hasattr("yscale") and e.dxf.yscale else sx
                        ip_x, ip_y = e.dxf.insert[0], e.dxf.insert[1]
                        for be in list(block):
                            prescale_entity(be, sx, sy, ip_x, ip_y)
                    e.dxf.insert = (0.0, 0.0, 0.0)
                    e.dxf.xscale = 1.0
                    e.dxf.yscale = 1.0
        except Exception:
            pass

    ms_count = 0
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                transform_entity_inplace(e, ax, ay, bx, by)
                ms_count += 1
        except Exception:
            pass
    block_count = 0
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            block = out_doc.blocks.get(name=block_name)
            for e in list(block):
                try:
                    transform_entity_inplace(e, ax, ay, bx, by)
                    block_count += 1
                except Exception:
                    pass
    print(f"Transformed {ms_count} modelspace entities + {block_count} block entities")

    # Step 4: Rename STR layers + force ByLayer
    str_layers_in_use = set()
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                layer = e.dxf.layer
                if not layer.startswith(STR_PREFIX):
                    str_layers_in_use.add(layer)
        except Exception:
            pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                try:
                    layer = e.dxf.layer
                    if not layer.startswith(STR_PREFIX):
                        str_layers_in_use.add(layer)
                except Exception:
                    pass

    existing_layers = {l.dxf.name for l in out_doc.layers}
    for layer in str_layers_in_use:
        new_name = STR_PREFIX + layer
        if new_name not in existing_layers:
            out_doc.layers.add(name=new_name, color=STR_COLOR)
            existing_layers.add(new_name)

    layer_renames = {old: STR_PREFIX + old for old in str_layers_in_use}
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                if e.dxf.layer in layer_renames:
                    e.dxf.layer = layer_renames[e.dxf.layer]
                if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
                    e.dxf.color = 256
        except Exception:
            pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                try:
                    if e.dxf.layer in layer_renames:
                        e.dxf.layer = layer_renames[e.dxf.layer]
                    if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
                        e.dxf.color = 256
                except Exception:
                    pass

    # Step 5: Recolor MECH layers to red
    for layer in out_doc.layers:
        try:
            if not layer.dxf.name.startswith(STR_PREFIX):
                layer.dxf.color = MECH_COLOR
        except Exception:
            pass

    # Step 6: Wrap EVERYTHING (MECH + STR) into OVERLAY_DRAWING block
    if OVERLAY_BLOCK in out_doc.blocks:
        out_doc.blocks.delete_block(OVERLAY_BLOCK, safe=False)
    overlay_block = out_doc.blocks.new(name=OVERLAY_BLOCK)
    for e in list(out_msp):
        try:
            out_msp.unlink_entity(e)
            overlay_block.add_entity(e)
        except Exception as ex:
            print(f"  warn: could not move {e.dxftype()}: {ex}")

    # Step 7: Add single INSERT at origin
    out_msp.add_blockref(OVERLAY_BLOCK, insert=(0.0, 0.0, 0.0))

    out_doc.saveas(str(OUT))
    print(f"\n✓ Saved {OUT.name}")
    print(f"  OVERLAY_DRAWING block: {len(list(overlay_block))} entities (MECH red + STR blue)")
    print(f"  Modelspace: 1 INSERT at origin")
    print(f"  Size: {os.path.getsize(OUT) / 1e6:.2f} MB")
    print(f"  Editability: LOW — one INSERT, move the whole overlay as one unit")


if __name__ == "__main__":
    main()
