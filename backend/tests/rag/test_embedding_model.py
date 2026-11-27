"""MKC-49 success criterion: one multilingual embedding model chosen and recorded in ADR 004.

The model and its dimension live in one config value, `mkc.rag.embeddings.EMBEDDING`; the
tests read them from there and never name a model.
"""

from pathlib import Path

ADR_004 = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "adr"
    / "241120261441-adr-004-rag-and-decision-layer.md"
)


def test_one_embedding_model_is_configured() -> None:
    from mkc.rag.embeddings import EMBEDDING

    assert isinstance(EMBEDDING.model, str) and EMBEDDING.model.strip()
    assert isinstance(EMBEDDING.dim, int) and EMBEDDING.dim > 0


def test_embedding_model_recorded_in_adr_004() -> None:
    from mkc.rag.embeddings import EMBEDDING

    assert EMBEDDING.model in ADR_004.read_text(encoding="utf-8"), (
        f"ADR 004 does not name the embedding model {EMBEDDING.model!r}"
    )
