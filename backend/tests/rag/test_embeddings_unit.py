"""MKC-49.3 unit tests: embeddings go through our provider layer, with zero-data-retention
routing, no hidden retries, input order kept and the configured dimension checked.

Only the HTTP transport is fake; no test here reaches the network.
"""

import json
from collections.abc import Sequence
from typing import Any

import httpx
import pytest

from mkc.config import Settings


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("MKC_OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("MKC_MODEL_MODE", "live")
    return Settings()


def _reply(vectors: list[list[float]], order: Sequence[int] | None = None) -> dict[str, Any]:
    order = list(order) if order is not None else list(range(len(vectors)))
    data = [{"object": "embedding", "index": i, "embedding": vectors[i]} for i in order]
    return {
        "object": "list",
        "model": "q/embed",
        "data": data,
        "usage": {"prompt_tokens": 7, "total_tokens": 7},
    }


def _transport(replies: list[httpx.Response], sent: list[dict[str, Any]]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return replies[len(sent) - 1]

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_embed_call_asks_for_zdr_floats_and_the_dimension(settings: Settings) -> None:
    from mkc.models.providers import build_embed_call

    sent: list[dict[str, Any]] = []
    reply = httpx.Response(200, json=_reply([[1.0, 0.0], [0.0, 1.0]], order=[1, 0]))
    call = build_embed_call(
        "openrouter", "q/embed", settings, 30, dimensions=2, http_client=_transport([reply], sent)
    )
    vectors, tokens = call(["a", "b"])
    (body,) = sent
    assert body["model"] == "q/embed"
    assert body["input"] == ["a", "b"]
    assert body["dimensions"] == 2
    assert body["encoding_format"] == "float"
    assert body["provider"] == {"zdr": True, "data_collection": "deny"}
    assert vectors == [[1.0, 0.0], [0.0, 1.0]], "sorted back into input order by index"
    assert tokens == 7


@pytest.mark.parametrize("status", [503, 429])
def test_embed_call_sends_one_request_on_errors(settings: Settings, status: int) -> None:
    from mkc.models.providers import build_embed_call

    sent: list[dict[str, Any]] = []
    reply = httpx.Response(status, json={"error": {"code": status, "message": "down"}})
    http = _transport([reply, reply, reply], sent)
    call = build_embed_call("openrouter", "q/embed", settings, 30, dimensions=2, http_client=http)
    with pytest.raises(Exception):  # noqa: B017 - any error; the point is one request
        call(["a"])
    assert len(sent) == 1


@pytest.mark.parametrize(
    "vectors",
    [
        [[1.0, 0.0]],  # one vector for two texts
        [[1.0, 0.0], [1.0, 0.0, 0.0]],  # a wrong dimension
    ],
)
def test_embed_call_refuses_a_wrong_reply(settings: Settings, vectors: list[list[float]]) -> None:
    from mkc.models.providers import build_embed_call
    from mkc.models.types import ModelError

    reply = httpx.Response(200, json=_reply(vectors))
    http = _transport([reply], [])
    call = build_embed_call("openrouter", "q/embed", settings, 30, dimensions=2, http_client=http)
    with pytest.raises(ModelError):
        call(["a", "b"])


def test_embed_call_needs_openrouter_and_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from mkc.models.providers import build_embed_call
    from mkc.models.types import ModelConfigError

    monkeypatch.delenv("MKC_OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("MKC_GOOGLE_API_KEY", "g-test")
    with pytest.raises(ModelConfigError):
        build_embed_call("openrouter", "q/embed", Settings(), 30, dimensions=2)
    with pytest.raises(ModelConfigError):
        build_embed_call("gemini", "g/embed", Settings(), 30, dimensions=2)


# --- EmbeddingClient -------------------------------------------------------------------


class FakeCall:
    def __init__(self, dim: int = 2) -> None:
        self.batches: list[list[str]] = []
        self.dim = dim

    def __call__(self, texts: Sequence[str]) -> tuple[list[list[float]], int]:
        self.batches.append(list(texts))
        return [[float(len(t))] * self.dim for t in texts], 10 * len(texts)


def _client(call: FakeCall, **kwargs: Any) -> Any:
    from mkc.models.client import EmbeddingClient
    from mkc.models.config import load_models_config
    from mkc.rag.embeddings import EMBEDDING

    def factory(provider: str, model: str, dimensions: int, timeout: float) -> FakeCall:
        assert (provider, model, dimensions) == (EMBEDDING.provider, EMBEDDING.model, 2)
        return call

    options: dict[str, Any] = {
        "provider": EMBEDDING.provider,
        "model": EMBEDDING.model,
        "dim": 2,
        "batch_size": 2,
    }
    options.update(kwargs)
    return EmbeddingClient(load_models_config(), factory, **options)


def test_client_batches_and_costs_from_models_yaml() -> None:
    from mkc.models.config import load_models_config
    from mkc.rag.embeddings import EMBEDDING

    call = FakeCall()
    reply = _client(call).embed(["a", "bb", "ccc", "dddd", "eeeee"])
    assert call.batches == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    assert reply.vectors == [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0], [5.0, 5.0]]
    assert reply.input_tokens == 50
    expected = load_models_config().cost_eur(EMBEDDING.provider, EMBEDDING.model, 50, 0)
    assert reply.cost_eur == pytest.approx(expected)
    assert reply.model_id == f"{EMBEDDING.provider}:{EMBEDDING.model}"


def test_client_makes_no_call_for_no_text() -> None:
    call = FakeCall()
    reply = _client(call).embed([])
    assert (reply.vectors, reply.input_tokens, call.batches) == ([], 0, [])


def test_client_refuses_replay_mode_and_an_unpriced_model() -> None:
    from mkc.models.types import ModelConfigError

    with pytest.raises(ModelConfigError, match="live"):
        _client(FakeCall(), mode="replay")
    with pytest.raises(ModelConfigError, match="price"):
        _client(FakeCall(), model="nobody/unpriced")


def test_client_classifies_provider_errors() -> None:
    from mkc.models.types import TransientModelError

    class Busy(Exception):
        status_code = 503

    def failing(texts: Sequence[str]) -> tuple[list[list[float]], int]:
        raise Busy("busy")

    from mkc.models.providers import classify_error

    client = _client(FakeCall(), classify=classify_error)
    client._factory = lambda *args: failing
    with pytest.raises(TransientModelError) as caught:
        client.embed(["a"])
    assert isinstance(caught.value.__cause__, Busy)


def test_from_settings_refuses_replay_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from mkc.models.client import EmbeddingClient
    from mkc.models.types import ModelConfigError
    from mkc.rag.embeddings import EMBEDDING

    monkeypatch.setenv("MKC_MODEL_MODE", "replay")
    monkeypatch.setenv("MKC_MODEL_REPLAY_DIR", "x")
    with pytest.raises(ModelConfigError, match="live"):
        EmbeddingClient.from_settings(
            Settings(), provider=EMBEDDING.provider, model=EMBEDDING.model, dim=EMBEDDING.dim
        )


# --- the corpus embedder ---------------------------------------------------------------


def test_embedding_model_is_priced_and_fits_an_ann_index() -> None:
    from mkc.models.config import load_models_config
    from mkc.rag.embeddings import EMBEDDING

    assert EMBEDDING.model in load_models_config().prices[EMBEDDING.provider]
    assert EMBEDDING.dim <= 2000, "pgvector indexes `vector` columns up to 2000 dimensions"


def test_provider_embedder_passes_texts_verbatim_and_counts_spend() -> None:
    from mkc.rag.embeddings import ProviderEmbedder

    call = FakeCall()
    embedder = ProviderEmbedder(_client(call), dim=2)
    assert embedder.embed(["§ 1 Zweck", "(1) Text."]) == [[9.0, 9.0], [9.0, 9.0]]
    assert embedder.embed(["x"]) == [[1.0, 1.0]]
    assert call.batches == [["§ 1 Zweck", "(1) Text."], ["x"]], "no prefix on documents"
    assert embedder.input_tokens == 30
    assert embedder.cost_eur > 0
