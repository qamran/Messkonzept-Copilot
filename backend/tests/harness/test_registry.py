"""The default registry (MKC-14.2): exactly the allow-lists of design section 8.1."""

from typing import Any

import pytest

from mkc.harness.registry import ITEM_TOOLS, RUN_OPERATIONS, default_registry
from mkc.harness.tools import ToolEnv
from mkc.models.types import ToolCall

ITEM = {
    "extract_text",
    "extract_tables",
    "render_region",
    "read_diagram",
    "validate_draft",
    "save_draft",
}
RUN = {"fetch_document", "segment_document", "enqueue_approval", "commit_record"}
ENV = ToolEnv(run_id=1, item_id=2, document_hash="h", concept_key="MK-1")

VALID_ARGS: dict[str, dict[str, Any]] = {
    "extract_text": {"page": 1},
    "extract_tables": {"kind": "lbs"},
    "render_region": {"page": 1, "bbox": [0, 0, 100, 100], "dpi": 150},
    "read_diagram": {"image_ref": "img-1"},
    "validate_draft": {"draft": {}},
    "save_draft": {"draft": {}},
    "fetch_document": {"operator_id": "stromnetz-berlin"},
    "segment_document": {"document_hash": "abc"},
    "enqueue_approval": {"draft_id": "d-1"},
    "commit_record": {"draft_id": "d-1"},
}


def test_item_context_exposes_exactly_the_six_tools() -> None:
    names = [t.name for t in default_registry().for_context("item")]
    assert len(names) == 6
    assert set(names) == ITEM
    assert {t.name for t in ITEM_TOOLS} == ITEM


def test_item_context_exposes_no_side_effect_tools() -> None:
    assert not [t.name for t in default_registry().for_context("item") if t.side_effect]


def test_run_context_holds_the_four_run_level_operations() -> None:
    names = {t.name for t in default_registry().for_context("run")}
    assert names == RUN
    assert {t.name for t in RUN_OPERATIONS} == RUN


def test_side_effect_flags() -> None:
    run = {t.name: t.side_effect for t in default_registry().for_context("run")}
    assert run == {
        "fetch_document": True,
        "segment_document": False,
        "enqueue_approval": True,
        "commit_record": True,
    }


def test_run_level_operations_are_refused_in_item_context() -> None:
    registry = default_registry()
    for op in sorted(RUN):
        result = registry.execute(ToolCall(id="c", name=op, args=VALID_ARGS[op]), "item", ENV)
        assert result.error is not None
        assert result.error.code == "tool_not_allowed"


@pytest.mark.parametrize("name", sorted(ITEM | RUN))
def test_placeholders_return_not_implemented(name: str) -> None:
    ctx = "item" if name in ITEM else "run"
    result = default_registry().execute(
        ToolCall(id="c", name=name, args=VALID_ARGS[name]), ctx, ENV
    )
    assert result.error is not None
    assert result.error.code == "not_implemented"


def test_every_tool_has_a_description() -> None:
    registry = default_registry()
    for tool in (*registry.for_context("item"), *registry.for_context("run")):
        assert tool.description.strip()
