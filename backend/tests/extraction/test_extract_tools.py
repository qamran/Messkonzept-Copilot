"""MKC-22: `extract_text` and `extract_tables` as item tools (design 8.1): deterministic,
cached, and JSON all the way.

Pinned:

- `default_registry(documents=DocumentOps(sessions, store))` makes both item tools real, as
  it does `fetch_document` and `segment_document` (MKC-21). Without `documents` they stay
  placeholders (`test_placeholders_return_not_implemented` is unchanged).
- The model never names the document: a tool reads the PDF from `documents.store` at
  `blob:sha256:<env.document_hash>` (the item's document hash is the PDF's sha256).
- Arguments: `extract_text` takes `page` (>= 1) and an optional `bbox` (`[x0, top, x1,
  bottom]`, as in the item's task; omitted means the whole page), so `{"page": 1}` stays
  valid for the harness tests. `extract_tables` takes only `kind`.
- Results are plain JSON: `extract_text` gives `TextFields.model_dump(mode="json")`,
  `extract_tables` the list of `Row.model_dump(mode="json")`. A cache hit gives the same
  value, read back from JSONB.
- Cached: the second identical call is a hit (`ToolTrace.cached`), and the PDF is not read
  again (`MemoryStore.gets`).
- No NUL characters reach a result (the backlog's MKC-16 note: JSONB refuses `\\u0000`).
"""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mkc.harness.cache import ToolCache
from mkc.harness.tools import ToolEnv, ToolTrace
from mkc.models.types import ToolCall
from tests.extraction.conftest import MemoryStore, Text, layout_pdf
from tests.extraction.synthetic import (
    APPLICATIONS,
    CONCEPT_BBOX,
    FOOTNOTES,
    LBS_EXPECTED,
    STATED,
    TITLE,
    concept_page_pdf,
    lbs_table_pdf,
)


def _setup(
    sessions: sessionmaker[Session], store: MemoryStore, pdf: bytes
) -> tuple[Any, ToolEnv, list[ToolTrace]]:
    from mkc.extraction.operations import DocumentOps
    from mkc.harness.registry import default_registry

    store.put(pdf)
    traces: list[ToolTrace] = []
    registry = default_registry((traces.append,), documents=DocumentOps(sessions, store))
    env = ToolEnv(
        run_id=1, item_id=2, document_hash=hashlib.sha256(pdf).hexdigest(), concept_key="4.4"
    )
    return registry, env, traces


def _call(name: str, **args: Any) -> ToolCall:
    return ToolCall(id="c", name=name, args=args)


def test_extract_text_reads_the_items_document(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store, concept_page_pdf())
    result = registry.execute(_call("extract_text", page=1, bbox=list(CONCEPT_BBOX)), "item", env)
    assert result.ok, result.error
    assert result.data == {
        "title": TITLE,
        "applications": APPLICATIONS,
        "footnotes": FOOTNOTES,
        "stated_lbs": [{"code": c, "condition": k} for c, k in STATED],
    }


def test_extract_tables_reads_the_items_document(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store, lbs_table_pdf())
    result = registry.execute(_call("extract_tables", kind="lbs"), "item", env)
    assert result.ok, result.error
    assert isinstance(result.data, list)
    got = [(r["page"], r["concepts"], r["code"], r["label"]) for r in result.data]
    assert got == LBS_EXPECTED
    assert {r["kind"] for r in result.data} == {"lbs"}
    assert all(r["cells"] == [] for r in result.data)


def test_both_tools_are_cached(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, traces = _setup(sessions, store, concept_page_pdf())
    cache = ToolCache(sessions, f"test-{uuid.uuid4()}")
    calls = [
        _call("extract_text", page=1, bbox=list(CONCEPT_BBOX)),
        _call("extract_tables", kind="lbs"),
    ]
    first = [registry.execute(c, "item", env, cache) for c in calls]
    reads = store.gets
    second = [registry.execute(c, "item", env, cache) for c in calls]
    assert all(r.ok for r in first + second), [r.error for r in first + second]
    assert [t.cached for t in traces] == [False, False, True, True]
    assert store.gets == reads, "a cache hit does not read the PDF again"
    assert [r.data for r in second] == [r.data for r in first]


def test_both_tools_are_deterministic_item_tools(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store, concept_page_pdf())
    tools = {t.name: t for t in registry.for_context("item")}
    for name in ("extract_text", "extract_tables"):
        assert tools[name].deterministic and tools[name].cacheable
        assert not tools[name].side_effect
    call = _call("extract_text", page=2, bbox=list(CONCEPT_BBOX))
    first, again = registry.execute(call, "item", env), registry.execute(call, "item", env)
    assert first.ok, first.error
    assert again.data == first.data


def test_page_defaults_to_the_whole_page(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store, concept_page_pdf())
    result = registry.execute(_call("extract_text", page=2), "item", env)
    assert result.ok, result.error
    assert [s["code"] for s in result.data["stated_lbs"]] == ["9992000000133"]


def test_a_page_beyond_the_document_is_an_error(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    registry, env, _ = _setup(sessions, store, concept_page_pdf())
    result = registry.execute(_call("extract_text", page=3), "item", env)
    assert result.error is not None and result.error.code == "tool_failed"
    bad = registry.execute(_call("extract_tables", kind="diagram"), "item", env)
    assert bad.error is not None and bad.error.code == "invalid_args"


def test_no_nul_reaches_a_result_or_the_cache(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    # The font maps `#` to U+0000, so pdfplumber reads a NUL in the title, a bullet and a
    # footnote (see `layout_pdf(nul_for=...)`).
    pdf = layout_pdf(
        [[Text(72, 72, "1 Volleinspeisung#", 10), Text(72, 96, "Anwendung:", 10),
          Text(72, 110, "• PV-Anlagen#", 10), Text(72, 124, "• LBS 9992 00000 003 4", 10),
          Text(72, 700, "*1) Fu#note", 10)]],
        nul_for="#",
    )  # fmt: skip
    registry, env, _ = _setup(sessions, store, pdf)
    cache = ToolCache(sessions, f"test-{uuid.uuid4()}")
    call = _call("extract_text", page=1)
    result = registry.execute(call, "item", env, cache)
    assert result.ok, result.error
    assert "\\u0000" not in json.dumps(result.data)
    assert result.data["applications"][0].startswith("PV-Anlagen")
    assert registry.execute(call, "item", env, cache).data == result.data
