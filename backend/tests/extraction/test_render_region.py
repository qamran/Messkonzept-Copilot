"""MKC-23: `render_region(page, bbox, dpi) -> ImageRef` as an item tool (design 8.1, 8.3).

Pinned (assumptions for the coordinator):

- `default_registry(documents=DocumentOps(sessions, store))` makes `render_region` real, as
  it does `extract_text`. The PDF comes from the store by the item's document hash.
- The result is `{"image_ref": <ref>, ...}`: the rendered image is put into the same blob
  store (`documents.store`) and `image_ref` is its ref, which `read_diagram(image_ref)`
  (MKC-26) takes. Pillow can open it; its pixel size is the bbox size in points times
  `dpi / 72` (within one pixel).
- The DPI cap is the setting `render_max_dpi` (`MKC_RENDER_MAX_DPI`), read when the
  `DocumentOps` is built or at the call.
- A bbox off the page or a page past the end is refused (`ok` false) and nothing is stored;
  argument shapes (MKC-14 finding 10: `page=True`, `page=1.0`, NaN or inf in the bbox, DPI
  not positive) are `invalid_args`.
- Cached by the tool cache on (document hash, page, bbox, dpi): the second identical call
  is a hit, reads no PDF and stores no image.
"""

import hashlib
import io
import uuid
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mkc.harness.cache import ToolCache
from mkc.harness.tools import ToolEnv, ToolTrace
from mkc.models.types import ToolCall
from tests.extraction.conftest import A4, Box, MemoryStore, Text, layout_pdf

BBOX = [72.0, 72.0, 144.0, 216.0]  # 72 x 144 pt: 100 x 200 px at 100 dpi


def _pdf() -> bytes:
    page = [Text(80, 80, "Z1 Zweirichtungszaehler"), Box(72, 72, 144, 216)]
    return layout_pdf([page, [Text(80, 80, "Seite 2")]], A4)


def _setup(
    sessions: sessionmaker[Session], store: MemoryStore
) -> tuple[Any, ToolEnv, list[ToolTrace]]:
    from mkc.extraction.operations import DocumentOps
    from mkc.harness.registry import default_registry

    pdf = _pdf()
    store.put(pdf)
    traces: list[ToolTrace] = []
    registry = default_registry((traces.append,), documents=DocumentOps(sessions, store))
    env = ToolEnv(1, 2, hashlib.sha256(pdf).hexdigest(), "3.2")
    return registry, env, traces


def _render(**args: Any) -> ToolCall:
    return ToolCall(id="r", name="render_region", args=args)


def test_render_region_returns_an_image_of_the_region(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store)
    result = registry.execute(_render(page=1, bbox=BBOX, dpi=100), "item", env)
    assert result.ok, result.error
    ref = result.data["image_ref"]
    assert ref in store.data, "the image is in the document store"
    width, height = Image.open(io.BytesIO(store.data[ref])).size
    assert abs(width - 100) <= 1 and abs(height - 200) <= 1


def test_render_region_is_deterministic(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store)
    first = registry.execute(_render(page=2, bbox=BBOX, dpi=72), "item", env)
    second = registry.execute(_render(page=2, bbox=BBOX, dpi=72), "item", env)
    assert first.ok and second.ok
    assert first.data["image_ref"] == second.data["image_ref"]


@pytest.mark.parametrize(
    "bbox",
    [
        [0.0, 0.0, 700.0, 100.0],  # past the right edge (A4 is 595 pt wide)
        [0.0, 800.0, 100.0, 900.0],  # past the bottom (842 pt high)
        [-10.0, 0.0, 100.0, 100.0],  # left of the page
        [600.0, 0.0, 650.0, 100.0],  # wholly off the page
    ],
)
def test_bbox_outside_page_rejected(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore, bbox: list[float]
) -> None:
    registry, env, _ = _setup(sessions, store)
    puts = store.puts
    result = registry.execute(_render(page=1, bbox=bbox, dpi=100), "item", env)
    assert not result.ok
    assert result.error is not None and result.error.code != "not_implemented"
    assert store.puts == puts, "nothing was rendered into the store"


def test_a_page_past_the_end_is_rejected(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store)
    puts = store.puts
    result = registry.execute(_render(page=3, bbox=BBOX, dpi=100), "item", env)
    assert not result.ok
    assert result.error is not None and result.error.code != "not_implemented"
    assert store.puts == puts


def test_the_dpi_cap_is_a_setting() -> None:
    from mkc.config import Settings

    cap = Settings().render_max_dpi
    assert isinstance(cap, int) and 150 <= cap <= 600


def test_dpi_above_cap_rejected(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.config import Settings

    cap = Settings().render_max_dpi
    registry, env, _ = _setup(sessions, store)
    small = [72.0, 72.0, 80.0, 80.0]
    puts = store.puts
    over = registry.execute(_render(page=1, bbox=small, dpi=cap + 1), "item", env)
    assert not over.ok and over.error is not None
    assert over.error.code != "not_implemented"
    assert store.puts == puts
    assert registry.execute(_render(page=1, bbox=small, dpi=cap), "item", env).ok


def test_the_dpi_cap_comes_from_the_environment(
    engine: Engine,
    sessions: sessionmaker[Session],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MKC_RENDER_MAX_DPI", "120")
    registry, env, _ = _setup(sessions, store)
    assert not registry.execute(_render(page=1, bbox=BBOX, dpi=121), "item", env).ok
    assert registry.execute(_render(page=1, bbox=BBOX, dpi=120), "item", env).ok


@pytest.mark.parametrize(
    "args",
    [
        {"page": True, "bbox": BBOX, "dpi": 100},
        {"page": 1.0, "bbox": BBOX, "dpi": 100},
        {"page": 1, "bbox": [72.0, float("nan"), 144.0, 216.0], "dpi": 100},
        {"page": 1, "bbox": [72.0, 72.0, float("inf"), 216.0], "dpi": 100},
        {"page": 1, "bbox": BBOX, "dpi": 0},
        {"page": 1, "bbox": BBOX, "dpi": -72},
        {"page": 1, "bbox": BBOX, "dpi": True},
        {"page": 1, "bbox": [144.0, 72.0, 72.0, 216.0], "dpi": 100},  # x0 > x1
    ],
)
def test_bad_argument_shapes_are_invalid_args(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore, args: dict[str, Any]
) -> None:
    registry, env, _ = _setup(sessions, store)
    result = registry.execute(_render(**args), "item", env)
    assert result.error is not None and result.error.code == "invalid_args", result


def test_render_cache_hit(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, traces = _setup(sessions, store)
    cache = ToolCache(sessions, f"test-{uuid.uuid4()}")
    first = registry.execute(_render(page=1, bbox=BBOX, dpi=100), "item", env, cache)
    assert first.ok, first.error
    gets, puts = store.gets, store.puts
    second = registry.execute(_render(page=1, bbox=BBOX, dpi=100), "item", env, cache)
    assert second.ok and second.data == first.data
    assert [t.cached for t in traces] == [False, True]
    assert (store.gets, store.puts) == (gets, puts), "a hit neither reads the PDF nor renders"
    other = registry.execute(_render(page=1, bbox=BBOX, dpi=101), "item", env, cache)
    assert other.ok and traces[-1].cached is False, "another dpi is another key"
