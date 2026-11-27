"""The item loop (MKC-15, design 8.1 to 8.3): inside one item, the model drives tools until a
draft is saved or the item fails. `process_run` runs the queue."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from mkc.harness.states import ItemState
from mkc.harness.tools import ToolRegistry
from mkc.models.client import ModelClient

TOOL_RESULT_CLOSE = "</tool_result>"


@dataclass(frozen=True)
class ItemOutcome:
    item_id: int
    state: ItemState
    reason: str | None
    steps: int
    cost_eur: Decimal


def run_item(
    item_id: int, *, session: Session, client: ModelClient, registry: ToolRegistry, max_steps: int
) -> ItemOutcome:
    raise NotImplementedError


def process_run(
    run_id: int, *, session: Session, client: ModelClient, registry: ToolRegistry, max_steps: int
) -> list[ItemOutcome]:
    raise NotImplementedError
