"""The data rule for gold files (AGENTS.md: gold data holds only extracted facts and page
references; decision 89): no image and no copied text block in a payload.

Limits: a string with a data URI, a base64-like run of 500 characters or more, or a string
over 2,000 characters is refused. A real footnote is a few hundred characters; a fact over
2,000 characters is a copied page, not a fact.
"""

import re
from collections.abc import Iterator
from typing import Any

MAX_TEXT = 2_000
MAX_BASE64_RUN = 500

DATA_URI = re.compile(r"data:[\w.+-]+/[\w.+-]+;base64,", re.IGNORECASE)
BASE64_RUN = re.compile(rf"[A-Za-z0-9+/=_-]{{{MAX_BASE64_RUN},}}")


class FactsOnlyError(ValueError):
    """A payload holds an image or a long text block."""


def _strings(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for name, item in value.items():
            yield from _strings(item, f"{path}.{name}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")


def facts_only_problems(payload: Any) -> list[str]:
    """What breaks the data rule in `payload`, one line per field."""
    found = []
    for path, text in _strings(payload, "payload"):
        if DATA_URI.search(text):
            found.append(f"{path}: an embedded image (data URI)")
        elif BASE64_RUN.search(text):
            found.append(f"{path}: a base64 run of {MAX_BASE64_RUN}+ characters")
        elif len(text) > MAX_TEXT:
            found.append(f"{path}: {len(text)} characters (a text block; at most {MAX_TEXT})")
    return found


def check_facts_only(key: str, payload: Any) -> None:
    found = facts_only_problems(payload)
    if found:
        raise FactsOnlyError(f"{key}: not facts only: " + "; ".join(found))
