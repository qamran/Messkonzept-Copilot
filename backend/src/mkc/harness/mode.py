"""Harness mode: `full` or `baseline` (MKC-20, design 8.5, decision 60).

Baseline is the same loop, tools, prompts, limits, retries and tracing with five switches
off. Nothing else may depend on the mode; `tests/harness/test_mode.py` checks that.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class HarnessMode(StrEnum):
    FULL = "full"
    BASELINE = "baseline"


DOCUMENTED_SWITCHES: tuple[str, ...] = (
    "checkpoints",
    "tool_cache",
    "durable_queue",
    "idempotency",
    "durable_approvals",
)
"""The switches of design 8.5, in its order."""


@dataclass(frozen=True)
class Switches:
    """What baseline switches off.

    - `checkpoints`: a `turn` row per turn and resume from the last complete turn
    - `tool_cache`: the `tool_cache` table
    - `durable_queue`: claims and item end states written as they happen; off, they stay in
      memory and are written once, when the run ends
    - `idempotency`: `save_draft` keyed by (document hash, concept key)
    - `durable_approvals`: drafts in the `draft` table; off, in memory only
    """

    checkpoints: bool
    tool_cache: bool
    durable_queue: bool
    idempotency: bool
    durable_approvals: bool

    def __post_init__(self) -> None:
        if self.checkpoints and not self.durable_queue:
            raise ValueError("checkpoints need durable_queue: turn rows need durable claims")


SWITCHES: Mapping[HarnessMode, Switches] = MappingProxyType(
    {
        HarnessMode.FULL: Switches(True, True, True, True, True),
        HarnessMode.BASELINE: Switches(False, False, False, False, False),
    }
)
