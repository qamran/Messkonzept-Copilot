"""MKC-49.2 unit tests: one chunk per Absatz for law text, numbered sections for the rest."""

from tests.rag.conftest import LAW_TEXT, OPERATOR_TEXT


def test_law_text_is_one_chunk_per_absatz_with_its_heading() -> None:
    from mkc.rag.chunking import chunk_text

    chunks = chunk_text(LAW_TEXT, source_id="musterg")
    refs = [c.source_ref for c in chunks]
    assert refs == [
        "§ 1 Abs. 1",
        "§ 1 Abs. 2",
        "§ 2 Abs. 1",
        "§ 2 Abs. 2",
        "§ 2 Abs. 3",
        "§ 14a Abs. 1",
        "§ 14a Abs. 2",
    ]
    first = chunks[5].text.splitlines()
    assert first == [
        "§ 14a Netzorientierte Steuerung",
        "(1) Betreiber von Verteilernetzen schließen Vereinbarungen mit Messstellenbetreibern.",
    ]


def test_a_paragraph_without_absatz_numbers_is_one_chunk() -> None:
    from mkc.rag.chunking import chunk_text

    text = "§ 3 Inkrafttreten\nDieses Gesetz tritt am Tag nach der Verkündung in Kraft.\n"
    (chunk,) = chunk_text(text, source_id="g")
    assert chunk.source_ref == "§ 3"
    assert chunk.text == text.strip()


def test_continuation_lines_stay_with_their_absatz() -> None:
    from mkc.rag.chunking import chunk_text

    text = "§ 5 Pflichten\n(1) Der Betreiber muss\n1. messen,\n2. melden.\n(2) Ende.\n"
    chunks = chunk_text(text, source_id="g")
    assert [c.source_ref for c in chunks] == ["§ 5 Abs. 1", "§ 5 Abs. 2"]
    assert chunks[0].text.splitlines()[1:] == ["(1) Der Betreiber muss", "1. messen,", "2. melden."]


def test_a_double_paragraph_heading_and_whitespace() -> None:
    from mkc.rag.chunking import chunk_text

    text = "§§ 7 bis 9 (weggefallen)\n\n§\u00a010   Schluss\n(1)   Ende   hier.\n"
    chunks = chunk_text(text, source_id="g")
    assert [c.source_ref for c in chunks] == ["§§ 7 bis 9", "§ 10 Abs. 1"]
    assert chunks[1].text == "§ 10 Schluss\n(1) Ende hier."


def test_text_before_the_first_paragraph_is_kept() -> None:
    from mkc.rag.chunking import chunk_text

    chunks = chunk_text("Eingangsformel des Gesetzes.\n" + LAW_TEXT, source_id="g")
    assert chunks[0].source_ref == "Vorspann"
    assert chunks[0].text == "Eingangsformel des Gesetzes."
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_empty_text_gives_no_chunks() -> None:
    from mkc.rag.chunking import chunk_text

    assert chunk_text(" \n\n", source_id="g") == []
    assert chunk_text("", source_id="g", layout="sections") == []


def test_sections_layout_follows_numbered_headings() -> None:
    from mkc.rag.chunking import chunk_text

    chunks = chunk_text(OPERATOR_TEXT, source_id="katalog", layout="sections")
    assert [c.source_ref for c in chunks] == ["Abschnitt 1", "Abschnitt 2"]
    assert chunks[1].text.splitlines() == [
        "2 Messkonzept MK-1",
        "Ein Zweirichtungszähler misst Bezug und Einspeisung der PV-Anlage.",
    ]
    assert all(c.source_id == "katalog" for c in chunks)


def test_sections_layout_does_not_split_at_a_paragraph_sign() -> None:
    from mkc.rag.chunking import chunk_text

    text = "1 Allgemeines\nDie Steuerung folgt\n§ 14a EnWG und der Festlegung.\n"
    (chunk,) = chunk_text(text, source_id="d", layout="sections")
    assert chunk.source_ref == "Abschnitt 1"


def test_sections_layout_with_subsections_and_no_headings() -> None:
    from mkc.rag.chunking import chunk_text

    text = "Vorbemerkung ohne Nummer.\n\n2.1 Zähler\nText A.\n\n2.2 Gateway\nText B.\n"
    chunks = chunk_text(text, source_id="d", layout="sections")
    assert [c.source_ref for c in chunks] == ["Vorspann", "Abschnitt 2.1", "Abschnitt 2.2"]


def test_a_long_section_is_split_at_blank_lines() -> None:
    from mkc.rag.chunking import MAX_CHUNK_CHARS, chunk_text

    block = "Satz " * (MAX_CHUNK_CHARS // 10)
    text = f"3 Lang\n{block}\n\n{block}\n\n{block}\n"
    chunks = chunk_text(text, source_id="d", layout="sections")
    assert len(chunks) >= 2
    assert {c.source_ref for c in chunks} == {"Abschnitt 3"}
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in chunks)
    joined = "\n".join(c.text for c in chunks)
    assert joined.count("Satz") == 3 * (MAX_CHUNK_CHARS // 10)


def test_a_lettered_absatz_is_its_own_chunk() -> None:
    from mkc.rag.chunking import chunk_text

    text = "§ 14a Steuerung\n(1) Eins.\n(2) Zwei.\n(2a) Zwei a.\n(3) Drei.\n"
    chunks = chunk_text(text, source_id="g")
    assert [c.source_ref for c in chunks] == [
        "§ 14a Abs. 1",
        "§ 14a Abs. 2",
        "§ 14a Abs. 2a",
        "§ 14a Abs. 3",
    ]
    assert chunks[2].text == "§ 14a Steuerung\n(2a) Zwei a."


def test_the_section_cap_is_4000_characters() -> None:
    from mkc.rag.chunking import MAX_CHUNK_CHARS, chunk_text

    assert MAX_CHUNK_CHARS == 4000
    part = "Wort " * 380  # 1,900 characters per paragraph
    two = chunk_text(f"4 Teil\n{part}\n\n{part}\n", source_id="d", layout="sections")
    assert len(two) == 1, "3,800 characters stay one chunk"
    three = chunk_text(f"4 Teil\n{part}\n\n{part}\n\n{part}\n", source_id="d", layout="sections")
    assert len(three) == 2, "5,700 characters are split at a blank line"


def test_a_long_law_absatz_stays_whole() -> None:
    """Decision 72: an Absatz is the smallest unit a citation names, so it is never split;
    the largest real one (MsbG, 7,836 characters) fits the model's 32k-token context."""
    from mkc.rag.chunking import MAX_CHUNK_CHARS, chunk_text

    long_absatz = "(1) " + "Satz. " * (2 * MAX_CHUNK_CHARS // 6)
    (chunk,) = chunk_text(f"§ 5 Lang\n{long_absatz}\n", source_id="g")
    assert chunk.source_ref == "§ 5 Abs. 1"
    assert len(chunk.text) > MAX_CHUNK_CHARS
