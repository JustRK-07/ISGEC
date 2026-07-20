"""DXF entity extraction + DWG metadata extraction — Python port of lib/parse.js.

Targets BACKEND_ARCHITECTURE §2 (Layer 1 — DWG → DXF & Entity Extraction).

The current Node parser in lib/parse.js is a hand-rolled tolerant DXF reader. We
port the desync-recovery logic verbatim (lines 88-110 of the JS), then optionally
swap in ezdxf for cleaner upstream parsing once production traffic validates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


def parse_file(file_path: str | Path, original_name: str | None = None) -> ParsedDrawing:
    """Top-level dispatcher — picks the parser based on extension."""
    name = original_name or str(file_path)
    ext = Path(name).suffix.lower()
    data = Path(file_path).read_bytes()

    if ext == ".dxf":
        return _parse_dxf(data, name)
    if ext == ".dwg":
        return _parse_dwg(data, name, str(file_path))
    if ext == ".ifc":
        return _parse_ifc(data, name)
    if ext == ".pdf":
        return _parse_pdf_stub(name)
    return ParsedDrawing(ok=False, kind="unknown", error=f"Unsupported extension {ext}")


# --------------------------------------------------------------------------- #
# DXF — tolerant parser (port of parseDxf from lib/parse.js)
# --------------------------------------------------------------------------- #


def _parse_dxf(buf: bytes, name: str) -> ParsedDrawing:
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

    # Pass 1 — walk ENTITIES / BLOCKS section
    entities: list[dict] = []
    i = 0
    in_entities = False
    block_depth = 0
    in_model_block = False
    last_entity_start = -1
    while i < len(tokens):
        code, value = tokens[i]
        if code == 2 and value in ("ENTITIES", "BLOCKS"):
            in_entities = True
            i += 1
            continue
        if in_entities and code == 0 and value in ("ENDSEC", "EOF"):
            break
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
            else:
                block_depth += 1
            i += 1
            continue
        if in_entities and code == 0 and value == "ENDBLK":
            if block_depth > 0:
                block_depth -= 1
            elif in_model_block:
                in_model_block = False
            i += 1
            continue
        if in_entities and code == 0:
            if i > last_entity_start:
                result = _parse_entity(tokens, i)
                if result is not None:
                    rec, next_i = result
                    entities.append(rec)
                    last_entity_start = i
                    i = next_i
                    continue
            last_entity_start = i
        i += 1

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

    return ParsedDrawing(
        ok=True,
        kind="dxf",
        entity_count=len(entities),
        entities=entities,
        layers=layers,
        text_labels=labels[:200],
        header={"$INSUNITS": ins_units},
        parse_meta={
            "kind": "dxf",
            "parser": "custom",
            "entityCount": len(entities),
            "layers": layers,
            "headerUnits": ins_units,
            "textLabels": labels[:200],
        },
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
                last_vert_set = False
        elif code == 20:
            y = float(value)
            if is_poly and rec["vertices"]:
                rec["vertices"][-1]["y"] = y
            pos["y"] = y
        elif code == 30:
            pos["z"] = float(value)
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
            rec["rotation"] = float(value)
        elif code == 41:
            rec["scale"] = float(value)
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


def _parse_dwg(buf: bytes, name: str, file_path: str) -> ParsedDrawing:
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

    # Attempt real conversion via ezdxf's addons.dwg2dxf if available.
    full_parse = _convert_dwg_with_ezdxf(file_path, name)
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
            "conversion": "ezdxf",
        }
        return full_parse

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
            "note": "ezdxf dwg2dxf not available; sent metadata to LLM.",
        },
        header={"dwgVersion": version},
    )


def _convert_dwg_with_ezdxf(file_path: str, name: str) -> ParsedDrawing | None:
    """Try ezdxf's addons.dwg2dxf (requires libredwg installed)."""
    try:
        from ezdxf.addons import dwg2dxf  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        # ezdxf exposes a high-level DWG→DXF converter.
        result = dwg2dxf.convert(file_path)  # type: ignore[attr-defined]
        if not result or not result.dxf_string:
            return None
        return _parse_dxf(result.dxf_string.encode("utf-8"), name)
    except Exception:
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


def classify_dxf_entity(entity: dict) -> str:
    layer = (entity.get("layer") or "").upper()
    t = (entity.get("type") or "").upper()
    if t in ("TEXT", "MTEXT"):
        return "text"
    if "GRID" in layer:
        return "grid-bubble"
    if "OPEN" in layer or "PENETR" in layer or "SLEEVE" in layer:
        return "opening"
    if "BEAM" in layer or "BM" in layer or "GIRDER" in layer:
        return "beam"
    if "COL" in layer or "PILLAR" in layer:
        return "column"
    if "PIPE" in layer:
        return "pipe"
    if "DUCT" in layer:
        return "duct"
    if "EQUIP" in layer or "MECH" in layer:
        return "equipment"
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
    m = re.search(r"(\d{4})", layer or "")
    return m.group(1) if m else "default"


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
