"""MKC-20.1: baseline differs from full only by the documented switches (decision 60)."""

from dataclasses import asdict, fields

import pytest

from mkc.config import Settings
from mkc.harness.limits import Limits
from mkc.harness.loop import ROLE, SYSTEM_PROMPT
from mkc.harness.mode import DOCUMENTED_SWITCHES, SWITCHES, HarnessMode, Switches
from mkc.harness.prompts import REPROMPT
from mkc.harness.registry import default_registry

FULL, BASELINE = HarnessMode.FULL, HarnessMode.BASELINE


def test_switches_are_the_documented_five() -> None:
    assert DOCUMENTED_SWITCHES == (
        "checkpoints",
        "tool_cache",
        "durable_queue",
        "idempotency",
        "durable_approvals",
    )
    assert tuple(f.name for f in fields(Switches)) == DOCUMENTED_SWITCHES


def test_full_all_on_baseline_all_off() -> None:
    assert set(SWITCHES) == {FULL, BASELINE}
    assert set(asdict(SWITCHES[FULL]).values()) == {True}
    assert set(asdict(SWITCHES[BASELINE]).values()) == {False}


def test_checkpoints_need_durable_queue() -> None:
    with pytest.raises(ValueError, match="durable_queue"):
        Switches(True, True, False, True, True)


def _settings(mode: str) -> Settings:
    return Settings(_env_file=None, harness_mode=mode)  # type: ignore[call-arg]


def test_settings_differ_only_by_mode() -> None:
    full, baseline = _settings("full").model_dump(), _settings("baseline").model_dump()
    assert full["harness_mode"] == FULL
    assert baseline["harness_mode"] == BASELINE
    assert {k for k in full if full[k] != baseline[k]} == {"harness_mode"}


def test_default_mode_is_full() -> None:
    assert Settings(_env_file=None).harness_mode == FULL  # type: ignore[call-arg]


def test_modes_share_everything_else() -> None:
    """Limits (with the one re-prompt), tools, prompts and the role come from the settings
    and code that both modes share; nothing in them depends on the mode."""
    full, baseline = _settings("full"), _settings("baseline")
    assert Limits.from_settings(full) == Limits.from_settings(baseline)
    assert Limits.from_settings(baseline).max_reprompts == 1
    specs = [t.to_spec() for t in default_registry().for_context("item")]
    assert [s.name for s in specs] == [
        "extract_text", "extract_tables", "render_region",
        "read_diagram", "validate_draft", "save_draft",
    ]  # fmt: skip
    assert SYSTEM_PROMPT and REPROMPT and ROLE == "extract_vision"
