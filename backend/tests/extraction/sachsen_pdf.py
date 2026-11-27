"""SachsenNetze fixtures for the MKC-27 tests: a synthetic two-up landscape catalogue.

Real layout (studied 27.11.2026 on "Standard-Messkonzepte in Niederspannung", 09/2025):
9 landscape pages of 960 x 540 pt. Pages 3 to 8 carry two concepts each, side by side. A
concept starts with the heading `Messkonzept <number>:` (`2-1:`, `2-1a:`, `13:`) on the first
line of its half, left half at x = 11 pt, right half at x = 499 pt, a title on the line below,
and a figure (an image) in the middle of the half. Frames end at about y = 483 pt; the footer
(`<page> | Standard-Messkonzepte ...`) sits at y = 509 pt.

No PDF file is committed: the PDF is built by hand. Positions are in pt from the top left.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

WIDTH, HEIGHT = 960.0, 540.0
LEFT_X, RIGHT_X = 11.0, 499.0
HEADING_TOP = 28.0
FOOTER_TOP = 509.0


@dataclass(frozen=True)
class Text:
    x: float
    top: float
    text: str
    size: float = 9.0


@dataclass(frozen=True)
class Box:
    """A stroked rectangle (a figure frame), (x0, top, x1, bottom)."""

    x0: float
    top: float
    x1: float
    bottom: float


def half(x: float, number: str, title: str, *, figure: bool = True, cites: str = "") -> list[Any]:
    """One concept half starting at x: heading, title, body and (optionally) a figure frame."""
    items: list[Any] = [
        Text(x, HEADING_TOP, f"Messkonzept {number}:", 10),
        Text(x, 42, title, 10),
        Text(x + 244, 78, "Anwendungen:"),
        Text(x + 244, 94, "- Windkraftanlagen"),
        Text(x, 431, "Anforderung:"),
        Text(x, 445, "Z1 Zweirichtungszaehler"),
    ]
    if cites:
        items.append(Text(x, 460, f"Wie Messkonzept {cites}: zusaetzlich Erzeugungsanlage G"))
    if figure:
        items.append(Box(x + 37, 131, x + 193, 366))
    return items


def footer(page: int) -> list[Any]:
    return [Text(11, FOOTER_TOP, f"{page} | Standard-Messkonzepte in Niederspannung 09/2025")]


def sachsen_pages() -> list[list[Any]]:
    """cover, contents, 2-1 | 2-1a, 2-2 | 2-2a, 3-5 | 13 (a placeholder), legend."""
    return [
        [Text(72, 229, "Standard-Messkonzepte in Niederspannung", 20), Text(72, 321, "09/2025")],
        [
            Text(28, 30, "Einleitung", 14),
            Text(28, 132, "Dieser Katalog bietet eine Uebersicht an Standard-Messkonzepten"),
            Text(28, 149, "fuer die Anmeldung von Erzeugungsanlagen."),
            *footer(2),
        ],
        [
            *half(LEFT_X, "2-1", "Volleinspeisung"),
            *half(RIGHT_X, "2-1a", "Volleinspeisung mit Erzeugungsmessung", cites="2-1"),
            *footer(3),
        ],
        [
            *half(LEFT_X, "2-2", "Ueberschusseinspeisung"),
            *half(RIGHT_X, "2-2a", "Ueberschusseinspeisung mit Speicher"),
            *footer(4),
        ],
        [
            *half(LEFT_X, "3-5", "Steuerbare Verbrauchseinrichtung"),
            # The real page 8 has a placeholder on the right: `13:`, title `Nr. (tbd)`, no figure.
            *half(RIGHT_X, "13", "Nr. (tbd)", figure=False),
            *footer(5),
        ],
        [
            Text(28, 30, "Standard Messkonzepte", 14),
            Text(28, 55, "Legende Komponenten", 14),
            Text(93, 109, "Z"),
            Text(184, 108, "zu definierende Messstelle"),
            *footer(6),
        ],
    ]


def make_landscape_pdf(
    pages: Sequence[Sequence[Any]], size: tuple[float, float] = (WIDTH, HEIGHT)
) -> bytes:
    """A small valid PDF: Helvetica text at absolute positions and stroked boxes."""
    w, h = size
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(len(pages)))}]"
            f" /Count {len(pages)} >>"
        ).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for i, items in enumerate(pages):
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w:g} {h:g}]"
                f" /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
            ).encode()
        )
        ops: list[str] = []
        for it in items:
            if isinstance(it, Box):
                ops.append(
                    f"{it.x0:g} {h - it.bottom:g} {it.x1 - it.x0:g} {it.bottom - it.top:g} re S"
                )
            else:
                esc = it.text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                y = h - it.top - it.size  # `top` is the top of the glyphs, as pdfplumber reports
                ops.append(f"BT /F1 {it.size:g} Tf 1 0 0 1 {it.x:g} {y:g} Tm ({esc}) Tj ET")
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
