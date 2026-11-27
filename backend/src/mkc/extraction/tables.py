"""`extract_tables` (feature 30, MKC-22.2, decision 77): the rows of the meter-tech and LBS
tables, read from pdfplumber's cell grid of each ruled table.

Line-by-line text shifts the rows of these tables: a short cell is centred in a tall row,
so its line meets the middle line of a wrapped neighbour (the spike of 24.11.2026; see
`mkc.extraction.naive`). The cell grid keeps each row whole.

Rules, per table (`table_rows`):

- A table is told by its header, never by its column count: a header cell `Code der LBS`
  makes an LBS table; `Messkonzept` in the first column with a power-band row (`kVA`) makes
  a meter-tech table. Other tables (`Befestigung der Messtechnik`) give nothing.
- The header is every row above the first data row. A data row starts with a list of
  concept numbers (`2 / 2.1 / 8 / 11.1`), or `nicht visualisiert` in an LBS table.
- LBS: the code cell must hold 13 ASCII digits (spaces removed), else the row is skipped;
  the check digit is not judged here (as in `extract_text`, decision 76). The label is the
  Bezeichnung, the cell right of the code.
- Meter tech: the label is the table's heading (the second column of the header rows that
  are not the power-band row), the cells are the power-band columns, left to right.
- Text that wraps in a cell is joined with one space; a word split with a hyphen is joined
  without it (`Abgren-` / `zungsmessung`). Control characters are removed.

A table that goes on over a page break repeats its header in the Berlin catalogue, so each
part is read on its own and the rows come back in page order.
"""

import io
import re
from typing import Literal

import pdfplumber
from pydantic import BaseModel, ConfigDict

from mkc.extraction.cleantext import clean, join_lines

Kind = Literal["meter_tech", "lbs"]
Grid = list[list[str | None]]

# A concept number: 1, 4.1, 11.1, 2a (as in `segment.NUMBER`).
CONCEPT = re.compile(r"\d{1,2}(?:\.\d{1,2})*[a-z]?")
NOT_SHOWN = "nicht visualisiert"
_CODE = re.compile(r"[0-9]{13}")


class Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Kind
    page: int  # 1-based
    concepts: list[str]  # as printed, in order; [] for `nicht visualisiert`
    code: str | None  # lbs: 13 digits; meter_tech: None
    label: str  # lbs: the Bezeichnung; meter_tech: the table's heading
    cells: list[str]  # meter_tech: one per power band; lbs: []


def extract_tables(pdf: bytes, kind: Kind) -> list[Row]:
    """Every row of every `kind` table in the document, in page order."""
    rows: list[Row] = []
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        for number, page in enumerate(document.pages, 1):
            tables = sorted(page.find_tables(), key=lambda t: (t.bbox[1], t.bbox[0]))
            for table in tables:
                rows += table_rows(table.extract(), number, kind)
    return rows


def table_rows(grid: Grid, page: int, kind: Kind) -> list[Row]:
    """The rows of one table's cell grid, if it is a `kind` table; else []."""
    text = [[cell_text(c) for c in row] for row in grid]
    first = next((i for i, row in enumerate(text) if concepts_of(row) is not None), None)
    if first is None:
        return []
    header = text[:first]
    data = [(row, concepts_of(row)) for row in text[first:]]
    if kind == "lbs":
        return _lbs_rows(header, data, page)
    return _meter_rows(header, data, page)


def cell_text(cell: str | None) -> str:
    return join_lines((cell or "").split("\n"))


def concepts_of(row: list[str]) -> list[str] | None:
    """The concept numbers in the row's first cell, [] for `nicht visualisiert`, or None
    when the cell is no concept list (a header or an empty row)."""
    if not row:
        return None
    first = row[0]
    if first.lower() == NOT_SHOWN:
        return []
    tokens = [clean(t) for t in first.split("/")]
    tokens = [t for t in tokens if t]
    if tokens and all(CONCEPT.fullmatch(t) for t in tokens):
        return tokens
    return None


def _lbs_rows(
    header: list[list[str]], data: list[tuple[list[str], list[str] | None]], page: int
) -> list[Row]:
    column = next(
        (i for row in header for i, c in enumerate(row) if c.lower() == "code der lbs"), None
    )
    if column is None:
        return []
    rows = []
    for row, concepts in data:
        if concepts is None or len(row) <= column:
            continue
        code = re.sub(r"\s", "", row[column])
        if not _CODE.fullmatch(code):
            continue
        label = row[column + 1] if len(row) > column + 1 else ""
        rows.append(Row(kind="lbs", page=page, concepts=concepts, code=code, label=label, cells=[]))
    return rows


def _meter_rows(
    header: list[list[str]], data: list[tuple[list[str], list[str] | None]], page: int
) -> list[Row]:
    bands = [row for row in header if any("kVA" in c for c in row[1:])]
    if not bands or not any(row and "Messkonzept" in row[0] for row in header):
        return []
    label = join_lines(row[1] for row in header if row not in bands and len(row) > 1)
    return [
        Row(kind="meter_tech", page=page, concepts=concepts, code=None, label=label, cells=row[1:])
        for row, concepts in data
        if concepts
    ]
