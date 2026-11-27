"""MKC-49: `backend/data/corpus_sources.yaml`, the narrow corpus with a licence class per
source (feature 69, ADR 004). The file holds only metadata, never a source's text."""

from pathlib import Path

import pytest
import yaml

SOURCES = Path(__file__).resolve().parents[2] / "data" / "corpus_sources.yaml"
# The narrow corpus of ADR 004: EnWG § 14a, MsbG, BK6-22-300 with Anlage 1, BK8-22/010-A.
REQUIRED_IDS = {"enwg-14a", "msbg", "bk6-22-300", "bk6-22-300-anlage-1", "bk8-22-010-a"}
FIELDS = {"id", "title", "source_type", "url", "version", "licence"}
OFFICIAL_TYPES = {"law", "bnetza_decision"}


def _entries() -> list[dict[str, object]]:
    assert SOURCES.is_file(), f"{SOURCES} missing"
    data = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    entries = data["sources"]
    assert isinstance(entries, list) and entries
    return entries


def test_corpus_sources_list_the_narrow_corpus() -> None:
    entries = _entries()
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate source ids"
    assert set(ids) >= REQUIRED_IDS, f"missing: {sorted(REQUIRED_IDS - set(ids))}"
    assert any(e["source_type"] == "operator_text" for e in entries), "no operator texts"


def test_every_source_has_a_licence_class_and_no_text() -> None:
    for entry in _entries():
        assert set(entry) >= FIELDS, (entry.get("id"), sorted(FIELDS - set(entry)))
        assert not {"text", "content", "body"} & set(entry), f"{entry['id']} carries text"
        assert str(entry["url"]).startswith("https://"), entry["id"]
        assert entry["licence"] in {"official", "restricted"}, entry["id"]
        assert entry["source_type"] in OFFICIAL_TYPES | {"operator_text"}, entry["id"]
        # Laws and BNetzA decisions are official works (free to use); operator texts are not.
        expected = "official" if entry["source_type"] in OFFICIAL_TYPES else "restricted"
        assert entry["licence"] == expected, entry["id"]


def test_load_sources_reads_the_default_file() -> None:
    from mkc.rag.sources import DEFAULT_SOURCES_PATH, LicenceClass, SourceType, load_sources

    assert DEFAULT_SOURCES_PATH == SOURCES
    sources = load_sources(DEFAULT_SOURCES_PATH)
    by_id = {s.id: s for s in sources}
    assert set(by_id) >= REQUIRED_IDS
    assert by_id["enwg-14a"].licence is LicenceClass.OFFICIAL
    assert by_id["enwg-14a"].source_type is SourceType.LAW
    assert by_id["bk8-22-010-a"].source_type is SourceType.BNETZA_DECISION
    operator = [s for s in sources if s.source_type is SourceType.OPERATOR_TEXT]
    assert operator and all(s.licence is LicenceClass.RESTRICTED for s in operator)


def test_load_sources_refuses_a_bad_file(tmp_path: Path) -> None:
    from mkc.rag.sources import CorpusSourceError, load_sources

    bad = tmp_path / "bad.yaml"
    bad.write_text("sources:\n  - id: x\n    licence: public-domain\n", encoding="utf-8")
    with pytest.raises(CorpusSourceError):
        load_sources(bad)
