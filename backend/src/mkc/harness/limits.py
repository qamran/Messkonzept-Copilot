"""Limits and stop reasons (MKC-18, design 8.5, decision 58)."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from mkc.config import Settings

Scope = Literal["run", "item"]


class StopReason(StrEnum):
    STEP_LIMIT = "step_limit"
    TOOL_RETRIES = "tool_retries"
    MALFORMED_OUTPUT = "malformed_output"
    RESUME_LIMIT = "resume_limit"
    MODEL_ERROR = "model_error"
    TOOL_ERROR = "tool_error"
    RUN_STEP_LIMIT = "run_step_limit"
    WALL_TIME = "wall_time"
    COST_LIMIT = "cost_limit"
    SETUP_ERROR = "setup_error"
    MODEL_UNAVAILABLE = "model_unavailable"

    @property
    def scope(self) -> Scope:
        raise NotImplementedError


@dataclass(frozen=True)
class Limits:
    max_steps_item: int = 12
    max_steps_run: int = 300
    max_wall_s: float = 7200.0
    max_cost_eur: Decimal = Decimal("3.00")
    max_retries_tool: int = 3
    max_retries_model: int = 4
    max_reprompts: int = 1
    max_resumes_item: int = 3
    backoff_base_s: float = 2.0
    backoff_max_s: float = 60.0
    turn_timeout_s: float = 180.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "Limits":
        raise NotImplementedError


@dataclass(frozen=True)
class RunUsage:
    steps: int
    cost_eur: Decimal
    wall_s: float


def run_limit_hit(usage: RunUsage, limits: Limits) -> StopReason | None:
    raise NotImplementedError
