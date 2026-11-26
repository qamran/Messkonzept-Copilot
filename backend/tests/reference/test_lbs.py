"""MKC-12.2: the LBS reference data loads as cited, validated facts."""

from pathlib import Path

import pytest

from mkc.reference.lbs import (
    DEFAULT_PATH,
    LbsDataError,
    check_digit,
    is_valid_code,
    load_lbs,
    load_lbs_source,
)

# Stromnetz Berlin, "Messkonzepte", Ausgabe September 2026, pages 6-7: the table
# "Code der LBS / Bezeichnung nach edi@energy". Facts only (codes), no text from the PDF.
BERLIN_LBS_CODES = {
    "9992000000018",
    "9992000000026",
    "9992000000034",
    "9992000000042",
    "9992000000068",
    "9992000000076",
    "9992000000084",
    "9992000000109",
    "9992000000117",
    "9992000000125",
    "9992000000133",
    "9992000000159",
    "9992000000167",
    "9992000000175",
    "9992000000183",
}

SOURCE = """\
source:
  title: Codeliste der Lokationsbündelstrukturen
  publisher: BDEW
  version: "1.0"
  edition: Konsolidierte Lesefassung mit Fehlerkorrekturen, Stand 13.12.2024
  applies_from: "2024-10-01"
  url: https://bdew-mako.de/pdf/example.pdf
  sha256: "0000"
  retrieved: "2026-11-26"
"""

OBJECT = (
    '      - {code: "9992000001016", objekt: MaLo, richtung: Verbrauch, ebene: 1,'
    ' flexibilitaet: Starr, anzahl: "1"}\n'
)


def _structure(code: str) -> str:
    return f"  - code: {code}\n    bezeichnung: Test\n    page: 17\n    objects:\n" + OBJECT


def _write(tmp_path: Path, *codes: str) -> Path:
    path = tmp_path / "lbs.yaml"
    body = "structures:\n" + "".join(_structure(c) for c in codes)
    path.write_text(SOURCE + body, encoding="utf-8")
    return path


def test_check_digit_matches_awh_example() -> None:
    # BDEW AWH "Identifikatoren in der Marktkommunikation" 1.2, section 8.1: MaLo-ID example.
    assert check_digit("4137355924") == 1


def test_lbs_codes_are_13_digits_with_valid_check_digit() -> None:
    structures = load_lbs(DEFAULT_PATH)
    assert len(structures) == 15
    codes = [s.code for s in structures] + [o.code for s in structures for o in s.objects]
    assert all(len(c) == 13 and c.isdigit() for c in codes)
    assert all(is_valid_code(c) for c in codes)


def test_invalid_check_digit_is_rejected(tmp_path: Path) -> None:
    assert is_valid_code("9992000000027") is False
    with pytest.raises(LbsDataError, match="9992000000027"):
        load_lbs(_write(tmp_path, '"9992000000027"'))


def test_loader_rejects_duplicate_codes(tmp_path: Path) -> None:
    with pytest.raises(LbsDataError, match="duplicate.*9992000000026"):
        load_lbs(_write(tmp_path, '"9992000000026"', '"9992000000026"'))


def test_loader_rejects_non_string_code(tmp_path: Path) -> None:
    # Unquoted digits load as an int in YAML; the loader must not accept that silently.
    with pytest.raises(LbsDataError, match="string"):
        load_lbs(_write(tmp_path, "9992000000026"))


def test_loader_accepts_a_valid_file(tmp_path: Path) -> None:
    structures = load_lbs(_write(tmp_path, '"9992000000026"'))
    assert [s.code for s in structures] == ["9992000000026"]
    assert structures[0].objects[0].anzahl == "1"


def test_every_code_in_berlin_table_exists() -> None:
    codes = {s.code for s in load_lbs(DEFAULT_PATH)}
    assert codes >= BERLIN_LBS_CODES


def test_umlaut_round_trips() -> None:
    by_code = {s.code: s for s in load_lbs(DEFAULT_PATH)}
    assert by_code["9992000000175"].bezeichnung == (
        "Verbrauchskaskade mit ungemessenen TR (Wärmepumpenkaskade)"
    )


def test_object_codes_are_consistent() -> None:
    # One object code is one position (Objekt, Richtung, Ebene) in every structure.
    # A column shift during extraction would break this.
    seen: dict[str, tuple[str, str, int]] = {}
    for structure in load_lbs(DEFAULT_PATH):
        for obj in structure.objects:
            key = (obj.objekt, obj.richtung, obj.ebene)
            assert seen.setdefault(obj.code, key) == key, obj.code


def test_known_composition_of_standard_structure() -> None:
    # Codeliste 13.12.2024, section 4.2, page 19.
    standard = {s.code: s for s in load_lbs(DEFAULT_PATH)}["9992000000026"]
    assert standard.page == 19
    assert [(o.code, o.objekt, o.anzahl) for o in standard.objects] == [
        ("9992000001032", "MeLo", "1"),
        ("9992000001024", "TR", "0-N"),
        ("9992000001016", "MaLo", "1"),
        ("9992000001256", "NeLo", "0-1"),
    ]


def test_source_names_edition() -> None:
    source = load_lbs_source(DEFAULT_PATH)
    assert "13.12.2024" in source.edition
    assert source.url.startswith("https://bdew-mako.de/")
    assert source.version == "1.0"
