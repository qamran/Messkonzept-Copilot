"""ORM models. Each table also has an Alembic migration; a test checks they match."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mkc.db.base import Base

BACKUP_STATES = ("running", "ok", "failed")


class BackupRun(Base):
    """One run of `mkc-backup` (MKC-11): written at the start, updated at the end.

    A run that stays `running` was killed; the status endpoint reports it as stale.
    """

    __tablename__ = "backup_runs"
    __table_args__ = (
        CheckConstraint("state IN ('running', 'ok', 'failed')", name="ck_backup_runs_state"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16))
    # The object's name in the bucket (never the upload link).
    object_name: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    # Error class and a short message with secrets removed.
    error: Mapped[str | None] = mapped_column(Text)


class LbsStructureRow(Base):
    """One Lokationsbündelstruktur from the BDEW Codeliste (MKC-12): reference data.

    Loaded by `mkc-load-lbs` from backend/data/lbs_structures.yaml. `objects` is the list of
    object positions; `source` is the document URL with the page; `version` names the edition.
    """

    __tablename__ = "lbs_structure"

    code: Mapped[str] = mapped_column(String(13), primary_key=True)
    bezeichnung: Mapped[str] = mapped_column(Text)
    objects: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Run(Base):
    """One extraction run (MKC-15). `state` is a `RunState`; change it only via `transition`."""

    __tablename__ = "run"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state: Mapped[str] = mapped_column(String(32))
    # Which run-level limit stopped the run (MKC-18); None unless `state` is `stopped`.
    stop_reason: Mapped[str | None] = mapped_column(Text)
    # The worker that holds the run and until when, by the database clock (MKC-17,
    # decision 57). Both None when the run is free.
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When `process_run` first worked on the run, by the database clock; the wall-time limit
    # counts from here (MKC-18, decision 58).
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The run's Langfuse trace: 32 random hex digits, set once (MKC-19, decision 59).
    trace_id: Mapped[str | None] = mapped_column(Text)
    # `full` or `baseline` (`HarnessMode`), set when the run is created (MKC-20, decision 60).
    mode: Mapped[str] = mapped_column(String(16), server_default="full")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Item(Base):
    """One concept of one document: the unit the item loop works on (MKC-15).

    `task` holds what the model is told (operator, concept key, region). `state` is an
    `ItemState`; change it only via `transition`.
    """

    __tablename__ = "item"
    __table_args__ = (
        UniqueConstraint("run_id", "concept_key", name="uq_item_run_concept"),
        Index("ix_item_run_state", "run_id", "state"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("run.id"))
    concept_key: Mapped[str] = mapped_column(Text)
    document_hash: Mapped[str] = mapped_column(Text)
    task: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(32))
    # Why the item failed, e.g. `step_limit`; None unless `state` is `failed`.
    failure_reason: Mapped[str | None] = mapped_column(Text)
    # Resumes since the last stored turn; over `MKC_ITEM_MAX_RESUMES` the item fails with
    # `resume_limit` (MKC-18, decision 58).
    attempts_without_progress: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Turn(Base):
    """One step of the item loop: the assistant message and the results of its tool calls."""

    __tablename__ = "turn"
    __table_args__ = (UniqueConstraint("item_id", "number", name="uq_turn_item_number"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("item.id"))
    number: Mapped[int] = mapped_column(Integer)
    assistant: Mapped[dict[str, Any]] = mapped_column(JSONB)
    tool_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    cost_eur: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    created_at: Mapped[datetime] = _created()


class Blob(Base):
    """A large tool output, addressed by its sha256 (MKC-16.2, decision 56)."""

    __tablename__ = "blob"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created()


class ToolCacheRow(Base):
    """One cached `ok` result of a deterministic document tool (MKC-16.4, decision 56)."""

    __tablename__ = "tool_cache"
    __table_args__ = (
        UniqueConstraint(
            "tool", "code_version", "args_hash", "document_hash", name="uq_tool_cache_key"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tool: Mapped[str] = mapped_column(Text)
    code_version: Mapped[str] = mapped_column(Text)
    args_hash: Mapped[str] = mapped_column(String(64))
    document_hash: Mapped[str] = mapped_column(Text)
    data: Mapped[Any] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = _created()


class Draft(Base):
    """One item's saved draft, unique by (document hash, concept key) (MKC-16.5)."""

    __tablename__ = "draft"
    __table_args__ = (UniqueConstraint("document_hash", "concept_key", name="uq_draft_record_key"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    document_hash: Mapped[str] = mapped_column(Text)
    concept_key: Mapped[str] = mapped_column(Text)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("item.id"))
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class RunLog(Base):
    """One traced event of a run: a model call attempt, a tool call, a stop or an outage
    (MKC-19, decision 59). The same record goes to Langfuse. No foreign keys (migration 0010).
    """

    __tablename__ = "run_log"
    __table_args__ = (Index("ix_run_log_run_id_id", "run_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(BigInteger)
    item_id: Mapped[int | None] = mapped_column(BigInteger)
    step: Mapped[int | None] = mapped_column(Integer)
    # `model`, `tool`, `stop` or `outage`
    kind: Mapped[str] = mapped_column(String(16))
    # the model id, the tool name or the stop reason
    name: Mapped[str] = mapped_column(Text)
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)
    # `live`, `record` or `replay` for a model call; spend sums take `live` only
    mode: Mapped[str | None] = mapped_column(String(16))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- MKC-21: operators and their fetched documents (decisions 62 and 63) ---


class Operator(Base):
    """One grid operator from `backend/data/operators.yaml`, upserted on every fetch.

    `edition` is the number of the operator's latest `source_document` (0 before a fetch).
    """

    __tablename__ = "operator"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    voltage_level: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    edition: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class SourceDocument(Base):
    """One edition of an operator's catalogue. The PDF itself is only in Storage, under the
    ref `blob:sha256:<sha256>`; Postgres keeps no bytes. A different hash than the latest
    edition's is a new edition, never an overwrite (decision 62)."""

    __tablename__ = "source_document"
    __table_args__ = (
        UniqueConstraint("operator_id", "edition", name="uq_source_document_edition"),
        Index("ix_source_document_sha256", "sha256"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    operator_id: Mapped[str] = mapped_column(Text, ForeignKey("operator.id"))
    edition: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
