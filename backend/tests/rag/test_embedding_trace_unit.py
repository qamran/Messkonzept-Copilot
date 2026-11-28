"""MKC-50 (MKC-49 review findings): `EmbeddingClient` gets trace hooks like `ModelClient`, and
the corpus embedder embeds a query with the model's query instruction.

One `EmbedTrace` per `embed()` call (not per batch): model id, number of texts, tokens, EUR
cost, latency, error and the caller's `TraceScope`. Never the texts themselves.
"""

from collections.abc import Sequence
from dataclasses import fields
from typing import Any

import pytest

from mkc.models.client import TraceScope
from tests.rag.test_embeddings_unit import FakeCall, _client

SECRET = "Geheimer Kundentext Musterstraße 1"


def test_each_embed_call_is_traced_once_with_spend_and_latency() -> None:
    from mkc.models.client import EmbedTrace

    seen: list[Any] = []
    scope = TraceScope(run_id=4, item_id=None, step=1)
    reply = _client(FakeCall(), tracers=[seen.append]).embed(["a", "bb", SECRET], scope=scope)
    assert len(seen) == 1, "one trace for three texts in two batches"
    (trace,) = seen
    assert isinstance(trace, EmbedTrace)
    assert trace.model_id == reply.model_id
    assert trace.texts == 3
    assert trace.input_tokens == reply.input_tokens == 30
    assert trace.cost_eur == pytest.approx(reply.cost_eur)
    assert trace.latency_ms == reply.latency_ms
    assert trace.mode == "live"
    assert trace.error is None
    assert trace.scope == scope


def test_the_trace_holds_no_text() -> None:
    seen: list[Any] = []
    _client(FakeCall(), tracers=[seen.append]).embed([SECRET])
    (trace,) = seen
    names = {f.name for f in fields(trace)}
    assert not {"texts_sent", "input", "text"} & names
    for name in names:
        assert SECRET not in repr(getattr(trace, name)), name


def test_a_failed_embed_call_is_traced_and_raised() -> None:
    from mkc.models.providers import classify_error
    from mkc.models.types import TransientModelError

    class Busy(Exception):
        status_code = 503

    def failing(texts: Sequence[str]) -> tuple[list[list[float]], int]:
        raise Busy("busy")

    seen: list[Any] = []
    client = _client(FakeCall(), classify=classify_error, tracers=[seen.append])
    client._factory = lambda *args: failing
    with pytest.raises(TransientModelError):
        client.embed(["a"])
    (trace,) = seen
    assert trace.error is not None and trace.error.startswith("Busy")
    assert trace.texts == 1
    assert isinstance(trace.latency_ms, int) and trace.latency_ms >= 0


def test_a_failing_hook_does_not_break_the_embed_call() -> None:
    def broken(trace: Any) -> None:
        raise RuntimeError("tracer down")

    seen: list[Any] = []
    reply = _client(FakeCall(), tracers=[broken, seen.append]).embed(["a"])
    assert reply.vectors == [[1.0, 1.0]]
    assert len(seen) == 1


def test_from_settings_passes_the_tracers_on(monkeypatch: pytest.MonkeyPatch) -> None:
    from mkc.config import Settings
    from mkc.models.client import EmbeddingClient
    from mkc.rag.embeddings import EMBEDDING

    monkeypatch.setenv("MKC_OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("MKC_MODEL_MODE", "live")
    hook = [].append
    client = EmbeddingClient.from_settings(
        Settings(), provider=EMBEDDING.provider, model=EMBEDDING.model, dim=EMBEDDING.dim,
        tracers=[hook],
    )  # fmt: skip
    assert client._tracers == [hook]


# --- the query side of the corpus embedder ------------------------------------------------


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.sent: list[list[str]] = []

    def embed(self, texts: Sequence[str], **kwargs: Any) -> Any:
        from mkc.models.client import EmbeddingReply

        self.sent.append(list(texts))
        return EmbeddingReply(
            vectors=[[0.5, 0.5] for _ in texts],
            model_id="openrouter:q/embed",
            input_tokens=9,
            cost_eur=0.000001,
            latency_ms=3,
        )


def test_a_query_is_embedded_with_the_query_instruction() -> None:
    """Qwen3-Embedding wants an instruction on queries and none on documents (decision 71);
    the instruction lives in the embedder, so `retrieve` hands over the raw query."""
    from mkc.rag.embeddings import ProviderEmbedder

    client = FakeEmbeddingClient()
    embedder = ProviderEmbedder(client, dim=2)  # type: ignore[arg-type]
    assert embedder.embed_query("Wann gilt § 14a?") == [0.5, 0.5]
    ((sent,),) = client.sent
    assert sent.startswith("Instruct: ")
    assert "\nQuery:" in sent
    assert sent.endswith("Wann gilt § 14a?")
    assert (embedder.input_tokens, embedder.cost_eur) == (9, pytest.approx(0.000001))


def test_passages_are_still_embedded_as_stored() -> None:
    from mkc.rag.embeddings import ProviderEmbedder

    client = FakeEmbeddingClient()
    ProviderEmbedder(client, dim=2).embed(["§ 14a Netzorientierte Steuerung"])  # type: ignore[arg-type]
    assert client.sent == [["§ 14a Netzorientierte Steuerung"]]


# --- MKC-50 mutation pass (test agent) -----------------------------------------------------


def test_the_trace_measures_the_call_on_success_and_on_error() -> None:
    import time

    class SlowCall(FakeCall):
        def __call__(self, texts: Sequence[str]) -> tuple[list[list[float]], int]:
            time.sleep(0.07)
            return super().__call__(texts)

    def failing(texts: Sequence[str]) -> tuple[list[list[float]], int]:
        time.sleep(0.07)
        raise RuntimeError("busy")

    seen: list[Any] = []
    _client(SlowCall(), tracers=[seen.append]).embed(["a"])
    client = _client(FakeCall(), tracers=[seen.append])
    client._factory = lambda *args: failing
    with pytest.raises(RuntimeError):
        client.embed(["a"])
    ok, failed = seen
    assert ok.latency_ms >= 50 and ok.error is None
    assert failed.latency_ms >= 50 and failed.error is not None


def test_the_query_text_is_qwen3s_format_exactly() -> None:
    """The model card's format: `Instruct: <task>`, a newline, `Query:` and the query, with no
    space after the colon (decision 71)."""
    from mkc.rag.embeddings import QUERY_INSTRUCTION, query_text

    assert QUERY_INSTRUCTION.strip()
    assert (
        query_text("Wann gilt § 14a?") == f"Instruct: {QUERY_INSTRUCTION}\nQuery:Wann gilt § 14a?"
    )
