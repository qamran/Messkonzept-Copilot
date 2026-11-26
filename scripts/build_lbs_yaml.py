"""Build backend/data/lbs_structures.yaml from the BDEW Codeliste PDF (MKC-12.2).

The PDF is never committed (AGENTS.md data rules). Download it into a temp directory,
then run from the repo root:

    uv run --no-project --with pdfplumber==0.11.7 --with pyyaml \
        python -I -X utf8 scripts/build_lbs_yaml.py \
        <path/to/Codeliste.pdf> backend/data/lbs_structures.yaml

Source and terms: docs/261120261404-codeliste-research.md (decision 50).

What it writes, per structure: code, Bezeichnung, page and objects (object code, Objekt,
Funktion, Richtung, Ebene, Flexibilität, Anzahl, Referenz Messlokation, Referenz
Netzlokation). Nothing else from the document.

How it reads the tables: pdfplumber's cell grid splits some cells and repeats their text,
and plain text extraction shifts rows. So it reads words: footnote superscripts (font
under 8 pt) are dropped, columns come from the header words' x positions, a line with an
object code starts a row, and other lines continue the row above (hyphenated words are
joined).

Normalised: the MeLo's Funktion (Netzübergabe, Hinterschaltung, Differenzmessung) is in the
Objekt column on some pages and in the Richtung column on others; it is moved to
`funktion`. "--" (none) becomes an empty value. Fails, and writes nothing, when the PDF's
hash differs from the edition below, when an object code maps to two different positions,
or when a value is not one the Codeliste uses.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from pathlib import Path
from typing import Any

import pdfplumber
import yaml

SOURCE = {
    "title": "Codeliste der Lokationsbündelstrukturen",
    "publisher": "BDEW",
    "version": "1.0",
    "edition": "Konsolidierte Lesefassung mit Fehlerkorrekturen, Stand 13.12.2024",
    "applies_from": "2024-10-01",
    "url": "https://bdew-mako.de/pdf/Codeliste-Lokationsbu%CC%88ndelstrukturen_1_0_Fehlerkorrektur_20241213.pdf",
    "sha256": "0ae47f79bb719c48920fed9019657eec84659a7f7edbc11805444499dc11ac96",
    "retrieved": "2026-11-26",
}

OVERVIEW_PAGE = 16
MIN_FONT = 8.0  # body text is 9 pt; footnote marks are 6-7 pt
CODE = re.compile(r"9992 ?00000 ?\d{3} ?\d")
FUNKTIONEN = ("Netzübergabe", "Hinterschaltung", "Differenzmessung")
OBJEKTE = ("MeLo", "MaLo", "TR", "NeLo")
ANZAHL = re.compile(r"^(\d|\d-\d|\d-N|≥\d)$")
COLUMNS = ["objekt_code", "objekt", "richtung", "ebene", "flex", "anzahl", "ref_melo", "ref_nelo"]


class BuildError(RuntimeError):
    pass


def compact(text: str) -> str:
    return text.replace(" ", "")


def codes_in(text: str) -> list[str]:
    return [compact(c) for c in CODE.findall(text)]


def clean_page(page: Any) -> Any:
    return page.dedupe_chars().filter(
        lambda o: o.get("object_type") != "char" or o["size"] >= MIN_FONT
    )


def overview(pdf: Any) -> dict[str, str]:
    """Section 3: code -> Bezeichnung."""
    names: dict[str, str] = {}
    for table in clean_page(pdf.pages[OVERVIEW_PAGE - 1]).extract_tables():
        for row in table:
            cells = [c.replace("\n", " ").strip() for c in row if c and c.strip()]
            if len(cells) == 2 and CODE.fullmatch(cells[0]):
                names[compact(cells[0])] = cells[1]
    if len(names) != 15:
        raise BuildError(f"overview: expected 15 structures, found {len(names)}")
    return names


def column_starts(words: list[dict[str, Any]]) -> list[float]:
    """x positions where each column's header word starts."""

    def first(text: str, after: float = -1.0) -> dict[str, Any]:
        for w in words:
            if w["text"].startswith(text) and w["x0"] > after:
                return w
        raise BuildError(f"header word {text!r} not found")

    objekt_code = first("Objekt-Code")
    objekt = first("Objekt", objekt_code["x1"])
    richtung = first("Richtung")
    ebene = first("Ebe")
    flex = first("Flexibilit")
    anzahl = first("Anzahl")
    starts = [
        objekt_code["x0"],
        objekt["x0"],
        richtung["x0"],
        ebene["x0"],
        flex["x0"],
        anzahl["x0"],
    ]
    refs = [
        w for w in words if w["text"].startswith("Referenz") and w["top"] < anzahl["bottom"] + 5
    ]
    starts += sorted(w["x0"] for w in refs)
    return starts


def join(previous: str, more: str) -> str:
    if not previous:
        return more
    if previous.endswith("-") and more[:1].islower():
        return previous[:-1] + more
    return f"{previous} {more}"


def structure_table(page: Any) -> tuple[str, list[dict[str, str]]] | None:
    """The structure code and object rows of the page's code table; None if it has none."""
    table = next(
        (
            t
            for t in page.find_tables()
            if "Objekt-Code" in (page.crop(t.bbox).extract_text() or "")
        ),
        None,
    )
    if table is None:
        return None
    code = f"page {page.page_number}"
    # The header ends at the first grid row that holds a code (a ruled line in the PDF).
    body_top = next(
        (r.bbox[1] for r in table.rows if CODE.search(page.crop(r.bbox).extract_text() or "")),
        None,
    )
    if body_top is None:
        raise BuildError(f"{code}: no body rows on page {page.page_number}")
    words = page.crop(table.bbox).extract_words(keep_blank_chars=False, x_tolerance=1.5)
    starts = column_starts([w for w in words if w["bottom"] <= body_top + 1])
    names = COLUMNS[: len(starts)]
    left = " ".join(
        w["text"]
        for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
        if w["top"] >= body_top - 1 and w["x0"] < starts[0] - 2
    )
    if len(codes_in(left)) != 1:
        raise BuildError(f"{code}: expected one structure code in the first column: {left!r}")
    code = codes_in(left)[0]
    body = [w for w in words if w["top"] >= body_top - 1 and w["x0"] >= starts[0] - 2]

    def column(word: dict[str, Any]) -> str:
        return names[max(i for i, s in enumerate(starts) if word["x0"] >= s - 2)]

    # One row per object code. Cells are top-aligned: a row's first line holds its object
    # code, and wrapped lines follow below it. Each word goes to the last code at or above it.
    anchors = sorted(
        float(w["top"]) for w in body if column(w) == "objekt_code" and w["text"] == "9992"
    )
    if not anchors:
        raise BuildError(f"{code}: no object codes on page {page.page_number}")
    parts: list[dict[str, list[dict[str, Any]]]] = [{n: [] for n in names} for _ in anchors]
    for w in body:
        above = [i for i, top in enumerate(anchors) if top <= w["top"] + 1]
        if not above:
            raise BuildError(f"{code}: text above the first object row: {w['text']!r}")
        parts[above[-1]][column(w)].append(w)
    rows: list[dict[str, str]] = []
    for part in parts:
        cells = dict.fromkeys(names, "")
        for name, found in part.items():
            for w in sorted(found, key=lambda w: (round(w["top"]), w["x0"])):
                cells[name] = join(cells[name], w["text"])
        if not CODE.fullmatch(cells["objekt_code"]):
            raise BuildError(f"{code}: row without one object code: {cells}")
        rows.append(cells)
    return code, rows


def normalise(row: dict[str, str], code: str) -> dict[str, Any]:
    objekt, richtung = row["objekt"], row["richtung"]
    funktion = None
    for name in FUNKTIONEN:
        for text in (objekt, richtung):
            if text.endswith(f"({name})"):
                funktion = name
        objekt = objekt.replace(f"({name})", "").strip()
        richtung = richtung.replace(f"({name})", "").strip()
    if objekt not in OBJEKTE:
        raise BuildError(f"{code}: unknown Objekt {row['objekt']!r}")
    if row["flex"] not in ("Starr", "Flexibel"):
        raise BuildError(f"{code}: unknown Flexibilität {row['flex']!r}")
    if not ANZAHL.match(row["anzahl"]):
        raise BuildError(f"{code}: unknown Anzahl {row['anzahl']!r}")
    if not row["ebene"].isdigit():
        raise BuildError(f"{code}: unknown Ebene {row['ebene']!r}")
    out: dict[str, Any] = {
        "code": compact(row["objekt_code"]),
        "objekt": objekt,
        "funktion": funktion,
        "richtung": None if richtung == "--" else richtung,
        "ebene": int(row["ebene"]),
        "flexibilitaet": row["flex"],
        "anzahl": row["anzahl"],
        "referenz_melo": codes_in(row.get("ref_melo", "")),
        "referenz_nelo": codes_in(row.get("ref_nelo", "")),
    }
    return out


def build(pdf_path: Path) -> dict[str, Any]:
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if digest != SOURCE["sha256"]:
        raise BuildError(f"sha256 {digest} is not the edition {SOURCE['edition']}")
    structures: list[dict[str, Any]] = []
    positions: dict[str, tuple[Any, ...]] = {}
    with pdfplumber.open(pdf_path) as pdf:
        names = overview(pdf)
        for page in pdf.pages[OVERVIEW_PAGE:]:
            clean = clean_page(page)
            if "Änd-ID" in (clean.extract_text() or ""):
                break  # section 5, the change history: no more structures
            found = structure_table(clean)
            if found is None:
                continue
            code, rows = found
            if code not in names or any(s["code"] == code for s in structures):
                raise BuildError(f"{code}: not in the overview, or twice in section 4")
            objects = [normalise(r, code) for r in rows]
            if not objects:
                raise BuildError(f"{code}: no objects")
            for obj in objects:
                key = (obj["objekt"], obj["funktion"], obj["richtung"], obj["ebene"])
                if positions.setdefault(obj["code"], key) != key:
                    raise BuildError(f"{obj['code']}: {key} vs {positions[obj['code']]}")
            structures.append(
                {
                    "code": code,
                    "bezeichnung": names[code],
                    "page": page.page_number,
                    "objects": objects,
                }
            )
    if sorted(s["code"] for s in structures) != sorted(names):
        raise BuildError("section 4 structures differ from the overview")
    return {"source": SOURCE, "structures": structures}


HEADER = """\
# LBS reference data (MKC-12): facts from the BDEW Codeliste der Lokationsbündelstrukturen.
# Only codes, Bezeichnung, page and object composition; never the document itself.
# Built by scripts/build_lbs_yaml.py; source and terms: docs/261120261404-codeliste-research.md.
# Do not edit by hand: rebuild from the PDF named in `source`.
"""


def flow(value: Any) -> str:
    text = str(
        yaml.safe_dump(
            value, allow_unicode=True, sort_keys=False, default_flow_style=True, width=10_000
        )
    ).strip()
    # A bare scalar is dumped as its own document, ending in "...".
    return text.removesuffix("...").strip()


def render(data: dict[str, Any]) -> str:
    """Block style for the file and each structure; one line per object, so a diff shows
    exactly which object changed."""
    head = yaml.safe_dump(
        {"source": data["source"]}, allow_unicode=True, sort_keys=False, width=10_000
    )
    lines = [head.rstrip("\n"), "structures:"]
    for s in data["structures"]:
        lines += [
            f"  - code: {flow(s['code'])}",
            f"    bezeichnung: {flow(s['bezeichnung'])}",
            f"    page: {s['page']}",
            "    objects:",
        ]
        lines += [f"      - {flow(o)}" for o in s["objects"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    # pdfminer warns about colour operators in the diagrams; they do not affect the text.
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    if len(argv) != 3:
        print(__doc__)
        return 2
    try:
        data = build(Path(argv[1]))
    except BuildError as exc:
        print(f"FAIL {exc}")
        return 1
    text = render(data)
    Path(argv[2]).write_text(HEADER + text, encoding="utf-8", newline="\n")
    print(f"ok: {len(data['structures'])} structures -> {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
