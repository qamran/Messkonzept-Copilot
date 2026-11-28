"""MKC-22.3: the `extract_text` arguments the model sends are checked before the PDF is read.
A `bbox` must be four finite numbers with x0 < x1 and top < bottom; anything else is
`invalid_args`. A bbox partly off the page is clipped to it; one wholly off it is
`tool_failed`."""

from typing import Any

import pytest

from mkc.harness.tools import ToolEnv
from mkc.models.types import ToolCall
from tests.extraction.synthetic import concept_page_pdf

ENV = ToolEnv(run_id=1, item_id=2, document_hash="x", concept_key="4.4")


class OneDocument:
    """Stands in for `DocumentOps`' store: every hash gives the synthetic concept page."""

    def __init__(self) -> None:
        self.pdf = concept_page_pdf()

    def get(self, ref: str) -> bytes:
        return self.pdf

    def put(self, data: bytes) -> str:
        raise AssertionError("the item tools never write")


def _registry() -> Any:
    from mkc.extraction.operations import DocumentOps
    from mkc.harness.registry import default_registry

    return default_registry(documents=DocumentOps(None, OneDocument()))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bbox",
    [
        [float("nan"), 60, 455, 760],
        [60, 60, float("inf"), 760],
        [455, 60, 60, 760],  # x0 > x1
        [60, 760, 455, 60],  # top > bottom
        [60, 60, 60, 760],  # no width
        [60, 60, 455],
    ],
)
def test_a_bad_bbox_is_invalid_args(bbox: list[float]) -> None:
    call = ToolCall(id="c", name="extract_text", args={"page": 1, "bbox": bbox})
    result = _registry().execute(call, "item", ENV)
    assert result.error is not None and result.error.code == "invalid_args", result


def test_a_bbox_partly_off_the_page_is_clipped() -> None:
    call = ToolCall(id="c", name="extract_text", args={"page": 2, "bbox": [-50, -50, 455, 2000]})
    result = _registry().execute(call, "item", ENV)
    assert result.ok, result.error
    assert [s["code"] for s in result.data["stated_lbs"]] == ["9992000000133"]


def test_a_bbox_off_the_page_is_tool_failed() -> None:
    call = ToolCall(id="c", name="extract_text", args={"page": 1, "bbox": [700, 900, 800, 1000]})
    result = _registry().execute(call, "item", ENV)
    assert result.error is not None and result.error.code == "tool_failed"


def test_page_zero_is_invalid_args() -> None:
    # Mutation pass (test agent): `page` is 1-based, so 0 never reaches the tool.
    from mkc.harness.registry import default_registry
    from mkc.harness.tools import ToolEnv
    from mkc.models.types import ToolCall

    env = ToolEnv(run_id=1, item_id=2, document_hash="h", concept_key="1")
    call = ToolCall(id="c", name="extract_text", args={"page": 0})
    result = default_registry().execute(call, "item", env)
    assert result.error is not None and result.error.code == "invalid_args"
