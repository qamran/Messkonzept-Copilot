"""Render a page region as a PNG (MKC-23.2, feature 31, design 8.1).

The bbox is `x0, top, x1, bottom` in PDF points from the top left of the page as shown (the
convention of `extract_text` and of the items' regions). The page and the bbox are checked
against the document before anything is drawn; the DPI cap is the caller's (the setting
`render_max_dpi`). PDFium crops on the bitmap, after the page's rotation, so the region is
the one pdfplumber reads. The same bytes, page, bbox and DPI give the same PNG.
"""

import io
from dataclasses import dataclass

import pypdfium2 as pdfium  # type: ignore[import-untyped]  # no py.typed; comes with pdfplumber

TOLERANCE_PT = 0.01
"""How far past the page edge a bbox may reach (float noise from the segmenter)."""


class RegionOutsidePage(ValueError):
    """The page is past the end, or the bbox reaches off the page."""


@dataclass(frozen=True)
class Rendered:
    png: bytes
    width: int
    height: int


def render_region(
    pdf: bytes, page: int, bbox: tuple[float, float, float, float], dpi: int
) -> Rendered:
    """The region of `page` (1-based) inside `bbox`, rendered at `dpi`, as a PNG."""
    x0, top, x1, bottom = bbox
    document = pdfium.PdfDocument(pdf)
    try:
        if not 1 <= page <= len(document):
            raise RegionOutsidePage(f"page {page} is past the end ({len(document)} pages)")
        pdf_page = document[page - 1]
        try:
            width, height = pdf_page.get_size()  # as shown: the rotation is applied
            if (
                min(x0, top) < -TOLERANCE_PT
                or x1 > width + TOLERANCE_PT
                or bottom > height + TOLERANCE_PT
            ):
                raise RegionOutsidePage(
                    f"bbox {list(bbox)} reaches off page {page} ({width:g} x {height:g} pt)"
                )
            crop = (max(x0, 0.0), max(height - bottom, 0.0), max(width - x1, 0.0), max(top, 0.0))
            bitmap = pdf_page.render(scale=dpi / 72, crop=crop)
            image = bitmap.to_pil()
        finally:
            pdf_page.close()
    finally:
        document.close()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Rendered(buffer.getvalue(), image.width, image.height)
