"""Harness mode: `full` or `baseline` (MKC-20, design 8.5, decision 60)."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class HarnessMode(StrEnum):
    FULL = "full"
    BASELINE = "baseline"


DOCUMENTED_SWITCHES: tuple[str, ...] = ()


@dataclass(frozen=True)
class Switches:
    checkpoints: bool
    tool_cache: bool
    durable_queue: bool
    idempotency: bool
    durable_approvals: bool


SWITCHES: Mapping[HarnessMode, Switches] = {}
