"""The real `save_draft`: one draft per (document hash, concept key) (MKC-16.5, decision 56).

The key comes from the harness's `ToolEnv`, never from the model's arguments. A second save
for the same key replaces the body and keeps one row. `commit_record` (MKC-29/30) uses the
same `record_key`. A draft row can outlive a failed item: go by the item state, not the row.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Draft
from mkc.harness.tools import ToolEnv


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
        body = draft_body(args)
        row = {
            "document_hash": document_hash,
            "concept_key": concept_key,
            "item_id": env.item_id,
            "body": body,
        }
        new = insert(Draft).values(row)
        upsert = new.on_conflict_do_update(
            constraint="uq_draft_record_key",
            set_={"body": new.excluded.body, "item_id": new.excluded.item_id,
                  "updated_at": func.now()},
        ).returning(Draft.id)  # fmt: skip
        with sessions.begin() as session:
            draft_id = session.execute(upsert).scalar_one()
        return {"draft_id": draft_id}

    return save_draft
