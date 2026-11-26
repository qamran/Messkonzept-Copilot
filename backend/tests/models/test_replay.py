"""MKC-13.4: record/replay. Replay returns recorded replies and never builds a provider."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from mkc.models.client import CallTrace, ModelClient
from mkc.models.replay import ReplayStore, replay_key
from mkc.models.types import Image, Message, ModelConfigError, ModelReply, ReplayMiss, Usage
from tests.models.fakes import ai, fake
from tests.models.test_client import LOOKUP, USER, Built, Verdict, config


class Other(BaseModel):
    note: str


def key(**change: object) -> str:
    parts: dict[str, object] = {
        "role": "facts",
        "model_id": "openrouter:a/cheap",
        "method": "chat",
        "messages": USER,
        "tools": [],
        "schema": None,
    }
    parts.update(change)
    return replay_key(**parts)  # type: ignore[arg-type]


# --- key ------------------------------------------------------------------------------


def test_key_is_a_stable_sha256() -> None:
    assert key() == key()
    assert len(key()) == 64
    assert int(key(), 16) >= 0


@pytest.mark.parametrize(
    "change",
    [
        {"role": "judge"},
        {"model_id": "openrouter:b/other"},
        {"method": "chat_with_tools"},
        {"messages": [Message(role="user", content="Hi!")]},
        {"messages": [Message(role="system", content="Be brief.")]},
        {"tools": [LOOKUP]},
        {"schema": Verdict},
    ],
)
def test_key_changes_with_each_part(change: dict[str, object]) -> None:
    assert key(**change) != key()


def test_key_changes_with_image_bytes_and_schema() -> None:
    def with_image(data: bytes) -> list[Message]:
        image = Image(media_type="image/png", data=data)
        return [Message(role="user", content="Hi", images=(image,))]

    assert key(messages=with_image(b"a")) != key(messages=with_image(b"b"))
    assert key(schema=Verdict) != key(schema=Other)


# --- store ----------------------------------------------------------------------------

REPLY = ModelReply(
    text="Hello",
    usage=Usage(input_tokens=10, output_tokens=2, cost_eur=0.001),
    model_id="openrouter:a/cheap",
    latency_ms=321,
)


def test_store_round_trip(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    store.put("ab" * 32, REPLY)
    assert store.get("ab" * 32) == REPLY


def test_store_miss_raises(tmp_path: Path) -> None:
    with pytest.raises(ReplayMiss, match="cd" * 32):
        ReplayStore(tmp_path).get("cd" * 32)


@pytest.mark.parametrize("bad", ["../x", "AB" * 32, "ab" * 31, "zz" * 32])
def test_store_refuses_keys_that_are_not_sha256(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        ReplayStore(tmp_path).get(bad)


# --- client modes ---------------------------------------------------------------------


def _client(mode: str, tmp_path: Path, model_reply: object = None) -> tuple[ModelClient, Built]:
    factory = Built(fake(ai("recorded", input_tokens=50, output_tokens=5)))
    store = ReplayStore(tmp_path)
    return ModelClient(config(), factory, mode=mode, store=store), factory  # type: ignore[arg-type]


def test_record_then_replay_returns_the_recorded_reply(tmp_path: Path) -> None:
    recorder, _ = _client("record", tmp_path)
    recorded = recorder.chat("facts", USER)
    replayer, factory = _client("replay", tmp_path)
    assert replayer.chat("facts", USER) == recorded
    assert factory.calls == []  # replay never builds a provider client


def test_record_and_replay_cover_tools_vision_and_structured(tmp_path: Path) -> None:
    call = {"id": "s1", "name": "Verdict", "args": {"code": "9", "confident": False}}
    factory = Built(fake(ai("", tool_calls=[call])))
    recorder = ModelClient(config(), factory, mode="record", store=ReplayStore(tmp_path))
    page = Image(media_type="image/png", data=b"page")
    recorded = [
        recorder.chat_structured("facts", USER, Verdict),
        recorder.chat_with_tools("facts", USER, [LOOKUP]),
        recorder.vision("extract_vision", USER, [page]),
    ]
    replayer = ModelClient(config(), Built(fake()), mode="replay", store=ReplayStore(tmp_path))
    assert replayer.chat_structured("facts", USER, Verdict) == recorded[0]
    assert replayer.chat_with_tools("facts", USER, [LOOKUP]) == recorded[1]
    assert replayer.vision("extract_vision", USER, [page]) == recorded[2]
    assert recorded[0].parsed == {"code": "9", "confident": False}


def test_replay_miss_raises_and_builds_nothing(tmp_path: Path) -> None:
    replayer, factory = _client("replay", tmp_path)
    with pytest.raises(ReplayMiss):
        replayer.chat("facts", USER)
    assert factory.calls == []


def test_replay_is_traced_as_replay(tmp_path: Path) -> None:
    _client("record", tmp_path)[0].chat("facts", USER)
    traces: list[CallTrace] = []
    replayer = ModelClient(
        config(), Built(fake()), mode="replay", store=ReplayStore(tmp_path), tracers=[traces.append]
    )
    replayer.chat("facts", USER)
    (trace,) = traces
    assert (trace.mode, trace.error, trace.model_id) == ("replay", None, "openrouter:a/cheap")


def test_stored_files_hold_no_request_text_or_images(tmp_path: Path) -> None:
    secret = "Sehr geehrte Damen und Herren, Zählpunkt DE000111"
    recorder, _ = _client("record", tmp_path)
    page = Image(media_type="image/png", data=b"IMAGE-BYTES-123")
    recorder.vision("extract_vision", [Message(role="user", content=secret)], [page])
    (stored,) = list(tmp_path.iterdir())
    text = stored.read_text(encoding="utf-8")
    assert secret not in text
    assert "IMAGE-BYTES-123" not in text
    assert "SU1BR0UtQllURVMtMTIz" not in text  # the image's base64
    assert json.loads(text)["text"] == "recorded"


@pytest.mark.parametrize("mode", ["record", "replay"])
def test_record_and_replay_need_a_store(mode: str) -> None:
    with pytest.raises(ModelConfigError, match="MKC_MODEL_REPLAY_DIR"):
        ModelClient(config(), Built(fake()), mode=mode)  # type: ignore[arg-type]
