"""Shared helpers for the RAG corpus tests (MKC-49, lane D).

Nothing here makes a network or model call: the text of a source comes from a fake fetcher
and its embeddings from a fake embedder. `mkc.rag` is imported inside the fixtures, so a
missing module fails each test on its own instead of the whole file at collection.
"""

import hashlib
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

# Synthetic law text in the layout of gesetze-im-internet.de: a heading line per §, then
# numbered Absätze. § 2 (3) mentions "§ 14a" inside a sentence: that is not a boundary.
LAW_TEXT = """\
§ 1 Zweck des Gesetzes
(1) Dieses Gesetz regelt den Betrieb von Messstellen in Musterstadt.
(2) Es gilt für alle Messstellenbetreiber im Netzgebiet.

§ 2 Begriffsbestimmungen
(1) Messstelle ist die Gesamtheit aller Mess- und Steuerungseinrichtungen.
(2) Messstellenbetreiber ist, wer den Messstellenbetrieb wahrnimmt.
(3) Steuerbare Verbrauchseinrichtung ist eine Wärmepumpe nach § 14a dieses Gesetzes.

§ 14a Netzorientierte Steuerung
(1) Betreiber von Verteilernetzen schließen Vereinbarungen mit Messstellenbetreibern.
(2) Die Steuerung erfolgt über ein Smart-Meter-Gateway.
"""

SOURCES_YAML = """\
sources:
  - id: musterg
    title: Gesetz über den Messstellenbetrieb in Musterstadt (synthetisch)
    source_type: law
    url: https://example.org/musterg
    version: "2026-11-27"
    licence: official
  - id: musterstadt-katalog
    title: Messkonzepte der Stadtwerke Musterstadt (synthetisch)
    source_type: operator_text
    url: https://example.org/musterstadt/katalog
    version: "2026-01"
    licence: restricted
"""

OPERATOR_TEXT = """\
1 Allgemeines
Die Stadtwerke Musterstadt Messtechnik GmbH beschreibt hier ihre Messkonzepte.

2 Messkonzept MK-1
Ein Zweirichtungszähler misst Bezug und Einspeisung der PV-Anlage.
"""

TEXTS = {"musterg": LAW_TEXT, "musterstadt-katalog": OPERATOR_TEXT}


class FakeEmbedder:
    """Deterministic vectors of the configured dimension; records every text it embeds."""

    def __init__(self, model: str, dim: int) -> None:
        self.model = model
        self.dim = dim
        self.texts: list[str] = []

    def vector(self, value: str) -> list[float]:
        digest = hashlib.sha256(value.encode("utf-8")).digest()
        return [round(digest[i % len(digest)] / 255.0 + i * 1e-4, 4) for i in range(self.dim)]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return [self.vector(t) for t in texts]


def fake_fetcher(texts: dict[str, str] = TEXTS) -> Callable[[Any], str]:
    """A fetcher that returns a source's text by its id, without any network call."""

    def fetch(source: Any) -> str:
        return texts[source.id]

    return fetch


@pytest.fixture
def embedder() -> FakeEmbedder:
    from mkc.rag.embeddings import EMBEDDING

    return FakeEmbedder(model="fake-embedder", dim=EMBEDDING.dim)


@pytest.fixture
def sources_file(tmp_path: Path) -> Path:
    path = tmp_path / "corpus_sources.yaml"
    path.write_text(SOURCES_YAML, encoding="utf-8")
    return path


@pytest.fixture
def corpus_engine(database_env: URL) -> Iterator[Engine]:
    """An engine on the migrated test database with empty corpus tables."""
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    eng = create_engine(database_env)
    with eng.begin() as conn:
        conn.execute(text("truncate chunk, corpus_document restart identity cascade"))
    try:
        yield eng
    finally:
        eng.dispose()
