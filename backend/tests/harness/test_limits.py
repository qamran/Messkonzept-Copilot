"""MKC-18.1: `Limits`, `StopReason` and the run-limit check (decision 58)."""

from decimal import Decimal

import pytest

from mkc.config import Settings
from mkc.harness.limits import Limits, RunUsage, StopReason, run_limit_hit


def test_limits_defaults_are_the_settings_defaults() -> None:
    assert Limits() == Limits.from_settings(Settings())


def test_limits_from_settings_maps_every_field() -> None:
    settings = Settings(
        item_max_steps=5,
        run_max_steps=50,
        run_max_wall_seconds=60,
        run_max_cost_eur=Decimal("0.5"),
        tool_max_retries=1,
        model_max_retries=2,
        model_backoff_base_seconds=1,
        model_backoff_max_seconds=4,
        turn_timeout_seconds=30,
        item_max_resumes=2,
    )
    assert Limits.from_settings(settings) == Limits(
        max_steps_item=5,
        max_steps_run=50,
        max_wall_s=60,
        max_cost_eur=Decimal("0.5"),
        max_retries_tool=1,
        max_retries_model=2,
        backoff_base_s=1,
        backoff_max_s=4,
        turn_timeout_s=30,
        max_resumes_item=2,
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"max_steps_item": 0},
        {"max_steps_run": 0},
        {"max_wall_s": 0},
        {"max_cost_eur": Decimal(0)},
        {"max_retries_tool": -1},
        {"max_retries_model": -1},
        {"max_reprompts": -1},
        {"max_resumes_item": -1},
        {"backoff_base_s": 0},
        {"backoff_base_s": 5, "backoff_max_s": 4},
        {"turn_timeout_s": 0},
    ],
)
def test_limits_refuse_bad_values(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Limits(**bad)  # type: ignore[arg-type]


LIMITS = Limits(max_steps_run=10, max_wall_s=60, max_cost_eur=Decimal("1.00"))
UNDER = RunUsage(steps=9, cost_eur=Decimal("0.99"), wall_s=59.9)


def test_no_run_limit_is_hit_below_every_limit() -> None:
    assert run_limit_hit(UNDER, LIMITS) is None


@pytest.mark.parametrize(
    ("usage", "reason"),
    [
        (RunUsage(10, Decimal("0.99"), 59.9), StopReason.RUN_STEP_LIMIT),
        (RunUsage(9, Decimal("1.00"), 59.9), StopReason.COST_LIMIT),
        (RunUsage(9, Decimal("0.99"), 60.0), StopReason.WALL_TIME),
    ],
)
def test_each_run_limit_has_its_own_reason(usage: RunUsage, reason: StopReason) -> None:
    assert run_limit_hit(usage, LIMITS) is reason


def test_stop_reasons_know_their_scope() -> None:
    run_level = {r for r in StopReason if r.scope == "run"}
    assert run_level == {
        StopReason.RUN_STEP_LIMIT,
        StopReason.WALL_TIME,
        StopReason.COST_LIMIT,
        StopReason.SETUP_ERROR,
        StopReason.MODEL_UNAVAILABLE,
    }
    assert {r.scope for r in StopReason} == {"run", "item"}
    assert StopReason.STEP_LIMIT.value == "step_limit"  # the MKC-15 reason is kept
