"""MKC-23: the Pydantic `MesskonzeptDraft` (design section 7) and its exported JSON schema.

Pinned (assumptions for the coordinator):

- `mkc.extraction.draft.MesskonzeptDraft`, with exactly the fields of `DRAFT_FIELDS`:
  section 7's Messkonzept without `status`, `approved_by` and `approved_at`, which belong to
  the approval; the model can't send them (`extra="forbid"` all the way down).
- `provenance` is `stated` or `inferred`; meter purposes and component kinds are the closed
  lists of section 7.
- The schema for the vision prompt (MKC-26) is the file
  `backend/prompts/messkonzept_draft.schema.json`, equal to `model_json_schema()`, so a
  change to the model without a new export fails here.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.extraction.drafts import COMPONENT_KINDS, DRAFT_FIELDS, PURPOSES, valid_draft

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "prompts" / "messkonzept_draft.schema.json"


def _model() -> Any:
    from mkc.extraction.draft import MesskonzeptDraft

    return MesskonzeptDraft


def test_the_draft_has_exactly_the_section_7_fields() -> None:
    assert set(_model().model_fields) == DRAFT_FIELDS


def test_a_complete_draft_validates_and_round_trips() -> None:
    model = _model()
    draft = model.model_validate(valid_draft())
    assert model.model_validate(draft.model_dump(mode="json")) == draft
    assert draft.formulas == []  # optional in section 7


@pytest.mark.parametrize("field", ["status", "approved_by", "approved_at", "document_hash"])
def test_approval_fields_and_keys_are_refused(field: str) -> None:
    body = valid_draft() | {field: "approved"}
    with pytest.raises(ValidationError):
        _model().model_validate(body)


@pytest.mark.parametrize("missing", ["operator", "number", "title", "meters", "lbs", "source"])
def test_a_required_field_missing_is_refused(missing: str) -> None:
    body = valid_draft()
    del body[missing]
    with pytest.raises(ValidationError):
        _model().model_validate(body)


def test_provenance_is_stated_or_inferred() -> None:
    model = _model()
    for provenance in ("stated", "inferred"):
        body = valid_draft()
        body["lbs"][0]["provenance"] = provenance
        assert model.model_validate(body).lbs[0].provenance == provenance
    body = valid_draft()
    body["lbs"][0]["provenance"] = "guessed"
    with pytest.raises(ValidationError):
        model.model_validate(body)


def test_meter_purposes_and_component_kinds_are_the_section_7_lists() -> None:
    model = _model()
    for purpose in PURPOSES:
        body = valid_draft()
        body["meters"][0]["purpose"] = purpose
        model.model_validate(body)
    for kind in COMPONENT_KINDS:
        body = valid_draft()
        body["components"][0]["kind"] = kind
        model.model_validate(body)
    bad_purpose = valid_draft()
    bad_purpose["meters"][0]["purpose"] = "Sonstiges"
    bad_kind = valid_draft()
    bad_kind["components"][0]["kind"] = "X"
    for body in (bad_purpose, bad_kind):
        with pytest.raises(ValidationError):
            model.model_validate(body)


def test_nested_objects_refuse_unknown_fields() -> None:
    body = valid_draft()
    body["meters"][0]["approved"] = True
    with pytest.raises(ValidationError):
        _model().model_validate(body)


def test_the_json_schema_is_exported_for_the_vision_prompt() -> None:
    assert SCHEMA_FILE.is_file(), f"{SCHEMA_FILE} is missing (MKC-26 reads it)"
    exported = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert exported == _model().model_json_schema()
    assert set(exported["properties"]) == DRAFT_FIELDS
