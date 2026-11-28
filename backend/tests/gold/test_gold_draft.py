"""MKC-24: gold drafts come from the `gold_draft` role, never the extraction model (design
11.1, decision 29), lane A2.

Pinned interface (module `mkc.gold.draft`):

    ensure_independent(config: ModelsConfig) -> None
        # ModelConfigError when `gold_draft` maps to the same provider and model as
        # `extract_vision`
    draft_concept(client: ModelClient, config: ModelsConfig, *, key: str, text: str,
                  images: Sequence[Image] = ()) -> GoldDraft
        # checks independence before any model call; one or more calls, all with the
        # `gold_draft` role, through `ModelClient` (never a provider SDK)
    GoldDraft.key: str
    GoldDraft.payload: dict   # validates as `MesskonzeptDraft` (mkc.extraction.draft)
    GoldDraft.drafted_by: str # `ModelReply.model_id` of the reply, "provider:model"

The model is a fake LangChain chat model behind a real `ModelClient`, built by a factory that
records which provider and model it was asked for. The fake's reply carries the payload both
as JSON text and as a `MesskonzeptDraft` tool call, so `chat`, `vision` and `chat_structured`
all read it; the test does not pin the client method.
"""

import json
from collections.abc import Callable
from typing import Any

import pytest

from mkc.extraction.draft import MesskonzeptDraft
from mkc.models.client import CallTrace, ModelClient
from mkc.models.config import ModelsConfig, load_models_config
from mkc.models.types import ROLES, ModelConfigError, ModelError
from tests.gold.conftest import draft_payload
from tests.models.fakes import FakeChatModel, ai

GOLD_MODEL = "openrouter:anthropic/claude-haiku-5.5"
"""The `gold_draft` role in `models.yaml` (extraction: google/gemini-3.8-flash)."""

TEXT = "4.1 Ueberschusseinspeisung. Z1 Zweirichtungszaehler. LBS 9907654321098."


def reply(payload: dict[str, Any]) -> Any:
    call = {"id": "g1", "name": "MesskonzeptDraft", "args": payload}
    return ai(json.dumps(payload), tool_calls=[call], input_tokens=900, output_tokens=400)


class Recorder:
    """A `ModelClient` factory and tracer that remember what was built and called."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.model = FakeChatModel(responses=[reply(payload)] * 4)
        self.built: list[tuple[str, str]] = []
        self.traces: list[CallTrace] = []

    def factory(self, provider: str, model: str, timeout: float) -> FakeChatModel:
        self.built.append((provider, model))
        return self.model

    def client(self, config: ModelsConfig) -> ModelClient:
        return ModelClient(config, self.factory, mode="live", tracers=[self.traces.append])  # type: ignore[arg-type]


def custom_config(gold: str, extract: str = "x/extract") -> ModelsConfig:
    roles: dict[str, Any] = {r: {"provider": "openrouter", "model": extract} for r in ROLES}
    roles["gold_draft"] = {"provider": "openrouter", "model": gold}
    models = {extract, gold}
    return ModelsConfig.model_validate(
        {
            "eur_per_usd": 1.0,
            "timeout_seconds": 90,
            "roles": roles,
            "contract_models": {
                "openrouter": extract,
                "gemini": "g",
                "anthropic": "c",
                "meta": "m",
            },
            "prices": {
                "openrouter": {m: {"input": 1.0, "output": 1.0} for m in models},
                "gemini": {"g": {"input": 0, "output": 0}},
                "anthropic": {"c": {"input": 0, "output": 0}},
                "meta": {"m": {"input": 0, "output": 0}},
            },
        }
    )


def _draft_concept() -> Callable[..., Any]:
    from mkc.gold.draft import draft_concept

    return draft_concept


def test_gold_draft_uses_gold_draft_role_model_not_extraction_model() -> None:
    config = load_models_config()  # the repo's models.yaml
    recorder = Recorder(draft_payload())
    draft = _draft_concept()(recorder.client(config), config, key="stromnetz-berlin:4.1", text=TEXT)
    assert recorder.traces, "no model call went through ModelClient"
    assert {t.role for t in recorder.traces} == {"gold_draft"}
    assert {t.model_id for t in recorder.traces} == {GOLD_MODEL}
    assert set(recorder.built) == {("openrouter", "anthropic/claude-haiku-5.5")}
    assert ("openrouter", "google/gemini-3.8-flash") not in recorder.built
    assert draft.drafted_by == GOLD_MODEL
    assert draft.key == "stromnetz-berlin:4.1"
    assert MesskonzeptDraft.model_validate(draft.payload).model_dump(mode="json") == (
        MesskonzeptDraft.model_validate(draft_payload()).model_dump(mode="json")
    )


def test_drafted_by_follows_the_configured_gold_model() -> None:
    config = custom_config(gold="y/gold")
    recorder = Recorder(draft_payload())
    draft = _draft_concept()(recorder.client(config), config, key="sachsennetze:2-1", text=TEXT)
    assert draft.drafted_by == "openrouter:y/gold"
    assert set(recorder.built) == {("openrouter", "y/gold")}


def test_the_repo_models_file_is_independent() -> None:
    from mkc.gold.draft import ensure_independent

    ensure_independent(load_models_config())  # no error


def test_gold_draft_on_the_extraction_model_is_refused() -> None:
    from mkc.gold.draft import ensure_independent

    with pytest.raises(ModelConfigError):
        ensure_independent(custom_config(gold="x/extract", extract="x/extract"))


def test_a_refused_config_makes_no_model_call() -> None:
    config = custom_config(gold="x/extract", extract="x/extract")
    recorder = Recorder(draft_payload())
    with pytest.raises(ModelConfigError):
        _draft_concept()(recorder.client(config), config, key="stromnetz-berlin:4.1", text=TEXT)
    assert recorder.built == []
    assert recorder.traces == []
    assert recorder.model.seen == []


def test_a_reply_that_is_not_a_messkonzept_draft_is_an_error() -> None:
    bad = draft_payload()
    del bad["meters"]
    config = custom_config(gold="y/gold")
    recorder = Recorder(bad)
    with pytest.raises((ModelError, ValueError)):
        _draft_concept()(recorder.client(config), config, key="stromnetz-berlin:4.1", text=TEXT)


def test_the_pdf_text_goes_in_a_user_message_not_the_system_prompt() -> None:
    config = custom_config(gold="y/gold")
    recorder = Recorder(draft_payload())
    _draft_concept()(recorder.client(config), config, key="stromnetz-berlin:4.1", text=TEXT)
    sent = recorder.model.seen[0]
    users = [str(m.content) for m in sent if m.type == "human"]
    others = [str(m.content) for m in sent if m.type != "human"]
    assert any(TEXT in u for u in users)
    assert not any(TEXT in o for o in others)
