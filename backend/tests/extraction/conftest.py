"""Helpers for the extraction tests (MKC-21): a migrated test database, an in-memory Storage
fake, a fake HTTP getter and a synthetic PDF builder. No test touches the network or a real
PDF; `mkc.extraction` is imported inside the tests, so a missing module fails each test, not
the collection.

MKC-22 adds `layout_pdf` (text at given positions, ruled boxes, cp1252 so `Ü`, `§` and `•`
work) and `ruled_table` (a ruled table whose shorter cells are centred in their row, as in
the Berlin catalogue; the centring is what shifts rows under naive line-by-line text).
"""

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from mkc.harness.blobs import PREFIX

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
OPERATOR_ID = "stromnetz-berlin"
URL_OK = "https://netz.example/messkonzepte.pdf"
HOST_OK = "netz.example"


@pytest.fixture
def engine(database_env: URL) -> Iterator[Engine]:
    """The test database at head, with the MKC-21 tables emptied (if they exist yet)."""
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    eng = create_engine(database_env)
    with eng.begin() as conn:
        present = [t for t in ("source_document", "operator") if inspect(conn).has_table(t)]
        if present:
            conn.execute(text(f"truncate {', '.join(present)} restart identity cascade"))
        conn.execute(text("truncate blob"))
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine)


class MemoryStore:
    """A `BlobStore` (mkc.harness.blobs) that keeps blobs in a dict: the Storage fake."""

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}
        self.puts = 0
        self.gets = 0  # MKC-22: a tool-cache hit must not read the PDF again

    def put(self, data: bytes) -> str:
        self.puts += 1
        ref = PREFIX + hashlib.sha256(data).hexdigest()
        self.data[ref] = data
        return ref

    def get(self, ref: str) -> bytes:
        self.gets += 1
        return self.data[ref]


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@dataclass
class FakeGet:
    """A getter for `fetch_document(get=...)`: returns the queued responses in order and
    records every URL asked for. A response is (final URL after redirects, bytes)."""

    responses: list[tuple[str, bytes]]
    calls: list[str] = field(default_factory=list)

    def __call__(self, url: str) -> Any:
        from mkc.extraction.fetch import FetchResponse

        self.calls.append(url)
        final_url, content = self.responses.pop(0)
        return FetchResponse(url=final_url, content=content)


def operators(url: str = URL_OK, hosts: tuple[str, ...] = (HOST_OK,)) -> dict[str, Any]:
    """An operator mapping for `fetch_document(operators=...)` with one test operator."""
    from mkc.extraction.operators import OperatorConfig

    return {
        OPERATOR_ID: OperatorConfig(
            id=OPERATOR_ID,
            name="Netz Musterstadt (test)",
            voltage_level="NS",
            url=url,
            allowed_hosts=hosts,
        )
    }


def rows(engine: Engine, sql: str) -> list[Any]:
    with engine.connect() as conn:
        return list(conn.execute(text(sql)))


def berlin_pages(concepts: Sequence[str]) -> list[list[str]]:
    """A Berlin-style catalogue in the real layout (Stromnetz Berlin, September 2026): a cover,
    a contents page, one page per concept, then an appendix page. A concept page opens with
    `<number> <title>` on the first line of the main column; a sidebar on the right repeats
    `Messkonzepte` (level with the heading) and `Seite/Umfang n/N`. One concept body cites
    another concept, and the appendix has table rows that start with concept numbers; neither
    may become a region of its own."""
    total = len(concepts) + 3
    pages: list[list[str]] = [
        ["Netz Musterstadt GmbH", "Messkonzepte fuer Kundenanlagen", "Stand 01.2026"],
        ["Inhaltsverzeichnis", *(f"{n}  Konzept ........ {i + 3}" for i, n in enumerate(concepts))],
    ]
    for i, n in enumerate(concepts):
        body = [f"{n} Ueberschusseinspeisung", "Anwendung:", "Z1 Zweirichtungszaehler"]
        if i > 0:
            body.append(f"Wie Messkonzept {concepts[0]}, zusaetzlich Erzeugungsanlage G")
        body += [Side("Messkonzepte"), Side("Seite/Umfang"), Side(f"{i + 3}/{total}")]
        pages.append(body)
    rows = [f"{n} 2RZ 60 A 2RZ 100 A" for n in concepts]
    pages.append(["Anhang: Legende", "Z = Zaehler, G = Erzeugungsanlage", *rows])
    return pages


class Side(str):
    """A line for the sidebar at x = 461 pt, in 8 pt type (see `make_pdf`)."""


def make_pdf(pages: Sequence[Sequence[str]], size: tuple[float, float] = (595.0, 842.0)) -> bytes:
    """A small valid PDF with one text line per entry, Helvetica, ASCII only. Built by hand so
    the tests need no PDF library and no PDF file is ever committed. Lines go down the main
    column from x = 72 pt in 14 pt type; `Side` lines go down a sidebar from x = 461 pt."""
    w, h = size
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(len(pages)))}]"
            f" /Count {len(pages)} >>"
        ).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, lines in enumerate(pages):
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w:g} {h:g}]"
                f" /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
            ).encode()
        )
        ops, rows = ["BT"], {False: 0, True: 0}
        for line in lines:
            side = isinstance(line, Side)
            x, size, step = (461, 8, 10) if side else (72, 14, 18)
            esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            y = h - 72 - step * rows[side]
            rows[side] += 1
            ops.append(f"/F1 {size} Tf 1 0 0 1 {x} {y:g} Tm ({esc}) Tj")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for num, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % num + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


@dataclass(frozen=True)
class Text:
    """One text line for `layout_pdf`: `x` and `top` in PDF points from the top left."""

    x: float
    top: float
    text: str
    size: float = 9.0


@dataclass(frozen=True)
class Box:
    """A stroked rectangle (a table rule) for `layout_pdf`, from the top left."""

    x0: float
    top: float
    x1: float
    bottom: float


A4 = (595.0, 842.0)


def layout_pdf(
    pages: Sequence[Sequence[Text | Box]],
    size: tuple[float, float] = A4,
    *,
    nul_for: str | None = None,
) -> bytes:
    """A small valid PDF with text and rules at given positions (Helvetica, WinAnsi/cp1252).
    Built by hand, like `make_pdf`, so no PDF file is ever committed. `nul_for` names one
    character whose glyph the font's `/ToUnicode` map turns into U+0000, as some real PDFs
    do: pdfplumber then reads a NUL there (MKC-22, the MKC-16 note on JSONB)."""
    h = size[1]
    streams = []
    for items in pages:
        ops = ["0.5 w"]
        for item in items:
            if isinstance(item, Box):
                bw, bh = item.x1 - item.x0, item.bottom - item.top
                ops.append(f"{item.x0:g} {h - item.bottom:g} {bw:g} {bh:g} re S")
            else:
                esc = item.text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
                y = h - item.top - item.size
                ops.append(f"BT /F1 {item.size:g} Tf 1 0 0 1 {item.x:g} {y:g} Tm ({esc}) Tj ET")
        streams.append("\n".join(ops).encode("cp1252"))
    return _assemble(streams, size, nul_for)


LINE = 11.0  # line pitch inside a table cell
PAD = 4.0  # cell padding above and below


def ruled_table(
    x0: float, top: float, widths: Sequence[float], rows: Sequence[Sequence[Sequence[str]]]
) -> tuple[list[Text | Box], float]:
    """A ruled table: each row is a list of cells, each cell a list of lines. A row is as
    tall as its longest cell; shorter cells are centred vertically, so their lines sit
    between the longer cell's lines. Returns the items and the table's bottom."""
    items: list[Text | Box] = []
    y = top
    for row in rows:
        height = max(len(cell) for cell in row) * LINE + 2 * PAD
        x = x0
        for width, cell in zip(widths, row, strict=True):
            items.append(Box(x, y, x + width, y + height))
            first = y + (height - len(cell) * LINE) / 2
            items += [Text(x + 3, first + i * LINE, line) for i, line in enumerate(cell)]
            x += width
        y += height
    return items, y


def _assemble(
    streams: Sequence[bytes], size: tuple[float, float], nul_for: str | None = None
) -> bytes:
    w, h = size
    n = len(streams)
    font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding"
    if nul_for is not None:
        font += f" /ToUnicode {4 + 2 * n} 0 R"
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>")
        .encode(),
        (font + " >>").encode(),
    ]  # fmt: skip
    for i, stream in enumerate(streams):
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w:g} {h:g}]"
                f" /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
            ).encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    if nul_for is not None:
        code = nul_for.encode("cp1252").hex().upper()
        cmap = (
            "/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Nul def\n"
            f"1 begincodespacerange <00> <FF> endcodespacerange\n1 beginbfchar <{code}> <0000>"
            "\nendbfchar endcmap CMapName currentdict /CMap defineresource pop end end"
        ).encode()
        objs.append(b"<< /Length %d >>\nstream\n" % len(cmap) + cmap + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for num, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % num + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)
