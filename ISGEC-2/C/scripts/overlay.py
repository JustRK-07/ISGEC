#!/usr/bin/env python3
"""overlay.py — Step 3 of the overlay pipeline (Approach C: 1-block).

Imports STR into MECH, transforms every STR entity via the gridline-
derived affine (using the INSERT.pos + xscale pre-scale to convert block
local coords → STR world coords), then wraps everything (MECH + STR)
into a single OVERLAY_DRAWING block. Modelspace has exactly 1 INSERT.

Structure:
  OVERLAY_DRAWING block (single block)
    ├─ 289 MECH entities (red)
    └─ 2,242 pre-scaled + transformed STR entities (blue)
  Modelspace:
    INSERT OVERLAY_DRAWING pos=(0, 0)  xscale=1

Editability: LOW — the entire overlay is one block. Move/scale it as a
unit with one click. To edit individual entities, double-click into
OVERLAY_DRAWING.

Prerequisite: run scripts/clean.py and scripts/fit.py first.

Usage:
  python3 scripts/overlay.py
"""

import json
import os
import sys
from pathlib import Path

import ezdxf
from ezdxf.addons.importer import Importer

HERE = Path(__file__).resolve().parent
APPROACH_DIR = HERE.parent
WORK = APPROACH_DIR / "work"
OUT_DIR = APPROACH_DIR / "out"

MECH = WORK / "TP-104 MECH GA_clean3.dxf"
STR = WORK / "TP-104 STR GA_clean3.dxf"
TRANSFORM = APPROACH_DIR / "transform.json"
OUT = OUT_DIR / "TP-104 OVERLAY_C.dxf"

MECH_COLOR = 1
STR_COLOR = 5
STR_PREFIX = "_STR_"
OVERLAY_BLOCK = "OVERLAY_DRAWING"

# Reuse Approach A's helpers (prescale + affine transform)
sys.path.insert(0, str(HERE))  # same dir
from overlay_helper import (  # noqa: E402
    prescale_entity, transform_entity_inplace,
)


def load_transform():
    with open(TRANSFORM) as f:
        t = json.load(f)
    return t["scale_x"], t["scale_y"], t["tx"], t["ty"]


def main():
    print("=" * 70)
    print("Step 3: OVERLAY — Approach C (1-block)")
    print("=" * 70)

    ax, ay, bx, by = load_transform()
    print(f"Transform from {TRANSFORM.name}:")
    print(f"  x_m = {ax:.6f} · x_s + {bx:.4f}")
    print(f"  y_m = {ay:.6f} · y_s + {by:.4f}")

    out_doc = ezdxf.readfile(str(MECH))
    out_msp = out_doc.modelspace()

    str_doc = ezdxf.readfile(str(STR))
    str_msp = str_doc.modelspace()

    # Step 1: Import all STR blocks
    print("\nStep 1: Importing STR blocks...")
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
    print(f"  Imported {len(block_map)} STR blocks (prefixed with {STR_PREFIX!r})")

    # Step 2: Import STR top-level entities
    print("\nStep 2: Importing STR top-level entities...")
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
    print(f"  Imported {len(imported_handles)} STR entities at modelspace")

    # Step 3: Pre-scale block contents then transform everything
    print("\nStep 3: Pre-scaling + transforming STR geometry...")
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

    block_count = 0
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                transform_entity_inplace(e, ax, ay, bx, by)
        except Exception:
            pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            block = out_doc.blocks.get(name=block_name)
            for e in list(block):
                try:
                    transform_entity_inplace(e, ax, ay, bx, by)
                    block_count += 1
                except Exception:
                    pass
    print(f"  Pre-scaled + transformed (entities-in-imported-blocks count: {block_count})")

    # Step 4: Rename STR layers + force ByLayer color
    print("\nStep 4: Renaming STR layers + recoloring to blue...")
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

    # Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_doc.saveas(str(OUT))
    print(f"\n✓ Saved {OUT.name}")
    print(f"  OVERLAY_DRAWING block: {len(list(overlay_block))} entities (MECH red + STR blue)")
    print(f"  Modelspace: 1 INSERT at origin")
    print(f"  Size: {os.path.getsize(OUT) / 1e6:.2f} MB")
    print(f"  Editability: LOW — single grab, the whole overlay moves as one")


if __name__ == "__main__":
    main()
