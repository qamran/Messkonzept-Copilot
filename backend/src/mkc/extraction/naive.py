"""The naive baseline for the E1 comparison (MKC-22.2, decision 77): plain text, line by line,
the way `pdftotext` gives it, and table rows read from that text with no cell grid.

Pure Python (pdfplumber's text, which pdfminer lays out line by line), so no system binary
is needed. `naive_tables` is an ordinary line parser, not rigged to fail: a line with an LBS
code is a row when the text before the code is only concept numbers or `nicht
visualisiert`; a meter-tech row is a line that starts with a concept number below a heading
naming a meter (`(Z2)`) on the same page. Where a ruled table centres a short cell in a
tall row, the code meets only the middle line of its concept cell, and the baseline pairs it
wrongly: the failure `extract_tables` exists to avoid.
"""

import io
import re

import pdfplumber

from mkc.extraction.cleantext import clean
from mkc.extraction.tables import CONCEPT, NOT_SHOWN, Kind, Row

_CODE = re.compile(r"(?<![0-9])([0-9]{4}\s?[0-9]{5}\s?[0-9]{3}\s?[0-9])(?![0-9])")
_HEADING = re.compile(r"\(Z\d")


def naive_text(pdf: bytes) -> str:
    """Every page's text in reading order, line by line; pages separated by a form feed."""
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        pages = [page.extract_text() or "" for page in document.pages]
    return "\f".join("\n".join(clean(line) for line in page.splitlines()) for page in pages)


def naive_tables(pdf: bytes, kind: Kind) -> list[Row]:
    """The rows of `naive_text`, line by line, in the shape `extract_tables` gives."""
    rows: list[Row] = []
    for number, page in enumerate(naive_text(pdf).split("\f"), 1):
        heading: str | None = None  # names the meter of its own page's table only
        for line in page.splitlines():
            if kind == "lbs":
                row = _lbs_row(line, number)
            else:
                if _HEADING.search(line):
                    heading = line
                    continue
                row = _meter_row(line, number, heading)
            if row is not None:
                rows.append(row)
    return rows


def _lbs_row(line: str, page: int) -> Row | None:
    found = _CODE.search(line)
    if found is None:
        return None
    before = line[: found.start()].strip()
    if before.lower() == NOT_SHOWN:
        concepts: list[str] = []
    else:
        concepts = [t for t in re.split(r"[\s/]+", before) if t]
        if not all(CONCEPT.fullmatch(t) for t in concepts):
            return None
    code = re.sub(r"\s", "", found.group(1))
    label = clean(line[found.end() :])
    return Row(kind="lbs", page=page, concepts=concepts, code=code, label=label, cells=[])


def _meter_row(line: str, page: int, heading: str | None) -> Row | None:
    first, _, rest = line.partition(" ")
    if heading is None or not rest or not CONCEPT.fullmatch(first):
        return None
    return Row(
        kind="meter_tech", page=page, concepts=[first], code=None, label=heading, cells=[rest]
    )
