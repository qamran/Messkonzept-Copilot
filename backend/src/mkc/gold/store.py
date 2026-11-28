"""Store gold drafts (MKC-24.2): the drafted item of a key, with its provenance."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from mkc.db.models import GoldItem
from mkc.gold.draft import GoldDraft
from mkc.gold.facts import check_facts_only


class VerifiedItem(RuntimeError):
    """The key's drafted item is verified: a new draft never overwrites it."""


def store_gold_draft(session: Session, draft: GoldDraft, *, split: str) -> None:
    """Insert or replace the drafted item of `draft.key` (kind `concept`, not blind).

    Raises `VerifiedItem` when that item is verified (nothing is written) and
    `FactsOnlyError` when the payload holds an image or a long text block."""
    check_facts_only(draft.key, draft.payload)
    row = session.scalars(
        select(GoldItem)
        .where(GoldItem.kind == "concept", GoldItem.key == draft.key, GoldItem.blind.is_(False))
        .with_for_update()
    ).first()
    if row is None:
        session.add(
            GoldItem(kind="concept", key=draft.key, split=split, blind=False,
                     payload=draft.payload, drafted_by=draft.drafted_by)
        )  # fmt: skip
        return
    if row.verified_by is not None:
        raise VerifiedItem(f"{draft.key} is verified by {row.verified_by}; not overwritten")
    row.payload = draft.payload
    row.drafted_by = draft.drafted_by
    row.split = split
