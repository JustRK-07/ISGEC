"""DXF entity extraction + DWG metadata extraction — Python port of lib/parse.js.

Targets BACKEND_ARCHITECTURE §2 (Layer 1 — DWG → DXF & Entity Extraction).

The current Node parser in lib/parse.js is a hand-rolled tolerant DXF reader. We
port the desync-recovery logic verbatim (lines 88-110 of the JS), then optionally
swap in ezdxf for cleaner upstream parsing once production traffic validates.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services import dwg_convert

logger = logging.getLogger(__name__)

# AutoCAD $INSUNITS → multiplier to convert to millimetres.
# 0 = unitless, 1 = inches, 2 = feet, 4 = mm, 5 = cm, 6 = metres
INSUNITS_TO_MM: dict[int, float] = {
    0: 1,
    1: 25.4,
    2: 304.8,
    4: 1,
    5: 10,
    6: 1000,
}

# DXF entity types that carry real geometry (lines, text, polylines, etc.).
# Anything outside this set (DICTIONARY, FIELD, XRECORD, LAYOUT, ...) lives in
# the OBJECTS/TABLES section and has no spatial meaning — we skip them so the
# canvas only sees renderable geometry.
_GEOMETRY_ENTITY_TYPES: frozenset[str] = frozenset({
    "LINE",
    "LWPOLYLINE",
    "POLYLINE",
    "CIRCLE",
    "ARC",
    "ELLIPSE",
    "SPLINE",
    "TEXT",
    "MTEXT",
    "INSERT",
    "ATTRIB",
    "ATTDEF",
    "HATCH",
    "SOLID",
    "3DFACE",
    "DIMENSION",
    "LEADER",
    "POINT",
})

# DWG version tags — every real DWG starts with one of these
DWG_VERSIONS: dict[str, str] = {
    "AC1012": "R13",
    "AC1013": "R13c",
    "AC1014": "R14",
    "AC1015": "R2000",
    "AC1018": "R2004",
    "AC1021": "R2007",
    "AC1024": "R2010",
    "AC1027": "R2013",
    "AC1032": "R2018",
}

VALID_GROUP_MAX = 1071


def units_to_mm(ins_units: int | None) -> float:
    return INSUNITS_TO_MM.get(ins_units or 0, 1)


@dataclass
class ParsedDrawing:
    ok: bool
    kind: str
    entity_count: int = 0
    entities: list[dict] = field(default_factory=list)
    layers: list[dict] = field(default_factory=list)
    text_labels: list[dict] = field(default_factory=list)
    header: dict = field(default_factory=dict)
    parse_meta: dict = field(default_factory=dict)
    parse_status: str = "ok"
    error: str | None = None


def parse_file(
    file_path: str | Path,
    original_name: str | None = None,
    max_primitives: int = 50_000,
) -> ParsedDrawing:
    """Top-level dispatcher — picks the parser based on extension.

    ``max_primitives`` is the backstop on INSERT expansion in Revit-style 3D
    exports where every primitive lives inside a block. If the cap is hit
    the parser emits ``parse_meta.truncatedInserts = True`` and stops
    expanding.
    """
    name = original_name or str(file_path)
    ext = Path(name).suffix.lower()
    data = Path(file_path).read_bytes()

    if ext == ".dxf":
        return _parse_dxf(data, name, max_primitives=max_primitives)
    if ext == ".dwg":
        return _parse_dwg(data, name, str(file_path), max_primitives=max_primitives)
    if ext == ".ifc":
        return _parse_ifc(data, name)
    if ext == ".pdf":
        return _parse_pdf_stub(name)
    return ParsedDrawing(ok=False, kind="unknown", error=f"Unsupported extension {ext}")


# --------------------------------------------------------------------------- #
# DXF — tolerant parser (port of parseDxf from lib/parse.js)
# --------------------------------------------------------------------------- #


def _parse_dxf(buf: bytes, name: str, max_primitives: int = 50_000) -> ParsedDrawing:
    text = buf.decode("utf-8", errors="replace")
    lines = text.splitlines()

    # Pass 0 — recover from desync (libredwg emits unescaped newlines inside MTEXT)
    tokens: list[tuple[int, str]] = []
    i = 0
    while i < len(lines) - 1:
        try:
            code = int(lines[i])
        except ValueError:
            # desync — treat this line as a continuation of the previous value
            if tokens:
                last_code, last_value = tokens[-1]
                tokens[-1] = (last_code, last_value + "\n" + lines[i])
            i += 1
            continue
        if code < 0 or code > VALID_GROUP_MAX:
            if tokens:
                last_code, last_value = tokens[-1]
                tokens[-1] = (last_code, last_value + "\n" + lines[i])
            i += 1
            continue
        tokens.append((code, lines[i + 1] if i + 1 < len(lines) else ""))
        i += 2

    # Pass 0b — find $INSUNITS in the HEADER section
    ins_units: int | None = None
    in_header = False
    for k, (code, value) in enumerate(tokens):
        if code == 0 and value == "SECTION" and k + 1 < len(tokens) and tokens[k + 1][0] == 2:
            in_header = tokens[k + 1][1] == "HEADER"
            continue
        if code == 0 and value in ("ENDSEC", "EOF"):
            in_header = False
        if in_header and code == 9 and value == "$INSUNITS":
            if k + 1 < len(tokens) and tokens[k + 1][0] == 70:
                ins_units = int(tokens[k + 1][1])

    # Pass 1 — walk BLOCKS + ENTITIES sections.
    # Block definitions are captured into ``blocks`` (so Pass 2 can expand
    # INSERTs in the modelspace), and modelspace entities land in ``entities``.
    entities: list[dict] = []
    blocks: dict[str, _BlockDef] = {}
    i = 0
    in_entities = False
    current_section: str | None = None  # 'BLOCKS' | 'ENTITIES' | None
    block_depth = 0
    in_model_block = False
    last_entity_start = -1
    current_block: _BlockDef | None = None
    while i < len(tokens):
        code, value = tokens[i]
        if code == 0 and value == "EOF":
            break
        if code == 2 and value in ("ENTITIES", "BLOCKS"):
            current_section = value
            in_entities = True
            i += 1
            continue
        if in_entities and code == 0 and value == "ENDSEC":
            # End of the current section (BLOCKS or ENTITIES). Reset to None
            # so subsequent sections (e.g. ENTITIES after BLOCKS) are picked up.
            current_section = None
            current_block = None
            block_depth = 0
            in_model_block = False
            i += 1
            continue
        if in_entities and code == 0 and value == "BLOCK":
            # peek for the block name
            block_name = ""
            for j in range(i + 1, min(i + 8, len(tokens))):
                if tokens[j][0] == 0:
                    break
                if tokens[j][0] == 2:
                    block_name = tokens[j][1]
                    break
            if block_name.startswith("*"):
                in_model_block = True
                current_block = None  # do not capture anonymous model/paper blocks
            else:
                block_depth += 1
                current_block = _BlockDef(name=block_name, base_point={"x": 0.0, "y": 0.0, "z": 0.0}, entities=[])
                # Capture the block's base point (codes 10/20/30 follow the
                # BLOCK code-0 row before any entity inside).
                for j in range(i + 1, min(i + 20, len(tokens))):
                    if tokens[j][0] == 0:
                        break
                    if tokens[j][0] == 10:
                        try:
                            current_block.base_point["x"] = float(tokens[j][1])
                        except ValueError:
                            pass
                    elif tokens[j][0] == 20:
                        try:
                            current_block.base_point["y"] = float(tokens[j][1])
                        except ValueError:
                            pass
                    elif tokens[j][0] == 30:
                        try:
                            current_block.base_point["z"] = float(tokens[j][1])
                        except ValueError:
                            pass
                blocks[block_name] = current_block
            i += 1
            continue
        if in_entities and code == 0 and value == "ENDBLK":
            if block_depth > 0:
                block_depth -= 1
                current_block = None
            elif in_model_block:
                in_model_block = False
                current_block = None
            i += 1
            continue
        if in_entities and code == 0:
            # Only walk the geometry entity types. Other DXF object types
            # (DICTIONARY, FIELD, XRECORD, ...) live in OBJECTS / TABLES
            # sections and have no real geometry; reading them pollutes the
            # entity list and confuses downstream consumers.
            if value in _GEOMETRY_ENTITY_TYPES:
                if i > last_entity_start:
                    result = _parse_entity(tokens, i)
                    if result is not None:
                        rec, next_i = result
                        if current_section == "BLOCKS" and current_block is not None:
                            # Tag with the owning block so the classifier can use
                            # block-name rules (e.g. Part-* → beam).
                            rec["blockName"] = current_block.name
                            current_block.entities.append(rec)
                        else:
                            entities.append(rec)
                        last_entity_start = i
                        i = next_i
                        continue
            elif value not in ("BLOCK", "ENDBLK", "ENDSEC", "EOF", "INSERT"):
                # Skip non-geometry rows within ENTITIES (e.g. DICTIONARY).
                # Move past this entity by consuming tokens until the next
                # code-0 row so we don't misattribute child codes.
                j = i + 1
                while j < len(tokens) and tokens[j][0] != 0:
                    j += 1
                last_entity_start = j - 1
                i = j
                continue
        i += 1

    # Pass 2 — expand INSERTs in modelspace using captured block definitions.
    # This is what turns Revit 3D exports (where every primitive lives inside a
    # block) into renderable 2D geometry. No recursion into INSERT-inside-BLOCK
    # (avoids exponential blow-up on pathological drawings).
    entities, truncated = _expand_inserts(entities, blocks, max_primitives=max_primitives)

    # Build summary
    layer_counts: dict[str, int] = {}
    labels: list[dict] = []
    for ent in entities:
        layer_name = ent.get("layer") or "0"
        layer_counts[layer_name] = layer_counts.get(layer_name, 0) + 1
        if ent.get("type") in ("TEXT", "MTEXT") and ent.get("text"):
            labels.append({"layer": layer_name, "text": str(ent["text"])[:200]})

    layers = sorted(
        ({"name": name, "count": count} for name, count in layer_counts.items()),
        key=lambda d: -d["count"],
    )[:60]

    parse_meta: dict = {
        "kind": "dxf",
        "parser": "custom",
        "entityCount": len(entities),
        "layers": layers,
        "headerUnits": ins_units,
        "textLabels": labels[:200],
    }
    if truncated:
        parse_meta["truncatedInserts"] = True
    if blocks:
        parse_meta["blockDefs"] = len(blocks)

    return ParsedDrawing(
        ok=True,
        kind="dxf",
        entity_count=len(entities),
        entities=entities,
        layers=layers,
        text_labels=labels[:200],
        header={"$INSUNITS": ins_units},
        parse_meta=parse_meta,
    )


def _parse_entity(tokens: list[tuple[int, str]], i: int) -> tuple[dict, int] | None:
    """Parse one entity starting at index `i` (where tokens[i] is the code-0 row)."""
    entity_type = (tokens[i][1] or "").upper()
    if not entity_type or entity_type in ("ENDBLK", "ENDSEC", "EOF"):
        return None

    rec: dict[str, Any] = {"type": entity_type}
    j = i + 1
    is_poly = entity_type in ("LWPOLYLINE", "POLYLINE")
    if is_poly:
        rec["vertices"] = []
    text_buf: list[str] = []
    pos = {"x": 0.0, "y": 0.0, "z": 0.0}
    has_pos = False
    end_pt = {"x": 0.0, "y": 0.0}
    has_end = False
    last_vert_set = False

    while j < len(tokens):
        code, value = tokens[j]
        if code == 0:
            break
        if code == 8:
            rec["layer"] = value
        elif code == 2 and entity_type == "INSERT":
            # Block name for INSERT entities (code 2 only after the type row).
            rec["blockName"] = value
        elif code == 10:
            x = float(value)
            if is_poly and rec["vertices"] and not last_vert_set:
                rec["vertices"].append({"x": x, "y": 0.0})
                last_vert_set = True
            else:
                pos["x"] = x
                has_pos = True
                if is_poly and not rec["vertices"]:
                    rec["vertices"].append({"x": x, "y": 0.0})
                if entity_type == "INSERT":
                    rec["insertPoint"] = {"x": x, "y": pos["y"], "z": pos["z"]}
                last_vert_set = False
        elif code == 20:
            y = float(value)
            if is_poly and rec["vertices"]:
                rec["vertices"][-1]["y"] = y
            pos["y"] = y
            if entity_type == "INSERT" and "insertPoint" in rec:
                rec["insertPoint"]["y"] = y
        elif code == 30:
            pos["z"] = float(value)
            if entity_type == "INSERT" and "insertPoint" in rec:
                rec["insertPoint"]["z"] = float(value)
        elif code == 11:
            end_pt["x"] = float(value)
            has_end = True
        elif code == 21:
            end_pt["y"] = float(value)
            has_end = True
        elif code == 40:
            if entity_type in ("CIRCLE", "ARC"):
                rec["radius"] = float(value)
            else:
                rec["textHeight"] = float(value)
        elif code in (1, 3):
            text_buf.append(value)
        elif code == 50:
            if entity_type == "ARC":
                rec["startAngle"] = float(value)
            else:
                rec["rotation"] = float(value)
        elif code == 51 and entity_type == "ARC":
            rec["endAngle"] = float(value)
        elif code == 41:
            # INSERT scale X (code 41); also used for other entities' scale.
            if entity_type == "INSERT":
                rec["scaleX"] = float(value) if value else 1.0
            else:
                rec["scale"] = float(value)
        elif code == 42:
            # INSERT scale Y.
            if entity_type == "INSERT":
                rec["scaleY"] = float(value) if value else 1.0
        elif code == 70:
            rec["flags"] = int(value)
        elif code == 90:
            rec["vertexCount"] = int(value)
        elif code == 1000 or code == 1001:
            text_buf.append(value)
        j += 1

    if entity_type in ("TEXT", "MTEXT"):
        rec["text"] = "\n".join(text_buf).strip()

    if has_pos:
        rec["position"] = {"x": pos["x"], "y": pos["y"]}
        if entity_type == "LINE":
            rec["startPoint"] = {"x": pos["x"], "y": pos["y"]}
    if has_end:
        rec["endPoint"] = {"x": end_pt["x"], "y": end_pt["y"]}

    return rec, j


# --------------------------------------------------------------------------- #
# DWG — magic-byte check + best-effort ASCII sniff + ezdxf/dwg2dxf wrapper
# --------------------------------------------------------------------------- #


def _parse_dwg(buf: bytes, name: str, file_path: str, max_primitives: int = 50_000) -> ParsedDrawing:
    sig = buf[:6].decode("ascii", errors="replace")
    version = DWG_VERSIONS.get(sig)
    if not version:
        return ParsedDrawing(
            ok=False,
            kind="dwg",
            parse_status="failed",
            error=f'Unrecognized DWG magic bytes "{sig}". Expected AC1xxx version tag.',
            parse_meta={"magicBytes": sig, "recognized": False},
        )

    # Best-effort ASCII extraction for layer names + labels (used as a hint even
    # when the full ezdxf conversion succeeds).
    ascii_text = buf.decode("latin-1", errors="replace")
    layer_re = re.compile(r"[A-Z][A-Z0-9_\-]{2,30}")
    layer_candidates = list(dict.fromkeys(layer_re.findall(ascii_text)))[:40]
    elev_re = re.compile(r"[EL\+\-LVL\.]{0,4}[\s]?[\+\-]?\d{1,2}\.\d{2,3}\s?m", re.I)
    elevations = list(dict.fromkeys(s.strip() for s in elev_re.findall(ascii_text)))[:20]
    pipe_re = re.compile(r"\b(?:DN|NPS|Ø)\s?\d{2,4}\b")
    pipes = list(dict.fromkeys(pipe_re.findall(ascii_text)))[:20]

    # Attempt real conversion via system libredwg binary.
    full_parse = _convert_dwg_with_libredwg(file_path, name, max_primitives=max_primitives)
    if full_parse is not None and full_parse.ok:
        full_parse.parse_meta = {
            **full_parse.parse_meta,
            "kind": "dwg",
            "parseStatus": "ok",
            "dwgVersion": version,
            "magicBytes": sig,
            "layerCandidates": layer_candidates,
            "elevations": elevations,
            "pipes": pipes,
            "conversion": "libredwg",
        }
        return full_parse

    note = (
        "libredwg dwg2dxf not available"
        if not dwg_convert.libredwg_available()
        else "libredwg conversion failed; sent metadata to LLM."
    )
    return ParsedDrawing(
        ok=True,
        kind="dwg",
        parse_status="partial",
        parse_meta={
            "magicBytes": sig,
            "dwgVersion": version,
            "sizeBytes": len(buf),
            "layerCandidates": layer_candidates,
            "elevations": elevations,
            "pipes": pipes,
            "note": note,
        },
        header={"dwgVersion": version},
    )


def _convert_dwg_with_libredwg(
    file_path: str, name: str, max_primitives: int = 50_000
) -> ParsedDrawing | None:
    """Convert a DWG file to DXF using the system libredwg binary, then parse.

    The produced DXF is written to a tempdir and unlinked after parsing. The
    returned ``ParsedDrawing`` is identical in shape to a native DXF parse so
    downstream code (analyze, rules, canvas) is agnostic to the source format.
    """
    converted = dwg_convert.convert_dwg_to_dxf(file_path, timeout_sec=60)
    if converted is None:
        return None
    try:
        dxf_bytes = converted.read_bytes()
    except OSError:
        return None
    finally:
        try:
            converted.unlink(missing_ok=True)
        except OSError:
            pass
        # Best-effort cleanup of the surrounding tempdir if it was empty.
        parent = converted.parent
        try:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
    try:
        return _parse_dxf(dxf_bytes, name, max_primitives=max_primitives)
    except Exception as exc:  # noqa: BLE001
        logger.warning("DXF parse after libredwg conversion failed: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# IFC / PDF stubs
# --------------------------------------------------------------------------- #


def _parse_ifc(buf: bytes, name: str) -> ParsedDrawing:
    text = buf.decode("utf-8", errors="replace")
    ifc_classes = list(dict.fromkeys(re.findall(r"\bIFC[A-Z][A-Z0-9]+", text)))[:20]
    return ParsedDrawing(
        ok=True,
        kind="ifc",
        parse_status="partial",
        parse_meta={"sizeBytes": len(buf), "ifcClasses": ifc_classes},
    )


def _parse_pdf_stub(name: str) -> ParsedDrawing:
    return ParsedDrawing(
        ok=False,
        kind="pdf",
        parse_status="skipped",
        parse_meta={"note": "PDF reference drawing — not parsed. Falls through to vision path."},
    )


# --------------------------------------------------------------------------- #
# DXF → normalized entity rows (port of dxfToEntities from lib/parse.js)
# --------------------------------------------------------------------------- #


@dataclass
class _BlockDef:
    """A DXF BLOCK definition captured during Pass 1 of _parse_dxf.

    ``entities`` is the list of primitives (LINE, LWPOLYLINE, ...) that make
    up the block body. ``base_point`` is the block's local origin (codes 10/20/30
    of the BLOCK row) — INSERTs transform around this point, not (0, 0).
    """

    name: str
    base_point: dict[str, float]
    entities: list[dict] = field(default_factory=list)


def _transform_point(
    p: dict[str, float] | None,
    insert_pt: dict[str, float],
    scale_x: float,
    scale_y: float,
    rotation_deg: float,
    base: dict[str, float],
) -> dict[str, float] | None:
    """Apply 2D affine OCS → world: scale, rotate, translate.

    ``base`` is the block's local origin (subtracted before rotation so the
    block rotates about its base point, then added back). INSERTs in 2D DXF
    can carry a rotation in degrees (code 50); we honour it.
    """
    if p is None:
        return None
    x0 = (p.get("x") or 0.0) - (base.get("x") or 0.0)
    y0 = (p.get("y") or 0.0) - (base.get("y") or 0.0)
    sx = x0 * scale_x
    sy = y0 * scale_y
    if rotation_deg:
        import math

        theta = math.radians(rotation_deg)
        cs = math.cos(theta)
        sn = math.sin(theta)
        rx = sx * cs - sy * sn
        ry = sx * sn + sy * cs
    else:
        rx, ry = sx, sy
    return {
        "x": (insert_pt.get("x") or 0.0) + rx,
        "y": (insert_pt.get("y") or 0.0) + ry,
    }


def _transformed_primitive(
    prim: dict,
    insert: dict,
    base: dict[str, float],
) -> dict:
    """Apply an INSERT's transformation to one of the block's primitives.

    Each primitive is a dict from Pass 1; we transform any (x, y) / (x, y, z)
    coordinate it carries (position, startPoint, endPoint, center, vertices).
    The block entity keeps its own layer if set, else inherits the INSERT's.
    The block name is added to the ``meta`` so the classifier can apply
    block-name rules.
    """
    sx = float(insert.get("scaleX") or 1.0)
    sy = float(insert.get("scaleY") or 1.0)
    rot = float(insert.get("rotation") or 0.0)
    ip = insert.get("insertPoint") or {"x": 0.0, "y": 0.0}
    insert_layer = insert.get("layer")

    out = dict(prim)  # shallow copy

    def xform(d: dict | None) -> dict | None:
        return _transform_point(d, ip, sx, sy, rot, base)

    if "position" in out and isinstance(out["position"], dict):
        out["position"] = xform(out["position"])
    if "startPoint" in out and isinstance(out["startPoint"], dict):
        out["startPoint"] = xform(out["startPoint"])
    if "endPoint" in out and isinstance(out["endPoint"], dict):
        out["endPoint"] = xform(out["endPoint"])
    if "center" in out and isinstance(out["center"], dict):
        out["center"] = xform(out["center"])
    if "vertices" in out and isinstance(out["vertices"], list):
        out["vertices"] = [xform(v) if isinstance(v, dict) else v for v in out["vertices"]]
    if "startAngle" in out:
        out["startAngle"] = float(out["startAngle"]) + rot
    if "endAngle" in out:
        out["endAngle"] = float(out["endAngle"]) + rot

    # Layer inheritance: block primitive keeps its own layer; otherwise fall
    # back to the INSERT's layer (matches AutoCAD's effective layer).
    if not out.get("layer") and insert_layer:
        out["layer"] = insert_layer

    # Tag the resulting primitive with the block it came from so the
    # classifier can apply BLOCK_KIND_RULES.
    block_name = out.get("blockName")
    if block_name:
        out["blockName"] = block_name
    return out


def _expand_inserts(
    entities: list[dict],
    blocks: dict[str, _BlockDef],
    max_primitives: int = 50_000,
) -> tuple[list[dict], bool]:
    """Replace each INSERT in ``entities`` with the transformed primitives
    from its block definition. Non-INSERT entities pass through unchanged.

    Returns ``(out, truncated)`` where ``truncated`` is True if the expansion
    hit ``max_primitives`` before all INSERTs were expanded.
    """
    if not blocks:
        return entities, False
    out: list[dict] = []
    truncated = False
    for ent in entities:
        if ent.get("type") != "INSERT":
            out.append(ent)
            continue
        block_name = ent.get("blockName")
        if not block_name:
            out.append(ent)
            continue
        block = blocks.get(block_name)
        if block is None:
            # Unknown block — pass the INSERT through; the canvas will render
            # it as a small marker.
            out.append(ent)
            continue
        for prim in block.entities:
            if len(out) >= max_primitives:
                truncated = True
                break
            out.append(_transformed_primitive(prim, ent, block.base_point))
        if truncated:
            break
    return out, truncated





# Layer-name → kind rules. Order matters: first match wins.
# Each tuple is (needle, kind) where ``needle`` is a case-insensitive substring
# matched against the layer name with spaces stripped. The list covers the layer
# vocabulary observed in real DWG exports (MECH GA.dwg: PANTHOM/HIDDDEN typos,
# MAIN OBJECT, BOX, AM_*, BELT, etc.) plus the original layer set the parser
# supported. Adding a new rule at the END of the list keeps existing behaviour.
LAYER_KIND_RULES: list[tuple[str, str]] = [
    ("GRID", "grid-bubble"),
    ("OPEN", "opening"),
    ("PENETR", "opening"),
    ("SLEEVE", "opening"),
    ("BEAM", "beam"),
    ("GIRDER", "beam"),
    ("BM", "beam"),
    ("COL", "column"),
    ("PILLAR", "column"),
    ("PIPE", "pipe"),
    ("DUCT", "duct"),
    ("EQUIP", "equipment"),
    ("MECH", "equipment"),
    ("MAIN OBJECT", "equipment"),
    ("PANTHOM", "phantom"),   # observed typo in MECH GA.dwg
    ("PHANTOM", "phantom"),
    ("HIDDEN", "hidden"),
    ("HIDDDEN", "hidden"),    # observed typo in MECH GA.dwg
    ("CENTRE", "centerline"),
    ("CENTER", "centerline"),
    ("CEN", "centerline"),
    ("AM_", "annotation"),
    ("BELT", "annotation"),
    ("SHEETING", "annotation"),
    ("HANDRAIL", "annotation"),
    ("CHUTE", "annotation"),
    ("REV", "annotation"),
    ("BOX", "annotation"),
    ("DIM", "dimension"),
    ("TXT-50", "annotation"),
    ("TXT-", "annotation"),
    ("TEXT_", "annotation"),         # TEXT_25, TEXT_2.5, TEXT_35 — large note text
    ("ALL BOUGHT", "equipment"),     # third-party scope — treat like MAIN OBJECT
    ("OBJECT", "equipment"),         # observed in MECH GA.dwg
    ("STRUC", "brace"),              # STRUC-* layers carry bracing detail
    ("CENETR", "centerline"),  # observed typo
]

# Block-name → kind rules. Block names are matched case-insensitively as a
# prefix. Used for STR drawings exported from Revit where layer information is
# lost (all entities sit on layer 0) but each INSERT points to a small block
# whose name encodes the element category.
BLOCK_KIND_RULES: list[tuple[str, str]] = [
    ("Part-", "beam"),
    ("Bolt-", "brace"),
    ("Connection-", "brace"),
    ("GridLine-", "gridline"),
    ("Column-", "column"),
    ("Beam-", "beam"),
]

# Layers whose entries should be dropped from the entity table entirely.
# They're how AutoCAD stores construction geometry -- no visual meaning.
SKIP_LAYERS: frozenset[str] = frozenset({
    "DEFPOINTS",   # AutoCAD internal construction points
})

# Entity types that exist in modelspace as block-attribute scaffolding (no
# visual contribution).
SKIP_TYPES: frozenset[str] = frozenset({
    "ATTRIB",
    "ATTDEF",
})


def classify_dxf_entity(entity: dict) -> str:
    layer = (entity.get("layer") or "").upper()
    t = (entity.get("type") or "").upper()
    if t in ("TEXT", "MTEXT"):
        return "text"
    # Layer-based classification runs BEFORE INSERT/BLOCK so that
    # `INSERT` entities on a `EQUIP` layer still resolve to "equipment"
    # (preserved from the original parser behaviour).
    layer_compact = layer.replace(" ", "")
    for needle, kind in LAYER_KIND_RULES:
        # The rule table stores needles with their original spacing; we match
        # against both the raw layer (so "MAIN OBJECT" hits the EQUIP rule
        # with the space) and the compact form (so "PANTHOM" / "HIDDDEN"
        # also work regardless of how the source wrote the layer).
        if needle in layer or needle in layer_compact:
            return kind
    # Block-name classification (Revit-exported drawings).
    block_name = (entity.get("blockName") or "").lower()
    if block_name:
        for prefix, kind in BLOCK_KIND_RULES:
            if block_name.startswith(prefix.lower()):
                return kind
        if block_name.startswith("unknown-"):
            return "unknown"
    if t == "INSERT":
        return "block"
    if t in ("BLOCK", "ENDBLK"):
        return "block"
    if t in ("LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC"):
        return "line"
    return "unknown"


def _entity_centroid(entity: dict) -> dict | None:
    if entity.get("position"):
        p = entity["position"]
        return {"x": p["x"], "y": p["y"]}
    if entity.get("center"):
        c = entity["center"]
        return {"x": c["x"], "y": c["y"]}
    verts = entity.get("vertices")
    if verts:
        sx = sum(v["x"] for v in verts) / len(verts)
        sy = sum(v["y"] for v in verts) / len(verts)
        return {"x": sx, "y": sy}
    if isinstance(entity.get("startPoint"), dict) and isinstance(entity.get("endPoint"), dict):
        s, e = entity["startPoint"], entity["endPoint"]
        return {"x": (s["x"] + e["x"]) / 2, "y": (s["y"] + e["y"]) / 2}
    if entity.get("startPoint"):
        s = entity["startPoint"]
        return {"x": s["x"], "y": s["y"]}
    return None


def _entity_dims(entity: dict) -> dict:
    verts = entity.get("vertices")
    if verts and len(verts) >= 2:
        xs = [v["x"] for v in verts]
        ys = [v["y"] for v in verts]
        return {"w": max(xs) - min(xs), "h": max(ys) - min(ys)}
    if entity.get("radius"):
        r = entity["radius"]
        return {"w": r * 2, "h": r * 2}
    return {"w": None, "h": None}


def _detect_sheet(layer: str) -> str:
    """Find a 4-digit sheet code in the layer name. Falls back to ``"0001"``
    so single-sheet DWGs (the common case) all end up on the first sheet
    and the canvas's sheet filter doesn't strand them on a phantom
    ``default`` sheet that the UI can't reach.
    """
    m = re.search(r"(\d{4})", layer or "")
    return m.group(1) if m else "0001"


def _conv_pt(point: dict | None, factor: float) -> dict | None:
    if point is None:
        return None
    return {"x": point["x"] * factor, "y": point["y"] * factor}


def dxf_to_entities(
    parsed: ParsedDrawing,
    discipline: str,
    project_id: str,
    uuid_factory,
    label_radius_mm: float = 800.0,
) -> list[dict]:
    """Walk the parsed DXF into normalized entity rows for the rule engine.

    Mirrors `dxfToEntities` from lib/parse.js — Pass 1 text labels, Pass 2
    nearest-label attach, with the radius configured per project.
    """
    if not parsed.ok or not parsed.entities:
        return []

    factor = units_to_mm(parsed.header.get("$INSUNITS") or 4)

    def conv(n: float | None) -> float | None:
        return None if n is None else n * factor

    def conv_pt(p: dict | None) -> dict | None:
        return _conv_pt(p, factor)

    out: list[dict] = []
    labels: list[dict] = []
    ins_units = parsed.header.get("$INSUNITS")

    for entity in parsed.entities:
        # Drop construction-data entities that have no visual contribution:
        #   * SKIP_LAYERS: how AutoCAD stores internal anchor points
        #   * SKIP_TYPES: ATTRIB/ATTDEF scaffolding that follows blocks
        if (entity.get("layer") or "").upper() in SKIP_LAYERS:
            continue
        if (entity.get("type") or "").upper() in SKIP_TYPES:
            continue
        kind = classify_dxf_entity(entity)
        xy = _entity_centroid(entity)
        if xy is None:
            continue
        xy_mm = {"x": xy["x"] * factor, "y": xy["y"] * factor}
        dims = _entity_dims(entity)
        w_mm = conv(dims.get("w"))
        h_mm = conv(dims.get("h"))
        is_text = entity.get("type") in ("TEXT", "MTEXT")

        rec = {
            "id": uuid_factory(),
            "project_id": project_id,
            "discipline": discipline,
            "sheet": _detect_sheet(entity.get("layer") or ""),
            "kind": kind,
            "label": entity.get("text"),
            "x_mm": xy_mm["x"],
            "y_mm": xy_mm["y"],
            "w_mm": w_mm,
            "h_mm": h_mm,
            "rotation": entity.get("rotation") or 0.0,
            "meta": {
                "layer": entity.get("layer") or "0",
                "type": entity.get("type"),
                "startPoint": conv_pt(entity.get("startPoint")),
                "endPoint": conv_pt(entity.get("endPoint")),
                "position": conv_pt(entity.get("position")),
                "center": conv_pt(entity.get("center")),
                "vertices": (
                    [_conv_pt(v, factor) for v in entity["vertices"]]
                    if entity.get("vertices")
                    else None
                ),
                "radius": conv(entity.get("radius")),
                "startAngle": entity.get("startAngle"),
                "endAngle": entity.get("endAngle"),
                "closed": bool((entity.get("flags") or 0) & 1),
                "insUnits": ins_units,
            },
        }
        out.append(rec)
        if is_text and entity.get("text"):
            labels.append(
                {
                    "x": xy_mm["x"],
                    "y": xy_mm["y"],
                    "text": str(entity["text"]),
                    "sheet": rec["sheet"],
                }
            )

    # Pass 2 — attach nearest label to opening/duct/pipe/beam/equipment
    for rec in out:
        if rec["kind"] not in ("opening", "duct", "pipe", "beam", "column", "equipment", "block"):
            continue
        best = None
        best_dist = float("inf")
        for lbl in labels:
            if lbl["sheet"] != rec["sheet"]:
                continue
            d = ((lbl["x"] - rec["x_mm"]) ** 2 + (lbl["y"] - rec["y_mm"]) ** 2) ** 0.5
            if d < best_dist and d < label_radius_mm:
                best_dist = d
                best = lbl
        if best is not None and not rec.get("label"):
            rec["label"] = best["text"]

    return out
