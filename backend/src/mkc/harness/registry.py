"""The default tool registry: the allow-lists of design section 8.1 (MKC-14.2).

Item tools are the only tools the model sees. Run-level operations are harness code; they
are registered here only so they get the same validation and tracing.

The argument models and functions are placeholders. The owning tickets replace them:
`render_region`, `save_draft`, `enqueue_approval` (MKC-23); `read_diagram` (MKC-26);
`validate_draft` (MKC-28); `commit_record` (MKC-29). Until then every placeholder returns the
structured error `not_implemented`; none fakes success. `fetch_document` and
`segment_document` (MKC-21) and the item tools `extract_text` and `extract_tables` (MKC-22)
are built: they are real when `default_registry` gets a `DocumentOps`, and stay placeholders
without one. The item tools read the PDF by the item's document hash; the model never names
a document.

`save_draft` writes only its own item's draft, idempotently by (document hash, concept
number), so it has no side effect (decision 53). Harness code runs `enqueue_approval` on its
result; the model never queues anything itself.
"""

from dataclasses import replace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from sqlalchemy.orm import Session, sessionmaker

from mkc.extraction.operations import DocumentOps
from mkc.harness.baseline import RunMemory, make_memory_save_draft
from mkc.harness.drafts import make_save_draft
from mkc.harness.tools import Tool, ToolEnv, ToolRegistry, ToolTracer


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextArgs(_Args):
    page: int = Field(ge=1, description="1-based page number")
    bbox: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat] | None = Field(
        default=None,
        description="x0, top, x1, bottom in PDF points from the top left, as in the item's"
        " task; omitted means the whole page",
    )

    @model_validator(mode="after")
    def _ordered(self) -> "TextArgs":
        if self.bbox is not None and not (
            self.bbox[0] < self.bbox[2] and self.bbox[1] < self.bbox[3]
        ):
            raise ValueError("bbox needs x0 < x1 and top < bottom")
        return self


class TablesArgs(_Args):
    kind: Literal["meter_tech", "lbs"]


class RenderArgs(_Args):
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float] = Field(description="x0, y0, x1, y1 in PDF points")
    dpi: int = Field(ge=1)


class ImageArgs(_Args):
    image_ref: str = Field(min_length=1)


class DraftArgs(_Args):
    draft: dict[str, Any]


class OperatorArgs(_Args):
    operator_id: str = Field(min_length=1)


class DocumentArgs(_Args):
    document_hash: str = Field(min_length=1)


class DraftIdArgs(_Args):
    draft_id: str = Field(min_length=1)


def _placeholder(ticket: str) -> Any:
    def not_built(args: BaseModel, env: ToolEnv) -> Any:
        raise NotImplementedError(f"comes in {ticket}")

    return not_built


ITEM_TOOLS: tuple[Tool, ...] = (
    Tool("extract_text", "Title, applications, footnotes and stated LBS codes of one concept"
         " region.", TextArgs,
         _placeholder("MKC-22"), side_effect=False, deterministic=True, cacheable=True),
    Tool("extract_tables", "Rows of the document's meter-tech or LBS table.", TablesArgs,
         _placeholder("MKC-22"), side_effect=False, deterministic=True, cacheable=True),
    Tool("render_region", "Render a page region as an image (DPI capped).", RenderArgs,
         _placeholder("MKC-23"), side_effect=False, deterministic=True, cacheable=True),
    Tool("read_diagram", "Read a rendered diagram into the topology schema.", ImageArgs,
         _placeholder("MKC-26"), side_effect=False, deterministic=False),
    Tool("validate_draft", "Check a draft; returns errors and warnings.", DraftArgs,
         _placeholder("MKC-28"), side_effect=False, deterministic=True),
    Tool("save_draft", "Save this item's draft (idempotent).", DraftArgs,
         _placeholder("MKC-23"), side_effect=False, deterministic=False),
)  # fmt: skip

RUN_OPERATIONS: tuple[Tool, ...] = (
    Tool("fetch_document", "Fetch an operator's PDF from its allow-listed URL.", OperatorArgs,
         _placeholder("MKC-21"), side_effect=True, deterministic=False),
    Tool("segment_document", "Split a cached document into concept items.", DocumentArgs,
         _placeholder("MKC-21"), side_effect=False, deterministic=True),
    Tool("enqueue_approval", "Queue a saved draft for human approval.", DraftIdArgs,
         _placeholder("MKC-23"), side_effect=True, deterministic=False),
    Tool("commit_record", "Commit an approved draft to the catalogue.", DraftIdArgs,
         _placeholder("MKC-29"), side_effect=True, deterministic=False),
)  # fmt: skip


def default_registry(
    tracers: tuple[ToolTracer, ...] = (),
    *,
    sessions: sessionmaker[Session] | None = None,
    approvals: RunMemory | None = None,
    documents: DocumentOps | None = None,
) -> ToolRegistry:
    """The registry of design 8.1. With `sessions`, `save_draft` is the real one (MKC-16.5);
    tools reach the database through a factory like this, never through `ToolEnv`. With
    `approvals` (baseline, durable approvals off), `save_draft` appends to that memory
    instead, with no key (MKC-20, decision 60); the tool and its spec stay the same. With
    `documents`, `fetch_document` and `segment_document` are the real run-level operations
    (MKC-21, decision 64), and `extract_text` and `extract_tables` the real item tools
    (MKC-22)."""
    item = ITEM_TOOLS
    save = None
    if approvals is not None:
        save = make_memory_save_draft(approvals)
    elif sessions is not None:
        save = make_save_draft(sessions)
    if save is not None:
        item = tuple(replace(t, fn=save) if t.name == "save_draft" else t for t in ITEM_TOOLS)
    run = RUN_OPERATIONS
    if documents is not None:
        real = {
            "fetch_document": documents.fetch,
            "segment_document": documents.segment,
            "extract_text": documents.extract_text,
            "extract_tables": documents.extract_tables,
        }
        item = tuple(replace(t, fn=real[t.name]) if t.name in real else t for t in item)
        run = tuple(replace(t, fn=real[t.name]) if t.name in real else t for t in run)
    return ToolRegistry(item=item, run=run, tracers=tracers)
