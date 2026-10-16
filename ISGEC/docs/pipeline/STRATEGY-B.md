# Strategy B — 2-Block Overlay

> **Source:** `ISGEC/B/scripts/overlay.py` (6.8 KB), `ISGEC/B/README.md`
> **Output:** `ISGEC/B/out/TP-104 OVERLAY_B.dxf` (~18 MB)

Each drawing is wrapped in its own block. **Modelspace has exactly 2 INSERTs.** The gridline-derived affine lives on the `STR_DRAWING` INSERT's `(insert, xscale, yscale)` — no per-entity transform needed.

---

## Color policy

**Forced 2-color** for at-a-glance readability:

- **Every MECH layer** (non-prefixed) is set to ACI color **1 (red)**
- **Every STR layer** is renamed with `_BLUE_` prefix and set to ACI color **5 (blue)**
- Per-entity color overrides on STR entities are reset to ByLayer (256) so they inherit the layer blue

This is the standard convention for engineering overlay drawings: **red for mechanical, blue for structural**.

> See [`STRATEGY-A.md`](./STRATEGY-A.md) if you want entities to keep their source colors instead. See [`STRATEGY-C.md`](./STRATEGY-C.md) for the 1-block equivalent.

---

## Editability

**MEDIUM** — click `STR_DRAWING` to grab the whole STR layer; double-click into `STR_DRAWING` to edit individual entities.

This is the "best of both worlds" approach — you can toggle STR with one click (delete the `STR_DRAWING` INSERT) AND drill into individual members when needed.

---

## Structure

```
Modelspace:
  INSERT MECH_DRAWING  pos=(0, 0)             xscale=1
  INSERT STR_DRAWING   pos=(208379.86, -179584.52)  xscale=1.0  yscale=1.0
     │
     └─ STR_DRAWING block contains:
         ├─ 1,953 INSERTs to GridLine-*, Part-*, Bolt-*, Connection-*
         └─ _BLUE_* layers (color 5 = blue)
```

---

## Algorithm

### 1. Wrap MECH into `MECH_DRAWING` block

```python
mech_block = out_doc.blocks.new(name="MECH_DRAWING")
for e in list(out_msp):
    out_msp.unlink_entity(e)
    mech_block.add_entity(e)
```

MECH entities stay at their original MECH coords — no transform applied to MECH geometry.

### 2. Import STR at original coords

```python
imp = Importer(str_doc, out_doc)
for str_block in list(str_doc.blocks):
    if str_block.name.startswith("*"): continue
    new_name = imp.import_block(str_block.name, rename=False)
    block_map[str_block.name] = new_name

for entity in list(str_msp):
    imp.import_entity(entity, target_layout=out_msp)
imp.finalize()
```

### 3. Wrap imported STR into `STR_DRAWING` block

```python
str_block_layout = out_doc.blocks.new(name="STR_DRAWING")
str_entities = [e for e in list(out_msp)
                if e.dxf.hasattr("handle") and e.dxf.handle in imported_handles]
for e in str_entities:
    out_msp.unlink_entity(e)
    str_block_layout.add_entity(e)
```

**The affine is NOT applied to STR entities here.** STR geometry stays at its original STR coords. The transform is baked into the `STR_DRAWING` INSERT's `xscale` + `insert` instead.

### 4. Recolor MECH layers → red

```python
for layer in out_doc.layers:
    layer.dxf.color = MECH_COLOR  # 1 = red

# Reset per-entity color overrides to ByLayer
for entity in list(mech_block):
    if entity.dxf.hasattr("color") and entity.dxf.color in (0, 256, None):
        entity.dxf.color = 256
```

### 5. STR layers → blue with `_BLUE_` prefix

```python
blue_layers = set()
for e in list(str_block_layout):
    if e.dxf.hasattr("layer"):
        blue_layers.add(e.dxf.layer)

for layer in blue_layers:
    if layer.startswith(BLUE_PREFIX): continue
    new_name = BLUE_PREFIX + layer
    out_doc.layers.add(name=new_name, color=STR_COLOR)  # 5 = blue
```

### 6. Add 2 INSERTs at modelspace

```python
out_msp.add_blockref("MECH_DRAWING", insert=(0.0, 0.0, 0.0))
out_msp.add_blockref("STR_DRAWING",
                     insert=(tx, ty, 0.0),
                     dxfattribs={"xscale": sx, "yscale": sy})
```

This is where the affine lives:
- `tx, ty` = the translation vector
- `sx, sy` = the scale factors (1.0 in our case)

When the CAD viewer renders this, it applies the INSERT's `(pos + scale)` to every entity inside the block — effectively overlaying STR onto MECH.

### 7. Save

```python
out_doc.saveas(str(OUT))   # → out/TP-104 OVERLAY_B.dxf
```

---

## Output

- **File**: `out/TP-104 OVERLAY_B.dxf` (~18 MB)
- **Modelspace**: 2 INSERTs only
- **Editability**: MEDIUM
- **Color policy**: Forced red/blue

```
MECH_DRAWING block: 289 MECH entities (red)
STR_DRAWING  block: ~1,953 STR entities (blue)
Inner STR blocks:   1,953 (blue)
Modelspace: 2 INSERTs
  MECH_DRAWING  pos=(0, 0)         xscale=1
  STR_DRAWING   pos=(208379.86, -179584.52)  xscale=1  yscale=1
```

---

## Why pick B over A

- You want **forced red/blue** for high-contrast overlay
- You want to **toggle STR on/off** with one click (delete the `STR_DRAWING` INSERT)
- You might re-align the overlay **later** by moving the `STR_DRAWING` INSERT position without re-running the script
- You want to keep MECH and STR as separate logical units

## Why pick B over C

- You want to *individually* edit STR members (B lets you double-click into `STR_DRAWING`; in C you'd double-click into the monolithic `OVERLAY_DRAWING`)
- You want the MECH and STR blocks to be **independently movable** (B exposes both as top-level INSERTs; C merges them into one block)

---

## Source code

- `ISGEC/B/scripts/overlay.py` — the implementation (6.8 KB)
- `ISGEC/B/README.md` — the in-folder README that ships with this approach
- `ISGEC/B/run.sh` — one-shot driver

---

## Reference

- [`STRATEGY-A.md`](./STRATEGY-A.md) — per-entity (highest editability)
- [`STRATEGY-C.md`](./STRATEGY-C.md) — 1-block (single atomic unit)