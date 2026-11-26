"""Check the Codeliste research note (MKC-12.1).

The note records which edition of the BDEW "Codeliste der Lokationsbündelstrukturen" the
repo's LBS data comes from, where it was found, its format and licence terms, what may be
committed, and how the check digit works. Exactly one note must exist in docs/, named
`<ddMMyyyyHHmm>-codeliste-research.md`, with these headings and facts.

Usage: python scripts/check_codeliste_note.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"^\d{12}-codeliste-research\.md$")
HEADINGS = [
    "## Version",
    "## Source",
    "## Format",
    "## Licence and terms",
    "## What may be committed",
    "## Check digit",
]
# The edition the data comes from, and that the note links its sources.
FACTS = ["13.12.2024", "https://"]


def problems(root: Path) -> list[str]:
    notes = sorted(p for p in (root / "docs").glob("*.md") if NAME.match(p.name))
    if not notes:
        return ["no research note docs/<ddMMyyyyHHmm>-codeliste-research.md"]
    if len(notes) > 1:
        return [f"more than one research note: {[p.name for p in notes]}"]
    text = notes[0].read_text(encoding="utf-8")
    lines = set(text.splitlines())
    found = [f"{notes[0].name}: heading missing: {h}" for h in HEADINGS if h not in lines]
    found += [f"{notes[0].name}: missing: {f}" for f in FACTS if f not in text]
    return found


def main() -> int:
    found = problems(ROOT)
    for problem in found:
        print(f"FAIL {problem}")
    if not found:
        print("ok: Codeliste research note")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
