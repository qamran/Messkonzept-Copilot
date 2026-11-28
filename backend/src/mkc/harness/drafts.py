"""The real `save_draft` and `enqueue_approval` (MKC-16.5, MKC-23.3, decisions 56 and 83).

`save_draft` keeps one draft per (document hash, concept key). The key comes from the
harness's `ToolEnv`, never from the model's arguments. It writes only when its item is still
`running`, and follows the user's ruling on a later save (decision 83):

- the key's draft still waits for approval (or has none): the body is replaced, one row;
- the item that owns the draft is `approved` or `committed`: refused with `draft_locked`,
  nothing written, and the loop fails the saving item.

`enqueue_approval` is the run-level operation the harness runs on a saved draft (decision
53); it upserts the draft's one `approval` row. `commit_record` (MKC-29/30) uses the same
`record_key`. A draft row can outlive a failed item: go by the item state, not the row.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Approval, Draft, Item
from mkc.harness.states import ItemState
from mkc.harness.tools import ToolEnv, ToolRefused

LOCKED = frozenset({ItemState.APPROVED.value, ItemState.COMMITTED.value})
"""States of the owning item in which a draft can no longer be replaced."""


class ItemNotRunning(RuntimeError):
    """The saving item is no longer `running`: another worker or a decision moved it."""


def record_key(env: ToolEnv) -> tuple[str, str]:
    """(document hash, concept key): the idempotency key of a draft and of its commit."""
    if env.document_hash is None or env.concept_key is None:
        raise ValueError(f"a record key needs document_hash and concept_key: {env}")
    return env.document_hash, env.concept_key


def draft_body(args: BaseModel) -> Any:
    """The JSON body of the args' `draft`: a `MesskonzeptDraft` dumped as JSON (MKC-23), or
    the value as it is for a test registry's free-form draft."""
    draft = getattr(args, "draft")  # noqa: B009  (any args model with a `draft` field)
    return draft.model_dump(mode="json") if isinstance(draft, BaseModel) else draft


def make_save_draft(sessions: sessionmaker[Session]) -> Callable[[BaseModel, ToolEnv], Any]:
    """`save_draft` writing through its own short transaction from `sessions`.

    The arguments carry only the body (`args.draft`); the key and the item are the harness's.
    Returns `{"draft_id": <id>}`, the same id for every save of one key.
    """

    def save_draft(args: BaseModel, env: ToolEnv) -> Any:
        document_hash, concept_key = record_key(env)
        row = {
            "document_hash": document_hash,
            "concept_key": concept_key,
            "item_id": env.item_id,
            "body": draft_body(args),
        }
        with sessions.begin() as session:
            _check_writable(session, env, document_hash, concept_key)
            new = insert(Draft).values(row)
            upsert = new.on_conflict_do_update(
                constraint="uq_draft_record_key",
                set_={"body": new.excluded.body, "item_id": new.excluded.item_id,
                      "updated_at": func.now()},
            ).returning(Draft.id)  # fmt: skip
            draft_id = session.execute(upsert).scalar_one()
        return {"draft_id": draft_id}

    return save_draft


def _check_writable(session: Session, env: ToolEnv, document_hash: str, concept_key: str) -> None:
    """Lock the saving item and the key's draft (if any); raise unless the save may write."""
    state = session.scalar(select(Item.state).where(Item.id == env.item_id).with_for_update())
    if state != ItemState.RUNNING.value:
        raise ItemNotRunning(f"item {env.item_id} is {state}, not running: nothing saved")
    owner = session.execute(
        select(Draft.id, Item.id, Item.state)
        .join(Item, Item.id == Draft.item_id)
        .where(Draft.document_hash == document_hash, Draft.concept_key == concept_key)
        .with_for_update(of=Draft)
    ).first()
    if owner is not None and owner[2] in LOCKED:
        raise ToolRefused(
            "draft_locked",
            f"the draft for concept {concept_key} is {owner[2]} (item {owner[1]}); it can't be"
            " replaced",
        )


def make_enqueue_approval(
    sessions: sessionmaker[Session],
) -> Callable[[BaseModel, ToolEnv], Any]:
    """`enqueue_approval`: queue draft `args.draft_id` for approval, at most one row per draft.

    Only the item that owns the draft may queue it (`env.item_id`). A second call for the same
    draft keeps the row and points it at this item. Returns `{"approval_id": <id>}`.
    """

    def enqueue_approval(args: BaseModel, env: ToolEnv) -> Any:
        raw = str(args.model_dump()["draft_id"])
        if not (raw.isascii() and raw.isdigit()):
            raise ToolRefused("invalid_args", f"draft_id {raw!r} is not a draft row id")
        draft_id = int(raw)
        with sessions.begin() as session:
            owner = session.scalar(select(Draft.item_id).where(Draft.id == draft_id))
            if owner is None or owner != env.item_id:
                raise ToolRefused(
                    "invalid_args", f"draft {draft_id} is not item {env.item_id}'s draft"
                )
            new = insert(Approval).values(draft_id=draft_id, item_id=env.item_id)
            upsert = new.on_conflict_do_update(
                index_elements=["draft_id"],
                set_={"item_id": new.excluded.item_id, "updated_at": func.now()},
            ).returning(Approval.id)
            approval_id = session.execute(upsert).scalar_one()
        return {"approval_id": approval_id}

    return enqueue_approval
