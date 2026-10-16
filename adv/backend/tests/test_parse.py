"""Unit tests for the DXF parser — covers the tolerant-desync recovery."""

from app.services.parse import (
    DWG_VERSIONS,
    INSUNITS_TO_MM,
    classify_dxf_entity,
    parse_file,
    units_to_mm,
    dxf_to_entities,
)


def test_units_to_mm():
    assert units_to_mm(6) == 1000  # metres → mm
    assert units_to_mm(4) == 1     # already mm
    assert units_to_mm(None) == 1  # default
    assert units_to_mm(99) == 1    # unknown → default


def test_dwg_versions_known_keys():
    # The DWG magic-byte table should at least cover R2018
    assert "AC1032" in DWG_VERSIONS
    assert DWG_VERSIONS["AC1032"] == "R2018"


def test_parse_file_unknown_extension_returns_error(tmp_path):
    """An existing file with an unsupported extension must report ok=False."""
    p = tmp_path / "nope.xyz"
    p.write_bytes(b"some bytes")
    result = parse_file(p, "nope.xyz")
    assert not result.ok
    assert "Unsupported extension" in (result.error or "")


def test_classify_dxf_entity_by_layer():
    assert classify_dxf_entity({"type": "LINE", "layer": "GRID-A"}) == "grid-bubble"
    assert classify_dxf_entity({"type": "LINE", "layer": "OPENINGS"}) == "opening"
    assert classify_dxf_entity({"type": "LINE", "layer": "P11-BEAMS"}) == "beam"
    assert classify_dxf_entity({"type": "LINE", "layer": "DUCTWORK"}) == "duct"
    assert classify_dxf_entity({"type": "LINE", "layer": "PIPE-LINE"}) == "pipe"
    assert classify_dxf_entity({"type": "INSERT", "layer": "EQUIP"}) == "equipment"
    assert classify_dxf_entity({"type": "INSERT", "layer": "MODEL"}) == "block"
    assert classify_dxf_entity({"type": "TEXT", "layer": "0"}) == "text"
    assert classify_dxf_entity({"type": "LWPOLYLINE", "layer": "0"}) == "line"


def test_parse_dxf_minimal_file(tmp_path):
    """A minimal hand-rolled DXF should parse and yield entities."""
    dxf = (
        "0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n"
        "0\nSECTION\n2\nENTITIES\n"
        "0\nTEXT\n8\nGRID-A\n10\n100.0\n20\n200.0\n40\n2.5\n1\nTP104-A\n"
        "0\nLWPOLYLINE\n8\nOPENINGS\n10\n300.0\n20\n400.0\n"
        "0\nENDSEC\n0\nEOF\n"
    )
    p = tmp_path / "sample.dxf"
    p.write_bytes(dxf.encode("utf-8"))

    parsed = parse_file(p, "sample.dxf")
    assert parsed.ok
    assert parsed.kind == "dxf"
    assert parsed.entity_count == 2
    assert parsed.header["$INSUNITS"] == 4
    # text label is captured
    text_entities = [e for e in parsed.entities if e["type"] == "TEXT"]
    assert text_entities[0]["text"] == "TP104-A"




def test_parse_arc_preserves_angles_and_normalized_metadata(tmp_path):
    dxf = (
        "0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n"
        "0\nSECTION\n2\nENTITIES\n"
        "0\nARC\n8\nOPENINGS\n10\n100.0\n20\n200.0\n40\n25.0\n50\n30.0\n51\n120.0\n"
        "0\nENDSEC\n0\nEOF\n"
    )
    p = tmp_path / "arc.dxf"
    p.write_bytes(dxf.encode("utf-8"))

    parsed = parse_file(p, "arc.dxf")
    assert parsed.ok
    arc = parsed.entities[0]
    assert arc["startAngle"] == 30.0
    assert arc["endAngle"] == 120.0
    assert "rotation" not in arc

    normalized = dxf_to_entities(parsed, "structural", "project-1", lambda: "entity-1")
    assert normalized[0]["meta"]["radius"] == 25.0
    assert normalized[0]["meta"]["startAngle"] == 30.0
    assert normalized[0]["meta"]["endAngle"] == 120.0
