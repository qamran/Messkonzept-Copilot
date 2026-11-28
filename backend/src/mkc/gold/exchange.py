"""Gold export and import for the user's verification, and blind labelling (MKC-24.3,
design 11.1, decision 89). The review UI's blind mode (MKC-29) can reuse `export_items`.

File: JSON `{"items": [...]}`.

- A drafted item: `kind`, `key`, `split`, `blind` (false), `payload`, `drafted_by`,
  `verified_by`. Importing it with `--verified-by NAME` stores the payload (the user's
  corrections) and sets `verified_by`; `drafted_by` stays. Remove an item from the file to
  leave it unverified.
- A blind item: `kind`, `key`, `split`, `blind` (true) and the user's own label in
  `payload` (null until labelled), never a draft or a drafter. A blind export creates the
  key's blind item next to the drafted one; its split comes from the drafted item, else
  from the split file. An item still without a payload is skipped on import.

Import checks every item first (a `MesskonzeptDraft`, the facts-only rule, an existing
item) and writes nothing when one fails. The file never sets `verified_by` or `drafted_by`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from mkc.db.models import GoldItem
from mkc.extraction.draft import MesskonzeptDraft
from mkc.gold.facts import facts_only_problems
from mkc.gold.split import GOLD_SPLIT_FILE, load_split

KIND = "concept"


class GoldFileError(ValueError):
    """The export or the file breaks a rule; `problems` name the keys."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class ImportResult:
    verified: int
    skipped: int  # blind items without a label


def _drafted(row: GoldItem) -> dict[str, Any]:
    return {
        "kind": row.kind,
        "key": row.key,
        "split": row.split,
        "blind": False,
        "payload": row.payload,
        "drafted_by": row.drafted_by,
        "verified_by": row.verified_by,
    }


def _blind(row: GoldItem) -> dict[str, Any]:
    return {"kind": row.kind, "key": row.key, "split": row.split, "blind": True,
            "payload": row.payload}  # fmt: skip


def _row(session: Session, key: str, *, blind: bool, lock: bool = False) -> GoldItem | None:
    query = select(GoldItem).where(
        GoldItem.kind == KIND, GoldItem.key == key, GoldItem.blind.is_(blind)
    )
    return session.scalars(query.with_for_update() if lock else query).first()


def export_items(
    session: Session,
    *,
    blind: bool = False,
    keys: Sequence[str] | None = None,
    split_file: Path = GOLD_SPLIT_FILE,
) -> dict[str, Any]:
    """The export document. Raises `GoldFileError` when a payload is not facts only, or a
    blind key has neither a drafted item nor a side in the split file."""
    if blind:
        if not keys:
            raise GoldFileError(["a blind export needs the keys to label (--key)"])
        rows = [_blind_row(session, key, split_file) for key in sorted(set(keys))]
        return {"items": [_blind(row) for row in rows]}
    query = select(GoldItem).where(GoldItem.kind == KIND, GoldItem.blind.is_(False))
    if keys:
        query = query.where(GoldItem.key.in_(set(keys)))
    rows = list(session.scalars(query.order_by(GoldItem.key)))
    problems = [f"{r.key}: {p}" for r in rows for p in facts_only_problems(r.payload)]
    if problems:
        raise GoldFileError(problems)
    return {"items": [_drafted(r) for r in rows]}


def _blind_row(session: Session, key: str, split_file: Path) -> GoldItem:
    row = _row(session, key, blind=True)
    if row is not None:
        return row
    drafted = _row(session, key, blind=False)
    if drafted is not None:
        side = drafted.split
    else:
        assignments = load_split(split_file).assignments if split_file.is_file() else {}
        if key not in assignments:
            raise GoldFileError([f"{key}: no drafted item and not in {split_file.name}"])
        side = assignments[key]
    row = GoldItem(kind=KIND, key=key, split=side, blind=True, payload=None, drafted_by=None)
    session.add(row)
    session.flush()
    return row


def import_items(session: Session, document: Any, *, verified_by: str) -> ImportResult:
    """Store the verified payloads of `document`, all or nothing (see the module doc)."""
    if not verified_by.strip():
        raise GoldFileError(["--verified-by is empty"])
    items = document.get("items") if isinstance(document, dict) else None
    if not isinstance(items, list):
        raise GoldFileError(['the file needs {"items": [...]}'])
    problems: list[str] = []
    planned: list[tuple[GoldItem, dict[str, Any]]] = []
    skipped = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            problems.append(f"item {index}: needs a key")
            continue
        key, blind = item["key"], item.get("blind") is True
        payload = item.get("payload")
        if blind and not payload:
            skipped += 1
            continue
        try:
            MesskonzeptDraft.model_validate(payload)
        except ValidationError as error:
            problems.append(f"{key}: not a MesskonzeptDraft: {error.error_count()} errors")
            continue
        problems += [f"{key}: {p}" for p in facts_only_problems(payload)]
        row = _row(session, key, blind=blind, lock=True)
        if row is None:
            problems.append(f"{key}: no {'blind' if blind else 'drafted'} item to verify")
            continue
        planned.append((row, cast(dict[str, Any], payload)))
    if problems:
        raise GoldFileError(problems)
    for row, payload in planned:
        row.payload = payload
        row.verified_by = verified_by
    return ImportResult(verified=len(planned), skipped=skipped)
