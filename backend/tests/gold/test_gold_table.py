"""MKC-24: table `gold_item(kind, key, split, payload, drafted_by, verified_by, blind)` and
storing a gold draft, lane A2.

Pinned interface:

    mkc.db.models.GoldItem        # ORM class of table `gold_item` (id, timestamps: free)
    mkc.gold.store.store_gold_draft(session: Session, draft: GoldDraft, *, split: str) -> None
        # upserts the drafted row of `draft.key` (kind "concept", blind false): payload and
        # drafted_by set, verified_by left as it is. A verified row is never overwritten.

Provenance per gold item (design 11.1): who drafted it, who verified it, blind or not. The
migration's revision id is not pinned (the coordinator may re-chain it).
"""

from typing import Any

import pytest
from sqlalchemy import Engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.gold.conftest import draft_payload
from tests.gold.test_gold_draft import TEXT, Recorder, custom_config

KEY = "stromnetz-berlin:4.1"


def _gold_draft(payload: dict[str, Any], key: str = KEY) -> Any:
    from mkc.gold.draft import draft_concept

    config = custom_config(gold="y/gold")
    return draft_concept(Recorder(payload).client(config), config, key=key, text=TEXT)


def _rows(engine: Engine) -> list[Any]:
    from mkc.db.models import GoldItem

    with Session(engine) as session:
        rows = list(session.scalars(select(GoldItem).order_by(GoldItem.id)))
        session.expunge_all()
        return rows


def test_gold_item_has_the_provenance_columns(gold_engine: Engine) -> None:
    columns = {c["name"]: c for c in inspect(gold_engine).get_columns("gold_item")}
    for name in ("kind", "key", "split", "payload", "drafted_by", "verified_by", "blind"):
        assert name in columns, name
    assert columns["blind"]["nullable"] is False
    assert columns["drafted_by"]["nullable"] is True  # a blind label has no drafter
    assert columns["verified_by"]["nullable"] is True  # not verified yet
    assert columns["payload"]["nullable"] is True  # a blind item waits for its label


def test_split_is_dev_or_test(gold_engine: Engine) -> None:
    from mkc.db.models import GoldItem

    with pytest.raises(IntegrityError), Session(gold_engine) as session, session.begin():
        session.add(GoldItem(kind="concept", key=KEY, split="train", blind=False))


def test_store_gold_draft_writes_the_provenance(gold_engine: Engine) -> None:
    from mkc.gold.store import store_gold_draft

    with Session(gold_engine) as session, session.begin():
        store_gold_draft(session, _gold_draft(draft_payload()), split="test")
    [row] = _rows(gold_engine)
    assert (row.kind, row.key, row.split, row.blind) == ("concept", KEY, "test", False)
    assert row.drafted_by == "openrouter:y/gold"
    assert row.verified_by is None
    assert row.payload["title"] == draft_payload()["title"]


def test_a_new_draft_of_the_same_key_replaces_the_unverified_one(gold_engine: Engine) -> None:
    from mkc.gold.store import store_gold_draft

    for title in ("first title", "second title"):
        with Session(gold_engine) as session, session.begin():
            store_gold_draft(session, _gold_draft(draft_payload(title=title)), split="dev")
    [row] = _rows(gold_engine)
    assert row.payload["title"] == "second title"


def test_a_verified_item_is_never_overwritten_by_a_new_draft(gold_engine: Engine) -> None:
    from mkc.db.models import GoldItem
    from mkc.gold.store import store_gold_draft

    with Session(gold_engine) as session, session.begin():
        session.add(
            GoldItem(kind="concept", key=KEY, split="dev", blind=False,
                     payload=draft_payload(title="verified title"),
                     drafted_by="openrouter:y/gold", verified_by="qamran")
        )  # fmt: skip
    try:
        with Session(gold_engine) as session, session.begin():
            store_gold_draft(session, _gold_draft(draft_payload(title="new")), split="dev")
    except Exception:  # refusing is fine; overwriting is not
        pass
    [row] = _rows(gold_engine)
    assert row.payload["title"] == "verified title"
    assert row.verified_by == "qamran"
