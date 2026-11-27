"""MKC-49.4 unit tests: the ORM classes write and read vectors, `tsv` follows `text`, and a
document's chunks go with it."""

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _document() -> object:
    from mkc.db.models import CorpusDocument

    return CorpusDocument(
        source_id="musterg",
        title="Mustergesetz",
        source_type="law",
        url="https://example.org/musterg",
        version="2026",
        licence="official",
    )


def test_a_chunk_round_trips_its_vector_and_gets_a_german_tsv(corpus_engine: Engine) -> None:
    from mkc.db.models import Chunk
    from mkc.rag.embeddings import EMBEDDING

    vector = [i / EMBEDDING.dim for i in range(EMBEDDING.dim)]
    with Session(corpus_engine) as session, session.begin():
        document = _document()
        session.add(document)
        session.flush()
        session.add(
            Chunk(
                document_id=document.id,  # type: ignore[attr-defined]
                ordinal=0,
                source_ref="§ 1 Abs. 1",
                text="Die Messstellenbetreiber messen.",
                embedding=vector,
            )
        )
    with Session(corpus_engine) as session:
        chunk = session.scalars(select(Chunk)).one()
        assert chunk.embedding == pytest.approx(vector, abs=1e-6)
        found = session.scalar(
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.tsv.op("@@")(func.plainto_tsquery("german", "Messstellenbetreiber")))
        )
        assert found == 1


def test_ordinals_are_unique_per_document_and_chunks_go_with_it(corpus_engine: Engine) -> None:
    from mkc.db.models import Chunk, CorpusDocument
    from mkc.rag.embeddings import EMBEDDING

    def chunk(document_id: int, ordinal: int) -> Chunk:
        return Chunk(
            document_id=document_id,
            ordinal=ordinal,
            source_ref="§ 1",
            text="x",
            embedding=[0.0] * EMBEDDING.dim,
        )

    with Session(corpus_engine) as session, session.begin():
        document = _document()
        session.add(document)
        session.flush()
        document_id = document.id  # type: ignore[attr-defined]
        session.add_all([chunk(document_id, 0), chunk(document_id, 1)])
    with pytest.raises(IntegrityError), Session(corpus_engine) as session, session.begin():
        session.add(chunk(document_id, 1))
    with corpus_engine.begin() as conn:
        conn.execute(text("delete from corpus_document"))
        assert conn.execute(text("select count(*) from chunk")).scalar_one() == 0
    assert CorpusDocument.__tablename__ == "corpus_document"
