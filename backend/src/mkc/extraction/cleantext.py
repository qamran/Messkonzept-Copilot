"""Text helpers shared by `extract_text`, `extract_tables` and the naive baseline (MKC-22).

PDF text can hold control characters: some fonts map a glyph to U+0000 through their
`/ToUnicode` table, and Postgres JSONB refuses `\\u0000` (the MKC-16 note). Every string the
extraction returns goes through `clean`.
"""

import re
from collections.abc import Iterable

# C0 controls and DEL; tab and newline become spaces in `clean`.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SPACE = re.compile(r"\s+")
# A line that ends in a hyphen after a lowercase letter: a word split over two lines.
_SPLIT_WORD = re.compile(r"[a-zäöüß]-$")


def clean(text: str) -> str:
    """Control characters removed, runs of white space made one space, ends stripped."""
    return _SPACE.sub(" ", _CONTROL.sub("", text)).strip()


def join_lines(lines: Iterable[str]) -> str:
    """Wrapped lines as one text, joined with one space. A word split with a hyphen
    (`Abgren-` / `zungsmessung`) is joined without it; `PV-` / `Anlagen` keeps it."""
    out = ""
    for raw in lines:
        line = clean(raw)
        if not line:
            continue
        if out and _SPLIT_WORD.search(out) and line[0].islower():
            out = out[:-1] + line
        else:
            out = f"{out} {line}" if out else line
    return out
