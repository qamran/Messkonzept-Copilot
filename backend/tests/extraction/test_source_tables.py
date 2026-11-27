"""MKC-21: tables `operator` and `source_document` exist after the migrations.

Design section 7: Operator (id, name, voltage level, allow-listed catalogue URL, edition);
SourceDocument (operator, URL, sha256, fetched_at, page count). `edition` on a source
document numbers the operator's editions 1, 2, ... (Review Focus 1). No PDF bytes are stored
in Postgres: the file lives in Storage only.
"""

from sqlalchemy import Engine, inspect

OPERATOR_COLUMNS = {"id", "name", "voltage_level", "url", "edition"}
SOURCE_DOCUMENT_COLUMNS = {
    "id",
    "operator_id",
    "url",
    "sha256",
    "fetched_at",
    "page_count",
    "edition",
}


def test_operator_and_source_document_tables_exist(engine: Engine) -> None:
    insp = inspect(engine)
    assert insp.has_table("operator")
    assert insp.has_table("source_document")


def test_operator_columns(engine: Engine) -> None:
    insp = inspect(engine)
    assert insp.has_table("operator")
    assert {c["name"] for c in insp.get_columns("operator")} >= OPERATOR_COLUMNS


def test_source_document_columns_and_keys(engine: Engine) -> None:
    insp = inspect(engine)
    assert insp.has_table("source_document")
    assert {c["name"] for c in insp.get_columns("source_document")} >= SOURCE_DOCUMENT_COLUMNS
    fks = {
        (tuple(f["constrained_columns"]), f["referred_table"])
        for f in insp.get_foreign_keys("source_document")
    }
    assert (("operator_id",), "operator") in fks
    # One row per edition of an operator: a new hash is a new edition, never an overwrite.
    unique = {tuple(u["column_names"]) for u in insp.get_unique_constraints("source_document")}
    assert ("operator_id", "edition") in unique


def test_no_pdf_bytes_in_postgres(engine: Engine) -> None:
    insp = inspect(engine)
    assert insp.has_table("source_document")
    for table in ("operator", "source_document"):
        binary = [c["name"] for c in insp.get_columns(table) if "BYTEA" in str(c["type"]).upper()]
        assert binary == [], f"{table} stores bytes {binary}: PDFs belong in Storage only"
