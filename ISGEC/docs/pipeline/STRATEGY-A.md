# Strategy A — Per-Entity Overlay

> **Source:** `ISGEC/A/scripts/overlay.py` (16 KB), `ISGEC/A/README.md`
> **Output:** `ISGEC/A/out/TP-104 OVERLAY_A.dxf` (~18 MB)

**Every STR entity is copied into MECH's modelspace and baked at its final (transformed) coordinates.** STR geometry is not wrapped in a block — it's loose in modelspace alongside MECH.

---

## Color policy

**Approach A preserves ORIGINAL colors.** When STR blocks/entities are imported:

1. Layers are renamed `LayerX` → `_STR_LayerX` to avoid MECH/STR name collisions.
2. The new `_STR_LayerX` layer is created with the **source layer's color** (looked up from `str_doc.layers`).
3. Per-entity color overrides on STR entities are **kept** (not reset to ByLayer).
4. MECH layers are untouched (every one of the 17 original layer colors is preserved).

So a steel beam stays gray, a magenta hatch keeps its source color, an orange pipe stays orange. Use this approach when you want the overlay to look **faithful** to the source drawings.

> See [`STRATEGY-B.md`](./STRATEGY-B.md) or [`STRATEGY-C.md`](./STRATEGY-C.md) if you want the traditional red-MECH / blue-STR forced color scheme.

---

## Editability

**HIGHEST** of the three approaches. Click any structural member in your CAD viewer to edit it directly — there's no block wrapper to navigate through.

This is the canonical default for downstream design work where individual member editing matters.

---

## Structure

```
Modelspace (2,242 entities):
  ├─ 1,953 STR INSERTs
  │   └─ snapped to (0, 0, 0) with xscale = 1
  │      └─ block contents pre-scaled + affine-transformed
  ├─ 1,953 STR top-level entities (pre-scaled + affine-transformed)
  └─ 289 MECH entities (untouched)

Layers:
  ├─ MECH original layers (17 unique colors preserved)
  └─ _STR_LayerX (color = source layer color)
```

---

## Algorithm

### 1. Import STR blocks

```python
imp = Importer(str_doc, out_doc)
block_map = {}
for str_block in list(str_doc.blocks):
    if str_block.name.startswith("*"): continue
    target = STR_PREFIX + str_block.name   # _STR_GridLine-A
    if target in out_doc.blocks:
        out_doc.blocks.delete_block(target, safe=False)
    new_name = imp.import_block(str_block.name, rename=False)
    if new_name != target:
        # rename to standard target name
        block_obj = out_doc.blocks.get(name=new_name)
        block_obj.rename(target)
        new_name = target
    block_map[str_block.name] = new_name
```

### 2. Import STR top-level entities

```python
mech_handles = {e.dxf.handle for e in out_msp if e.dxf.hasattr("handle")}
for entity in list(str_msp):
    imp.import_entity(entity, target_layout=out_msp)
imp.finalize()

imported_handles = {e.dxf.handle for e in out_msp
                    if e.dxf.hasattr("handle") and e.dxf.handle not in mech_handles}
```

### 3. Pre-scale + transform

For each imported INSERT:
```python
src_block_name = e.dxf.name
block = out_doc.blocks.get(name=src_block_name)
sx = e.dxf.xscale or 1.0
sy = e.dxf.yscale if e.dxf.hasattr("yscale") and e.dxf.yscale else sx
ip_x, ip_y = e.dxf.insert[0], e.dxf.insert[1]
for be in list(block):
    prescale_entity(be, sx, sy, ip_x, ip_y)
e.dxf.insert = (0.0, 0.0, 0.0)
e.dxf.xscale = 1.0
e.dxf.yscale = 1.0
```

Then transform every imported entity in-place:
```python
for e in list(out_msp):
    if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
        transform_entity_inplace(e, ax, ay, bx, by)
for block_name in block_map.values():
    block = out_doc.blocks.get(name=block_name)
    for be in list(block):
        transform_entity_inplace(be, ax, ay, bx, by)
```

### 4. Rename STR layers (preserving colors)

```python
# Collect all STR layer names in use
str_layers_in_use = set()
for e in list(out_msp):
    if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
        layer = e.dxf.layer
        if not layer.startswith(STR_PREFIX):
            str_layers_in_use.add(layer)

# Create new _STR_* layers with source color
existing_layers = {l.dxf.name for l in out_doc.layers}
for layer in str_layers_in_use:
    new_name = STR_PREFIX + layer
    if new_name not in existing_layers:
        src_layer = str_doc.layers.get(name=layer)
        layer_color = src_layer.dxf.color if src_layer else 7
        out_doc.layers.add(name=new_name, color=layer_color)

# Rename references
layer_renames = {old: STR_PREFIX + old for old in str_layers_in_use}
for e in list(out_msp):
    if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
        if e.dxf.layer in layer_renames:
            e.dxf.layer = layer_renames[e.dxf.layer]
```

### 5. Save

```python
OUT_DIR.mkdir(parents=True, exist_ok=True)
out_doc.saveas(str(OUT))   # → out/TP-104 OVERLAY_A.dxf
```

---

## `transform_entity_inplace` — handles every entity type

```python
def transform_entity_inplace(entity, ax, ay, bx, by):
    """Apply the affine to an entity in place. INSERTs are intentionally
    NOT transformed (the caller pre-scales their block contents and snaps
    them to (0, 0, 0) with xscale=1 first)."""
    t = entity.dxftype()
    if t in ("LINE", "RAY", "XLINE"):
        entity.dxf.start = transform_xy(entity.dxf.start[0], entity.dxf.start[1], ax, ay, bx, by)
        entity.dxf.end   = transform_xy(entity.dxf.end[0],   entity.dxf.end[1],   ax, ay, bx, by)
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
        entity.dxf.center = transform_xy(...)
        m = entity.dxf.major_axis
        entity.dxf.major_axis = (m[0] * ax, m[1] * ay, m[2])
    elif t == "POINT":
        entity.dxf.location = transform_xy(...)
    elif t in ("TEXT", "MTEXT"):
        entity.dxf.insert = transform_xy(...)
        # height scales too
    elif t == "INSERT":
        pass  # leave at (0, 0) with xscale=1 — set in main()
    elif t == "SPLINE":
        # transform control_points + fit_points
    elif t == "HATCH":
        # transform path vertices
    elif t == "DIMENSION":
        entity.dxf.insert = transform_xy(...)
    elif t in ("SOLID", "TRACE", "3DFACE"):
        # transform vtx0/1/2/3 (or first/second/third/fourth_corner)
```

Every entity type is handled. If a type doesn't match a branch, it's silently skipped (the entity stays at its current coords — usually fine for unusual types).

---

## Output

- **File**: `out/TP-104 OVERLAY_A.dxf` (~18 MB)
- **Modelspace**: 2,242 entities (1,953 STR INSERTs + 1,953 STR top-level entities + 289 MECH entities)
- **Wrappers**: 0
- **Editability**: HIGHEST
- **Color policy**: Original colors preserved (MECH: 17 unique; STR: source colors)

---

## When to pick Approach A

- ✅ You need to edit individual structural members after overlay
- ✅ You want a faithful overlay that doesn't rebrand colors
- ✅ You want a clean modelspace (no wrapper INSERT)
- ✅ The downstream tool works better with loose entities than with INSERTs

See [`STRATEGY-B.md`](./STRATEGY-B.md) and [`STRATEGY-C.md`](./STRATEGY-C.md) for the alternatives.

---

## Source code

- `ISGEC/A/scripts/overlay.py` — the implementation (~16 KB)
- `ISGEC/A/README.md` — the in-folder README that ships with this approach
- `ISGEC/A/run.sh` — one-shot driver (clean → fit → overlay)