"""MKC-23 mutation pass: `render_region` rules the acceptance tests left open.

- Every refusal (page past the end, bbox off the page, DPI over the cap) is `invalid_args`,
  as `DocumentOps.render_region` documents (survivors V1, O3, O5).
- A bbox above the page top is off the page (V2); a boolean coordinate is `invalid_args` (G1).
- The image is the region asked for, not another strip of the page (V6); it is a PNG (V8);
  the result's `width` and `height` are the image's (O4).
- `DocumentOps(render_max_dpi=...)` is the cap when given (O2).
"""

import io
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mkc.harness.tools import ToolEnv
from mkc.models.types import ToolCall
from tests.extraction.conftest import A4, Box, MemoryStore, Text, layout_pdf
from tests.extraction.test_render_region import BBOX, _setup

INSIDE = Box(90, 100, 126, 190)  # a ruled box well inside BBOX (72, 72, 144, 216)


def _render(registry: Any, env: ToolEnv, **args: Any) -> Any:
    return registry.execute(ToolCall(id="r", name="render_region", args=args), "item", env)


@pytest.mark.parametrize(
    ("page", "bbox", "dpi"),
    [
        (3, BBOX, 100),  # past the end
        (1, [0.0, 0.0, 700.0, 100.0], 100),  # off the right edge
        (1, [72.0, -10.0, 144.0, 100.0], 100),  # above the top
        (1, BBOX, 10_000),  # over any cap
    ],
)
def test_every_refusal_is_invalid_args(
    engine: Engine,
    sessions: sessionmaker[Session],
    store: MemoryStore,
    page: int,
    bbox: list[float],
    dpi: int,
) -> None:
    registry, env, _ = _setup(sessions, store)
    puts = store.puts
    result = _render(registry, env, page=page, bbox=bbox, dpi=dpi)
    assert result.error is not None and result.error.code == "invalid_args", result
    assert store.puts == puts


def test_a_boolean_coordinate_is_invalid_args(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store)
    result = _render(registry, env, page=1, bbox=[True, 72.0, 144.0, 216.0], dpi=100)
    assert result.error is not None and result.error.code == "invalid_args"


def test_the_image_shows_the_region_and_is_a_png(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.operations import DocumentOps
    from mkc.harness.registry import default_registry

    pdf = layout_pdf([[INSIDE]], A4)
    ref = store.put(pdf)
    registry = default_registry(documents=DocumentOps(sessions, store))
    env = ToolEnv(1, 2, ref.removeprefix("blob:sha256:"), "3.2")
    shown = _render(registry, env, page=1, bbox=BBOX, dpi=72)
    assert shown.ok, shown.error
    png = store.data[shown.data["image_ref"]]
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(io.BytesIO(png)).convert("L")
    assert (shown.data["width"], shown.data["height"]) == image.size
    assert min(image.getdata()) < 128, "the box's rules are in the region"
    blank = _render(registry, env, page=1, bbox=[72.0, 626.0, 144.0, 770.0], dpi=72)
    assert min(Image.open(io.BytesIO(store.data[blank.data["image_ref"]])).convert("L")
               .getdata()) > 200, "the mirrored strip is empty"  # fmt: skip


def test_render_max_dpi_given_to_document_ops_is_the_cap(
    engine: Engine, sessions: sessionmaker[Session]
) -> None:
    from mkc.extraction.operations import DocumentOps
    from mkc.harness.registry import default_registry

    store = MemoryStore()
    ref = store.put(layout_pdf([[Text(80, 80, "Z1")]], A4))
    registry = default_registry(documents=DocumentOps(sessions, store, render_max_dpi=100))
    env = ToolEnv(1, 2, ref.removeprefix("blob:sha256:"), "3.2")
    over = _render(registry, env, page=1, bbox=BBOX, dpi=101)
    assert over.error is not None and over.error.code == "invalid_args"
    assert _render(registry, env, page=1, bbox=BBOX, dpi=100).ok
