#!/usr/bin/env python3
"""Overlay TP-104 STR onto TP-104 MECH using a fitted affine transform.

Uses ezdxf's official Importer addon (designed for cross-document transfers).
Then walks the imported entities and applies the scale+translate transform.

Transform: x_m = 0.8 * x_s + 208739.144
           y_m = 0.8 * y_s + (-175320.362)
"""

import ezdxf
from ezdxf.addons.importer import Importer

MECH = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 MECH GA_clean3.dxf"
STR  = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 STR GA_clean3.dxf"
OUT  = "/home/rushabh/Desktop/Rushabh New Laptop Files/desktop/Rushabh/edi_sem_5/ISGEC/dxf/TP-104 OVERLAY.dxf"

SCALE = 1.0
TX    = 208247.0
TY    = -179585.0
STR_PREFIX = "_STR_"


def transform_xy(x, y):
    return (SCALE * x + TX, SCALE * y + TY)


def transform_entity_inplace(entity):
    """Apply the scale+translate transform to an entity in place."""
    t = entity.dxftype()
    try:
        if t in ("LINE", "RAY", "XLINE"):
            entity.dxf.start = transform_xy(entity.dxf.start[0], entity.dxf.start[1])
            entity.dxf.end   = transform_xy(entity.dxf.end[0],   entity.dxf.end[1])

        elif t == "LWPOLYLINE":
            new_pts = [transform_xy(v[0], v[1]) for v in entity.vertices()]
            entity.clear()
            for p in new_pts:
                entity.append_vertices(p)

        elif t == "CIRCLE":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1])
            entity.dxf.radius = entity.dxf.radius * SCALE

        elif t == "ARC":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1])
            entity.dxf.radius = entity.dxf.radius * SCALE

        elif t == "ELLIPSE":
            entity.dxf.center = transform_xy(entity.dxf.center[0], entity.dxf.center[1])
            m = entity.dxf.major_axis
            entity.dxf.major_axis = (m[0] * SCALE, m[1] * SCALE, m[2] * SCALE)

        elif t == "POINT":
            entity.dxf.location = transform_xy(entity.dxf.location[0], entity.dxf.location[1])

        elif t in ("TEXT", "MTEXT"):
            entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1])
            try:
                if entity.dxf.hasattr("alignment_point") and entity.dxf.alignment_point:
                    entity.dxf.alignment_point = transform_xy(entity.dxf.alignment_point[0], entity.dxf.alignment_point[1])
            except Exception:
                pass
            try:
                entity.dxf.height = entity.dxf.height * SCALE
            except Exception:
                pass

        elif t == "INSERT":
            # The block CONTENTS have been transformed to MECH coordinates,
            # so the INSERT just needs to be at (0,0) with scale 1 — the block
            # geometry already sits at its final position.
            entity.dxf.insert = (0.0, 0.0, 0.0)
            try:
                entity.dxf.xscale = 1.0
            except Exception:
                pass
            try:
                entity.dxf.yscale = 1.0
            except Exception:
                pass

        elif t == "SPLINE":
            try:
                cps = list(entity.control_points)
                entity.control_points = [transform_xy(p[0], p[1]) for p in cps]
            except Exception:
                pass
            try:
                fps = list(entity.fit_points)
                entity.fit_points = [transform_xy(p[0], p[1]) for p in fps]
            except Exception:
                pass

        elif t == "HATCH":
            for path in entity.paths:
                try:
                    verts = list(path.vertices)
                    # Vertices may be (x,y) or (x,y,bulge) — preserve bulge
                    new_verts = []
                    for v in verts:
                        if len(v) >= 3:
                            nx, ny = transform_xy(v[0], v[1])
                            new_verts.append((nx, ny, v[2]))
                        else:
                            nx, ny = transform_xy(v[0], v[1])
                            new_verts.append((nx, ny))
                    path.vertices = new_verts
                except Exception:
                    pass

        elif t == "DIMENSION":
            try:
                entity.dxf.insert = transform_xy(entity.dxf.insert[0], entity.dxf.insert[1])
            except Exception:
                pass

        elif t in ("SOLID", "TRACE", "3DFACE"):
            for attr in ("vtx0", "vtx1", "vtx2", "vtx3", "first_corner", "second_corner", "third_corner", "fourth_corner"):
                try:
                    v = getattr(entity.dxf, attr)
                    setattr(entity.dxf, attr, transform_xy(v[0], v[1]))
                except Exception:
                    pass

    except Exception as ex:
        pass  # silent for unrecognized types


# ---- MAIN -----------------------------------------------------------------

print(f"Reading MECH from {MECH}")
out_doc = ezdxf.readfile(MECH)
out_msp = out_doc.modelspace()

print(f"Reading STR from {STR}")
str_doc = ezdxf.readfile(STR)
str_msp = str_doc.modelspace()

# Initialize Importer (handles blocks + tables + dependencies)
imp = Importer(str_doc, out_doc)

# Step 1: Import all STR blocks (will be renamed on collision)
print("\nStep 1: Importing STR blocks...")
block_map = {}
for str_block in list(str_doc.blocks):
    if str_block.name.startswith("*"):
        continue
    # Rename strategy: delete any pre-existing target block then import with rename
    target_name = STR_PREFIX + str_block.name
    if target_name in out_doc.blocks:
        try:
            out_doc.blocks.delete_block(target_name, safe=False)
        except Exception:
            pass
    # import_block renames on conflict
    new_name = imp.import_block(str_block.name, rename=False)
    # Rename in out_doc
    if new_name != target_name:
        try:
            block_obj = out_doc.blocks.get(name=new_name)
            if block_obj is not None:
                block_obj.rename(target_name)
                new_name = target_name
        except Exception:
            pass
    block_map[str_block.name] = new_name

print(f"  Imported {len(block_map)} STR blocks (renamed)")

# Step 2: Import STR top-level entities into out_doc's modelspace
print("\nStep 2: Importing STR top-level entities...")
# Snapshot the original MECH modelspace handles BEFORE importing
mech_handles = {e.dxf.handle for e in out_msp if e.dxf.hasattr("handle")}
for entity in list(str_msp):
    try:
        imp.import_entity(entity, target_layout=out_msp)
    except Exception as ex:
        print(f"  warn: import_entity({entity.dxftype()}) failed: {ex}")

# Now find entities that were NOT in the original MECH (i.e., were imported)
imported_handles = set()
for e in list(out_msp):
    try:
        if e.dxf.hasattr("handle") and e.dxf.handle not in mech_handles:
            imported_handles.add(e.dxf.handle)
    except Exception:
        pass
print(f"  Imported {len(imported_handles)} STR entities at modelspace")

# Step 3: Resolve INSERT name remapping
print("\nStep 3: Resolving INSERT references...")
try:
    imp.finalize()
except Exception as ex:
    print(f"  finalize warning: {ex}")

# Step 4: Transform every STR-originated entity in out_doc
# Walk: top-level modelspace + every imported block
print("\nStep 4: Applying scale+translate transform to all imported STR entities...")

# Snapshot the original MECH block handles BEFORE importing
mech_block_handles = set()
for b in out_doc.blocks:
    if b.name.startswith("*"):
        continue
    if not b.name.startswith(STR_PREFIX):
        try:
            rec = b.block_record
            if rec and hasattr(rec, "handle"):
                mech_block_handles.add(rec.handle)
        except Exception:
            pass

ms_count = 0
for e in list(out_msp):
    # Only transform entities that were imported from STR (identified by handle)
    try:
        if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
            transform_entity_inplace(e)
            ms_count += 1
    except Exception:
        pass

# Transform entities inside _STR_* blocks (these are all imported from STR)
block_count = 0
for block_name in block_map.values():
    if block_name in out_doc.blocks:
        block = out_doc.blocks.get(name=block_name)
        for e in list(block):
            try:
                transform_entity_inplace(e)
                block_count += 1
            except Exception:
                pass

print(f"  Transformed {ms_count} modelspace entities")
print(f"  Transformed {block_count} entities inside _STR_* blocks")

# Step 5: Ensure all _STR_* layers exist + add prefix to imported STR layers
print("\nStep 5: Renaming imported STR entity layers to _STR_* prefix...")
existing_layers = {l.dxf.name for l in out_doc.layers}

# First pass: identify layers used by imported STR entities
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
        block = out_doc.blocks.get(name=block_name)
        for e in list(block):
            try:
                layer = e.dxf.layer
                if not layer.startswith(STR_PREFIX):
                    str_layers_in_use.add(layer)
            except Exception:
                pass

# Create the prefixed layers
for layer in str_layers_in_use:
    new_name = STR_PREFIX + layer
    if new_name not in existing_layers:
        out_doc.layers.add(name=new_name, color=2)
        existing_layers.add(new_name)

# Second pass: update entities' layer attribute
layer_renames = {old: STR_PREFIX + old for old in str_layers_in_use}

for e in list(out_msp):
    try:
        if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
            if e.dxf.layer in layer_renames:
                e.dxf.layer = layer_renames[e.dxf.layer]
            # Force inline colors to ByLayer (256) so the layer color shows
            try:
                if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
                    e.dxf.color = 256
            except Exception:
                pass
    except Exception:
        pass

for block_name in block_map.values():
    if block_name in out_doc.blocks:
        block = out_doc.blocks.get(name=block_name)
        for e in list(block):
            try:
                if e.dxf.layer in layer_renames:
                    e.dxf.layer = layer_renames[e.dxf.layer]
                # Force inline colors to ByLayer
                try:
                    if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
                        e.dxf.color = 256
                except Exception:
                    pass
            except Exception:
                pass

print(f"  Renamed {len(layer_renames)} layers to _STR_* prefix")

# Step 6: Save
out_doc.saveas(OUT)
print(f"\nSaved {OUT}")

import os
print(f"  Size: {os.path.getsize(OUT) / 1e6:.2f} MB")
