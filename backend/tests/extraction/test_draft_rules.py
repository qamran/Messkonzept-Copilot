"""MKC-23 mutation pass: `MesskonzeptDraft` rules pinned as behaviour, not only through the
exported schema file (survivor M1; M3 to M6 were killed only by the schema snapshot)."""

import pytest
from pydantic import ValidationError

from tests.extraction.drafts import valid_draft


def _refused(body: dict) -> None:  # type: ignore[type-arg]
    from mkc.extraction.draft import MesskonzeptDraft

    with pytest.raises(ValidationError):
        MesskonzeptDraft.model_validate(body)


def test_a_nul_character_is_refused() -> None:
    _refused(valid_draft("Titel\x00mit NUL"))  # Postgres JSONB refuses it


def test_a_meter_needs_a_direction_and_a_draft_a_meter() -> None:
    no_direction = valid_draft()
    no_direction["meters"][0]["directions"] = []
    no_meter = valid_draft() | {"meters": []}
    _refused(no_direction)
    _refused(no_meter)


@pytest.mark.parametrize("code", ["999200000013", "99920000001333", "9992 00000 013 3"])
def test_an_lbs_code_is_exactly_13_digits(code: str) -> None:
    body = valid_draft()
    body["lbs"][0]["code"] = code
    _refused(body)


@pytest.mark.parametrize("page", [0, True, 1.0])
def test_the_source_page_is_a_positive_int(page: object) -> None:
    body = valid_draft()
    body["source"]["page"] = page
    _refused(body)
