"""Unit tests for the DXF parser — covers the tolerant-desync recovery."""

from app.services.parse import (
    DWG_VERSIONS,
    INSUNITS_TO_MM,
    classify_dxf_entity,
    parse_file,
    units_to_mm,
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


def test_insunits_to_mm_complete_table():
    # All codes used in the parser should map to mm factors
    for code, expected in [(0, 1), (1, 25.4), (2, 304.8), (4, 1), (5, 10), (6, 1000)]:
        assert INSUNITS_TO_MM[code] == expected
