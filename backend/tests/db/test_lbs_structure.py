"""MKC-12.3: table `lbs_structure` and loading the LBS reference data into it."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from mkc.reference.lbs import DEFAULT_PATH, load_lbs, load_lbs_source
from mkc.reference.sync import main, sync_lbs

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
COLUMNS = {"code", "bezeichnung", "objects", "source", "version"}


def _columns(url: URL) -> set[str] | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            if not insp.has_table("lbs_structure"):
                return None
            return {c["name"] for c in insp.get_columns("lbs_structure")}
    finally:
        engine.dispose()


def test_0003_creates_lbs_structure_and_downgrades(database_env: URL) -> None:
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")
    assert _columns(database_env) == COLUMNS

    command.downgrade(config, "0002")
    assert _columns(database_env) is None

    command.upgrade(config, "head")
    command.upgrade(config, "head")  # the deploy hook runs it on every release
    assert _columns(database_env) == COLUMNS


def test_sync_lbs_loads_15_rows_and_is_idempotent(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    structures, source = load_lbs(DEFAULT_PATH), load_lbs_source(DEFAULT_PATH)
    engine = create_engine(database_env)
    try:
        for _ in range(2):
            with Session(engine) as session, session.begin():
                assert sync_lbs(session, structures, source) == 15
        with engine.connect() as conn:
            assert conn.execute(text("select count(*) from lbs_structure")).scalar_one() == 15
            row = conn.execute(
                text("select * from lbs_structure where code = '9992000000026'")
            ).mappings().one()
    finally:
        engine.dispose()
    assert row["bezeichnung"] == "Verbrauch mit einer Messlokation (Standard)"
    assert row["objects"][0]["code"] == "9992000001032"
    assert row["objects"][0]["funktion"] == "Netzübergabe"
    assert "13.12.2024" in row["version"]
    assert row["source"].endswith("#page=19")


def test_sync_lbs_updates_a_changed_row(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    engine = create_engine(database_env)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "insert into lbs_structure values "
                    "('9992000000026', 'old', '[]'::jsonb, 'old', 'old')"
                )
            )
        with Session(engine) as session, session.begin():
            sync_lbs(session, load_lbs(DEFAULT_PATH), load_lbs_source(DEFAULT_PATH))
        with engine.connect() as conn:
            name = conn.execute(
                text("select bezeichnung from lbs_structure where code = '9992000000026'")
            ).scalar_one()
    finally:
        engine.dispose()
    assert name == "Verbrauch mit einer Messlokation (Standard)"


def test_mkc_load_lbs_command(database_env: URL) -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    assert main() == 0
    engine = create_engine(database_env)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("select count(*) from lbs_structure")).scalar_one() == 15
    finally:
        engine.dispose()
