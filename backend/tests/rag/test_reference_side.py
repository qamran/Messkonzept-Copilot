"""MKC-50 mutation pass: the retriever's reference side (a `§ <n> [Abs. <m>]` in the query
ranks that paragraph's chunks by `source_ref`, the named Absatz first).

The chunk texts hold no digits and none of the query words, so the keyword side finds
nothing and the reference side alone decides what a reference adds. Unit vectors as in
`test_retriever.py`: "Abschnitt 1" is first on the vector side; of the § 14a
chunks, "Abs. 2a" (6th) comes just before "Abs. 1" (7th).
"""

from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.rag.test_retriever import ScriptedEmbedder, _vector

# Inserted in this order, so the chunk ids rise down the list.
ROWS = [
    ("§ 1 Abs. 1", "Alpha Zweck", 0.90),
    ("§ 1 Abs. 2", "Beta Geltung", 0.80),
    ("§ 14 Abs. 1", "Gamma Pflichten", 0.70),
    ("§ 3", "Delta Inkrafttreten", 0.60),
    ("§ 14a Abs. 1", "Epsilon Vereinbarung", 0.10),
    ("§ 14a Abs. 2", "Zeta Gateway", -0.50),
    ("§ 14a Abs. 2a", "Eta Sonderfall", 0.20),
    ("Abschnitt 1", "Theta Allgemeines", 0.95),
]


@pytest.fixture
def references(corpus_engine: Engine) -> None:
    from mkc.db.models import Chunk as ChunkRow
    from mkc.db.models import CorpusDocument
    from mkc.rag.embeddings import EMBEDDING

    with Session(corpus_engine) as session, session.begin():
        document = CorpusDocument(source_id="refg", title="Referenzgesetz (synthetisch)",
                                  source_type="law", url="https://example.org/refg",
                                  version="2026", licence="official")  # fmt: skip
        session.add(document)
        session.flush()
        for ordinal, (ref, body, cosine) in enumerate(ROWS):
            session.add(
                ChunkRow(document_id=document.id, ordinal=ordinal, source_ref=ref, text=body,
                         embedding=_vector(cosine, 2 + ordinal, EMBEDDING.dim))
            )  # fmt: skip
            session.flush()


def _retrieve(engine: Engine, query: str, k: int) -> tuple[list[Any], Any]:
    from mkc.rag.embeddings import EMBEDDING
    from mkc.rag.retriever import retrieve

    seen: list[Any] = []
    with Session(engine) as session:
        found = retrieve(query, k, session=session, embedder=ScriptedEmbedder(EMBEDDING.dim),
                         tracers=[seen.append])  # fmt: skip
    return found, seen[0]


@pytest.mark.parametrize(
    ("query", "hits"),
    [
        ("§ 1", 2),  # § 1 Abs. 1 and 2, not § 14 or § 14a
        ("§ 14", 1),  # not § 14a
        ("§ 3", 1),  # a paragraph without Absätze: its source_ref is "§ 3" exactly
        ("§ 14a", 3),
        ("§14a Abs. 2a", 3),  # no space after §
        ("§ 7", 0),
        ("Was gilt nach § 1 und § 3?", 3),
        ("Kein Verweis hier", 0),
    ],
)
def test_the_reference_side_finds_exactly_the_named_paragraphs(
    references: None, corpus_engine: Engine, query: str, hits: int
) -> None:
    _, trace = _retrieve(corpus_engine, query, 3)
    assert trace.keyword_hits == 0, "the texts share no term with the query"
    assert trace.reference_hits == hits


@pytest.mark.parametrize("query", ["§ 14a Abs. 2a", "§ 14a Absatz 2a", "§ 14a Abs 2a"])
def test_the_named_lettered_absatz_comes_first(
    references: None, corpus_engine: Engine, query: str
) -> None:
    """It has the highest id of its paragraph and is only one place ahead of `Abs. 1` on the
    vector side, so `Abs. 1` would win if the reference side ranked by id alone
    (1/61 + 1/67 > 1/63 + 1/66); "named Absatz first" puts it on top."""
    found, _ = _retrieve(corpus_engine, query, 1)
    assert [c.source_ref for c in found] == ["§ 14a Abs. 2a"]


def test_a_named_paragraph_beats_the_vector_side_alone(
    references: None, corpus_engine: Engine
) -> None:
    """ "§ 3" is 5th on the vector side and found by no keyword: the reference side lifts it
    above "Abschnitt 1", the vector side's first."""
    found, _ = _retrieve(corpus_engine, "§ 3", 2)
    assert [c.source_ref for c in found] == ["§ 3", "Abschnitt 1"]
    assert found[0].score == pytest.approx(1 / 61 + 1 / 65)
