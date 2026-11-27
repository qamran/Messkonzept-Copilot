"""MKC-49: tables `corpus_document` and `chunk` (embedding vector, German full text).

No revision number is named here: lane A also writes the next migration, and the coordinator
may re-chain this lane's one (AGENTS.md, Parallel lanes). The round trip to base is covered
by tests/db/test_migrations.py.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
DOCUMENT_COLUMNS = {"id", "source_id", "title", "source_type", "url", "version", "licence"}
CHUNK_COLUMNS = {"id", "document_id", "ordinal", "source_ref", "text", "embedding", "tsv"}


def test_corpus_tables_exist_at_head(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    engine = create_engine(database_env)
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            assert insp.has_table("corpus_document"), "table corpus_document missing"
            assert insp.has_table("chunk"), "table chunk missing"
            document = {c["name"] for c in insp.get_columns("corpus_document")}
            chunk = {c["name"] for c in insp.get_columns("chunk")}
            fks = insp.get_foreign_keys("chunk")
            types = dict(
                conn.execute(
                    text(
                        "select attname, format_type(atttypid, atttypmod) from pg_attribute "
                        "where attrelid = 'chunk'::regclass and attname in ('embedding', 'tsv')"
                    )
                ).all()
            )
            indexes = conn.execute(
                text("select indexdef from pg_indexes where tablename = 'chunk'")
            ).scalars()
            gin_on_tsv = [d for d in indexes if "gin" in d.lower() and "tsv" in d]
    finally:
        engine.dispose()

    assert document >= DOCUMENT_COLUMNS, sorted(DOCUMENT_COLUMNS - document)
    assert chunk >= CHUNK_COLUMNS, sorted(CHUNK_COLUMNS - chunk)
    assert any(
        fk["referred_table"] == "corpus_document" and fk["constrained_columns"] == ["document_id"]
        for fk in fks
    ), fks
    from mkc.rag.embeddings import EMBEDDING

    assert types["embedding"] == f"vector({EMBEDDING.dim})"
    assert types["tsv"] == "tsvector"
    assert gin_on_tsv, "no GIN index on chunk.tsv"
