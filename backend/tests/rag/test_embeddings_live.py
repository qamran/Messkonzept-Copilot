"""MKC-49.3 live check of the corpus embedding model (costs a fraction of a cent).

Run on purpose, from `backend/`:
`uv run --env-file .env pytest -m live tests/rag/test_embeddings_live.py -s`
(`MKC_OPENROUTER_API_KEY` in `.env`; the test sets live mode itself).
"""

import math

import pytest

from mkc.config import Settings

pytestmark = pytest.mark.live


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


def test_live_embeddings_have_the_configured_dimension() -> None:
    from mkc.rag.embeddings import EMBEDDING, ProviderEmbedder

    embedder = ProviderEmbedder.from_settings(Settings(model_mode="live"))
    texts = [
        "§ 14a EnWG: netzorientierte Steuerung von steuerbaren Verbrauchseinrichtungen.",
        "Der Netzbetreiber darf Wärmepumpen bei einem Netzengpass dimmen.",
        "Ein Zweirichtungszähler misst Bezug und Einspeisung der PV-Anlage.",
    ]
    vectors = embedder.embed(texts)
    assert [len(v) for v in vectors] == [EMBEDDING.dim] * 3
    assert _cosine(vectors[0], vectors[1]) > _cosine(vectors[0], vectors[2])
    assert embedder.input_tokens > 0
    print(f"tokens {embedder.input_tokens}, cost {embedder.cost_eur:.8f} EUR")
