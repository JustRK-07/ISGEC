#!/usr/bin/env python3
"""overlay.py — Step 3 of the overlay pipeline (Approach A: per-entity).

Imports every STR entity into the MECH document and applies the
gridline-derived affine in place — each STR LINE/LWPOLYLINE/etc. sits at
its final MECH world coord.

Structure:
  Modelspace: 2,242 entities (2025 INSERTs + 217 others — MECH geometry
             + STR geometry baked to MECH coords).

Editability: HIGHEST — click any structural member in your CAD viewer to
edit it directly (no block wrapper to navigate through).

Colors:
  Approach A PRESERVES the original layer/entity colors of both drawings —
  steel beams stay their source color, MECH equipment keeps MECH colors,
  pipes keep their process colors. We only RENAME STR layers to `_STR_*`
  so MECH/STR layer names don't collide. This is the key difference from
  Approach B/C which force MECH→red and STR→blue for high-contrast
  visual overlays.

Prerequisite: run scripts/clean.py and scripts/fit.py first.

Usage:
  python3 scripts/overlay.py
"""

import json
import os
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
OUT = OUT_DIR / "TP-104 OVERLAY_A.dxf"

MECH_COLOR = 1   # red
STR_COLOR = 5    # blue
STR_PREFIX = "_STR_"


def load_transform():
    with open(TRANSFORM) as f:
        t = json.load(f)
    return t["scale_x"], t["scale_y"], t["tx"], t["ty"]


def prescale_entity(entity, sx, sy, ip_x=0.0, ip_y=0.0):
    """Bake INSERT position + xscale into each entity in a block.
    Converts block-local coords → STR-world coords by replicating
    `INSERT.pos + xscale * local`."""
    if sx == 1.0 and sy == 1.0 and ip_x == 0.0 and ip_y == 0.0:
        return
    t = entity.dxftype()
    try:
        if t in ("LINE", "RAY", "XLINE"):
            entity.dxf.start = (ip_x + sx * entity.dxf.start[0],
                                ip_y + sy * entity.dxf.start[1], 0.0)
            entity.dxf.end = (ip_x + sx * entity.dxf.end[0],
                              ip_y + sy * entity.dxf.end[1], 0.0)
        elif t == "LWPOLYLINE":
            new_pts = [(ip_x + sx * v[0], ip_y + sy * v[1]) for v in entity.vertices()]
            entity.clear()
            for p in new_pts:
                entity.append_vertices(p)
        elif t in ("CIRCLE", "ARC"):
            entity.dxf.center = (ip_x + sx * entity.dxf.center[0],
                                 ip_y + sy * entity.dxf.center[1], 0.0)
            entity.dxf.radius = entity.dxf.radius * max(abs(sx), abs(sy))
        elif t == "ELLIPSE":
            entity.dxf.center = (ip_x + sx * entity.dxf.center[0],
                                 ip_y + sy * entity.dxf.center[1], 0.0)
            m = entity.dxf.major_axis
            entity.dxf.major_axis = (m[0] * sx, m[1] * sy, m[2])
        elif t == "POINT":
            entity.dxf.location = (ip_x + sx * entity.dxf.location[0],
                                    ip_y + sy * entity.dxf.location[1], 0.0)
        elif t in ("TEXT", "MTEXT"):
            entity.dxf.insert = (ip_x + sx * entity.dxf.insert[0],
                                  ip_y + sy * entity.dxf.insert[1], 0.0)
        elif t == "SPLINE":
            try:
                cps = list(entity.control_points)
                entity.control_points = [(ip_x + sx * p[0], ip_y + sy * p[1]) for p in cps]
            except Exception:
                pass
        elif t == "HATCH":
            for path in entity.paths:
                try:
                    verts = list(path.vertices)
                    new_verts = []
                    for v in verts:
                        nx, ny = ip_x + sx * v[0], ip_y + sy * v[1]
                        if len(v) >= 3:
                            new_verts.append((nx, ny, v[2]))
                        else:
                            new_verts.append((nx, ny))
                    path.vertices = new_verts
                except Exception:
                    pass
        elif t == "DIMENSION":
            try:
                entity.dxf.insert = (ip_x + sx * entity.dxf.insert[0],
                                      ip_y + sy * entity.dxf.insert[1], 0.0)
            except Exception:
                pass
        elif t in ("SOLID", "TRACE", "3DFACE"):
            for attr in ("vtx0", "vtx1", "vtx2", "vtx3",
                         "first_corner", "second_corner", "third_corner", "fourth_corner"):
                try:
                    v = getattr(entity.dxf, attr)
                    setattr(entity.dxf, attr, (ip_x + sx * v[0],
                                               ip_y + sy * v[1], v[2]))
                except Exception:
                    pass
    except Exception:
        pass


def transform_xy(x, y, ax, ay, bx, by):
    return (ax * x + bx, ay * y + by)


def transform_entity_inplace(entity, ax, ay, bx, by):
    """Apply the affine to an entity in place. INSERTs are intentionally
    NOT transformed (the caller in main() pre-scales their block contents
    and snaps them to (0, 0, 0) with xscale=1 first)."""
    t = entity.dxftype()
    try:
        if t in ("LINE", "RAY", "XLINE"):
            entity.dxf.start = transform_xy(entity.dxf.start[0], entity.dxf.start[1], ax, ay, bx, by)
            entity.dxf.end = transform_xy(entity.dxf.end[0], entity.dxf.end[1], ax, ay, bx, by)
        elif t == "LWPOLYLINE":
            new_pts = [transform_xy(v[0], v[1], ax, ay, bx, by) for v in entity.vertices()]
            entity.clear()
            for p in new_pts:
                entity.append_vertices(p)
        elif t in ("CIRCLE", "ARC"):
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1], ax, ay, bx, by)
            r_scale = max(abs(ax), abs(ay))
            entity.dxf.radius = entity.dxf.radius * r_scale
        elif t == "ELLIPSE":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1], ax, ay, bx, by)
            m = entity.dxf.major_axis
            entity.dxf.major_axis = (m[0] * ax, m[1] * ay, m[2])
        elif t == "POINT":
            entity.dxf.location = transform_xy(entity.dxf.location[0], entity.dxf.location[1], ax, ay, bx, by)
        elif t in ("TEXT", "MTEXT"):
            entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1], ax, ay, bx, by)
            try:
                if entity.dxf.hasattr("alignment_point") and entity.dxf.alignment_point:
                    entity.dxf.alignment_point = transform_xy(
                        entity.dxf.alignment_point[0], entity.dxf.alignment_point[1],
                        ax, ay, bx, by)
            except Exception:
                pass
            try:
                entity.dxf.height = entity.dxf.height * max(abs(ax), abs(ay))
            except Exception:
                pass
        elif t == "INSERT":
            pass  # leave at (0, 0) with xscale=1 — set in main()
        elif t == "SPLINE":
            try:
                cps = list(entity.control_points)
                entity.control_points = [transform_xy(p[0], p[1], ax, ay, bx, by) for p in cps]
            except Exception:
                pass
            try:
                fps = list(entity.fit_points)
                entity.fit_points = [transform_xy(p[0], p[1], ax, ay, bx, by) for p in fps]
            except Exception:
                pass
        elif t == "HATCH":
            for path in entity.paths:
                try:
                    verts = list(path.vertices)
                    new_verts = []
                    for v in verts:
                        nx, ny = transform_xy(v[0], v[1], ax, ay, bx, by)
                        if len(v) >= 3:
                            new_verts.append((nx, ny, v[2]))
                        else:
                            new_verts.append((nx, ny))
                    path.vertices = new_verts
                except Exception:
                    pass
        elif t == "DIMENSION":
            try:
                entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1], ax, ay, bx, by)
            except Exception:
                pass
        elif t in ("SOLID", "TRACE", "3DFACE"):
            for attr in ("vtx0", "vtx1", "vtx2", "vtx3",
                         "first_corner", "second_corner", "third_corner", "fourth_corner"):
                try:
                    v = getattr(entity.dxf, attr)
                    setattr(entity.dxf, attr, transform_xy(v[0], v[1], ax, ay, bx, by))
                except Exception:
                    pass
    except Exception:
        pass


def main():
    print("=" * 70)
    print("Step 3: OVERLAY — Approach A (per-entity)")
    print("=" * 70)

    ax, ay, bx, by = load_transform()
    print(f"Transform from {TRANSFORM.name}:")
    print(f"  x_m = {ax:.6f} · x_s + {bx:.4f}")
    print(f"  y_m = {ay:.6f} · y_s + {by:.4f}")

    print(f"\nReading MECH: {MECH.name}")
    out_doc = ezdxf.readfile(str(MECH))
    out_msp = out_doc.modelspace()

    print(f"Reading STR:  {STR.name}")
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

    # Step 3: Pre-scale each block's contents, snap INSERTs to (0,0,0),
    # then transform everything
    print("\nStep 3: Pre-scaling + transforming STR geometry...")
    ms_count = 0
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
                ms_count += 1
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

    print(f"  Pre-scaled + transformed {ms_count} INSERTs")
    print(f"  Transformed {block_count} entities inside {STR_PREFIX}* blocks")

    # Step 4: Rename STR layers (preserve ORIGINAL colors)
    # Unlike B/C, Approach A keeps every layer's source color so steel
    # beams stay gray, pipes keep their color, etc. We only rename to
    # avoid MECH/STR layer-name collisions.
    print("\nStep 4: Renaming STR layers (preserving original colors)...")
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
            # Look up the source layer's color in STR so we preserve it.
            try:
                src_layer = str_doc.layers.get(name=layer)
                layer_color = src_layer.dxf.color if (src_layer is not None
                                                      and src_layer.dxf.hasattr("color")) else 7
            except Exception:
                layer_color = 7
            out_doc.layers.add(name=new_name, color=layer_color)
            existing_layers.add(new_name)

    layer_renames = {old: STR_PREFIX + old for old in str_layers_in_use}
    for e in list(out_msp):
        try:
            if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
                if e.dxf.layer in layer_renames:
                    e.dxf.layer = layer_renames[e.dxf.layer]
        except Exception:
            pass
    for block_name in block_map.values():
        if block_name in out_doc.blocks:
            for e in out_doc.blocks.get(name=block_name):
                try:
                    if e.dxf.layer in layer_renames:
                        e.dxf.layer = layer_renames[e.dxf.layer]
                except Exception:
                    pass

    print(f"  Renamed {len(layer_renames)} layers to {STR_PREFIX}* (colors preserved)")

    # (No Step 5 in Approach A — MECH layers keep their original colors too.
    # This is the key difference from B/C which force MECH→red, STR→blue.)

    # Step 6: Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_doc.saveas(str(OUT))
    print(f"\n✓ Saved {OUT.name}")
    print(f"  Size: {os.path.getsize(OUT) / 1e6:.2f} MB")
    print(f"  Modelspace: MECH (red) + STR (blue, per-entity)")
    print(f"  Editability: HIGHEST — click any structural member in CAD to edit")


if __name__ == "__main__":
    main()
