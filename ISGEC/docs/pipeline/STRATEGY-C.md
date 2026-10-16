# Strategy C — 1-Block Overlay

> **Source:** `ISGEC/C/scripts/overlay.py` (8.7 KB), `ISGEC/C/scripts/overlay_helper.py` (7.3 KB), `ISGEC/C/README.md`
> **Output:** `ISGEC/C/out/TP-104 OVERLAY_C.dxf` (~18 MB)

Both MECH and STR are merged into a single `OVERLAY_DRAWING` block. **Modelspace has exactly one INSERT at the origin.**

---

## Color policy

**Forced 2-color** (same convention as Approach B):

- **Every MECH layer** is set to ACI color **1 (red)**
- **Every STR layer** is renamed with `_STR_` prefix and set to ACI color **5 (blue)**
- Per-entity color overrides on STR entities are reset to ByLayer (256) so they inherit the layer blue

> See [`STRATEGY-A.md`](./STRATEGY-A.md) if you want entities to keep their source colors instead. See [`STRATEGY-B.md`](./STRATEGY-B.md) for the 2-block equivalent.

---

## Editability

**LOW** — the entire overlay is one block. Move/scale it as a unit with one click. To edit individual entities, double-click into `OVERLAY_DRAWING` (which contains ~16,015 entities — slow).

---

## Structure

```
Modelspace:
  INSERT OVERLAY_DRAWING pos=(0, 0)  xscale=1
     │
     └─ OVERLAY_DRAWING block contains:
         ├─ 289 MECH entities (red, layer colors set to ACI 1)
         ├─ 1,953 INSERTs to GridLine-*, Part-*, Bolt-*, Connection-*
         ├─ 16,015 inner entities inside _STR_* blocks (blue)
         └─ _STR_* layers (color 5 = blue)
```

---

## Algorithm

C is the most code-intensive of the three because it combines A's per-entity transform with B's color forcing, then wraps everything in one block.

### 1. Import STR blocks

Same as A:
```python
imp = Importer(str_doc, out_doc)
for str_block in list(str_doc.blocks):
    if str_block.name.startswith("*"): continue
    target = STR_PREFIX + str_block.name  # _STR_GridLine-A
    new_name = imp.import_block(str_block.name, rename=False)
    if new_name != target:
        block_obj = out_doc.blocks.get(name=new_name)
        block_obj.rename(target)
    block_map[str_block.name] = new_name
```

### 2. Import STR top-level entities

```python
for entity in list(str_msp):
    imp.import_entity(entity, target_layout=out_msp)
imp.finalize()
```

### 3. Pre-scale + transform (reuses A's helpers)

C imports the helpers from `overlay_helper.py` (a sibling script in the same dir):

```python
sys.path.insert(0, str(HERE))  # same dir
from overlay_helper import prescale_entity, transform_entity_inplace
```

The pre-scale + transform loop is identical to A's (see [`STRATEGY-A.md`](./STRATEGY-A.md) §3 for the algorithm).

### 4. Rename STR layers + force ByLayer color

```python
str_layers_in_use = set()
for e in list(out_msp):
    if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
        layer = e.dxf.layer
        if not layer.startswith(STR_PREFIX):
            str_layers_in_use.add(layer)

for layer in str_layers_in_use:
    new_name = STR_PREFIX + layer
    out_doc.layers.add(name=new_name, color=STR_COLOR)  # 5 = blue (forced)

layer_renames = {old: STR_PREFIX + old for old in str_layers_in_use}
for e in list(out_msp):
    if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles:
        if e.dxf.layer in layer_renames:
            e.dxf.layer = layer_renames[e.dxf.layer]
        if e.dxf.hasattr("color") and e.dxf.color not in (0, 256, None):
            e.dxf.color = 256  # reset to ByLayer
```

### 5. Recolor MECH layers to red

```python
for layer in out_doc.layers:
    if not layer.dxf.name.startswith(STR_PREFIX):
        layer.dxf.color = MECH_COLOR  # 1 = red
```

### 6. Wrap everything into `OVERLAY_DRAWING` block

```python
overlay_block = out_doc.blocks.new(name="OVERLAY_DRAWING")
for e in list(out_msp):
    out_msp.unlink_entity(e)
    overlay_block.add_entity(e)
```

This is C's distinguishing step — every entity (MECH + STR + STR blocks) goes into one block.

### 7. Add 1 INSERT at origin

```python
out_msp.add_blockref("OVERLAY_DRAWING", insert=(0.0, 0.0, 0.0))
```

### 8. Save

```python
out_doc.saveas(str(OUT))   # → out/TP-104 OVERLAY_C.dxf
```

---

## Why `overlay_helper.py`?

The per-entity pre-scale + affine transform code is identical between A and C. To avoid duplication, C imports the helpers from `overlay_helper.py`:

```python
# In overlay_helper.py:
def prescale_entity(entity, sx, sy, ip_x=0.0, ip_y=0.0):
    """Bake INSERT position + xscale into each entity in a block."""
    ...

def transform_entity_inplace(entity, ax, ay, bx, by):
    """Apply the affine to an entity in place."""
    ...
```

```python
# In overlay.py:
sys.path.insert(0, str(HERE))  # same dir
from overlay_helper import prescale_entity, transform_entity_inplace
```

This is the only sharing between strategies — `A/scripts/overlay.py` and `C/scripts/overlay.py` each define their own helpers, but `C` uses the helper module instead of inlining the logic.

---

## Output

- **File**: `out/TP-104 OVERLAY_C.dxf` (~18 MB)
- **Modelspace**: 1 INSERT at origin
- **Wrappers**: 1 (`OVERLAY_DRAWING`)
- **Editability**: LOW (single grab, the whole overlay moves as one)
- **Color policy**: Forced red/blue

```
OVERLAY_DRAWING block: 289 MECH + ~16,015 STR entities (red + blue)
Modelspace: 1 INSERT at origin
```

---

## Why pick C over A or B

- You want a **single atomic** overlay object (move/scale/delete with one click)
- You don't need per-layer or per-entity toggling
- You're embedding the overlay into another assembly drawing as one unit

## Why NOT C

- To edit individual entities you must `double-click` into the massive `OVERLAY_DRAWING` block — slow with 16,015 entities inside
- No way to toggle just STR off without deleting the whole block
- No way to re-align later without re-running the pipeline (the `STR_DRAWING` exposure of B is lost)

---

## Source code

- `ISGEC/C/scripts/overlay.py` — the implementation (8.7 KB)
- `ISGEC/C/scripts/overlay_helper.py` — the shared helpers (7.3 KB)
- `ISGEC/C/README.md` — the in-folder README
- `ISGEC/C/run.sh` — one-shot driver

---

## Reference

- [`STRATEGY-A.md`](./STRATEGY-A.md) — per-entity (highest editability)
- [`STRATEGY-B.md`](./STRATEGY-B.md) — 2-block (toggleable)