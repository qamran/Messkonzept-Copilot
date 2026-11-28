"""Check that the go/no-go vision check (MKC-25, feature 34, design 15) is recorded.

- Status doc, section "## Go/no-go vision check (MKC-25)": the result table with the header
  `| concept | meters correct | upstream correct | components correct |`, exactly one row per
  concept of the truth sheet (`backend/data/go_no_go/truth.yaml`, 5 concepts), each cell
  `yes` or `no`; and one decision line, `**Decision:** go (the user, dd.MM.yyyy)` or
  `**Decision:** Berlin only (the user, dd.MM.yyyy)`. The decision is the user's.
- Berlin only: design doc section "## 15. Build order" has a line naming both `MKC-25` and
  `Berlin only`. go: it has no such line.

Stays red until the user's results and decision are in. Standard library only (CI's `docs`
job runs it with plain python3), so the sheet's `concept:` values are read with a regex.

Usage: python scripts/check_go_no_go.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
STATUS = Path("docs/241120261430-project-status.md")
DESIGN = Path("docs/superpowers/specs/241120261330-messkonzept-copilot-design.md")
SHEET = Path("backend/data/go_no_go/truth.yaml")

SECTION = "## Go/no-go vision check (MKC-25)"
BUILD_ORDER = "## 15. Build order"
HEADER = ["concept", "meters correct", "upstream correct", "components correct"]
CONCEPTS = 5
CELLS = {"yes", "no"}
DECISION = re.compile(r"^\*\*Decision:\*\*(.*)$", re.M)
VALID_DECISION = re.compile(r"^ (go|Berlin only) \(the user, \d{2}\.\d{2}\.\d{4}\)\.?\s*$")
SHEET_CONCEPT = re.compile(r"""^\s*(?:-\s+)?concept:\s*["']?([^"'#\s]+)["']?\s*(?:#.*)?$""", re.M)


def section(text: str, heading: str) -> str:
    match = re.search(rf"^{re.escape(heading)}[ \t]*$", text, re.M)
    if not match:
        return ""
    end = text.find("\n## ", match.end())
    return text[match.start() : end if end != -1 else len(text)]


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_rows(text: str) -> list[list[str]] | None:
    """The rows under the pinned header (separator skipped), or None without the header."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and cells(line) == HEADER:
            rows: list[list[str]] = []
            for row in lines[i + 2 :]:
                if not row.strip().startswith("|"):
                    break
                rows.append(cells(row))
            if i + 1 >= len(lines) or set("".join(cells(lines[i + 1]))) - set("-: "):
                return None
            return rows
    return None


def sheet_concepts(root: Path) -> list[str] | None:
    path = root / SHEET
    if not path.is_file():
        return None
    return SHEET_CONCEPT.findall(path.read_text(encoding="utf-8"))


def problems(root: Path = ROOT) -> list[str]:
    found: list[str] = []
    concepts = sheet_concepts(root)
    if concepts is None:
        found.append(f"{SHEET.as_posix()}: file missing")
    elif len(concepts) != CONCEPTS or len(set(concepts)) != CONCEPTS:
        found.append(f"{SHEET.as_posix()}: needs {CONCEPTS} distinct concepts, has {concepts}")

    status = section((root / STATUS).read_text(encoding="utf-8"), SECTION)
    if not status:
        return found + [f"status doc: missing section '{SECTION}'"]

    rows = table_rows(status)
    if rows is None:
        found.append("status doc: missing the result table header '| " + " | ".join(HEADER) + " |'")
    else:
        if len(rows) != CONCEPTS:
            found.append(f"status doc: the result table needs {CONCEPTS} rows, has {len(rows)}")
        for row in rows:
            if len(row) != len(HEADER):
                found.append(f"status doc: row {row} needs {len(HEADER)} cells")
            elif any(c not in CELLS for c in row[1:]):
                found.append(f"status doc: row {row}: each result cell is 'yes' or 'no'")
        named = [row[0] for row in rows if row]
        if len(set(named)) != len(named):
            found.append(f"status doc: a concept is in the table twice: {named}")
        if concepts is not None and set(named) != set(concepts):
            found.append(f"status doc: table concepts {named} differ from the sheet's {concepts}")

    decisions = DECISION.findall(status)
    decision = None
    if len(decisions) != 1:
        found.append(f"status doc: needs one '**Decision:**' line, has {len(decisions)}")
    else:
        match = VALID_DECISION.match(decisions[0])
        if not match:
            found.append(
                "status doc: the decision must read '**Decision:** go (the user, dd.MM.yyyy)'"
                " or '**Decision:** Berlin only (the user, dd.MM.yyyy)'"
            )
        else:
            decision = match.group(1)

    build_order = section((root / DESIGN).read_text(encoding="utf-8"), BUILD_ORDER)
    noted = any("MKC-25" in line and "Berlin only" in line for line in build_order.splitlines())
    if decision == "Berlin only" and not noted:
        found.append("design doc: section 15 must say 'Berlin only' with MKC-25")
    if decision == "go" and noted:
        found.append("design doc: section 15 says 'Berlin only' for MKC-25, the decision is go")
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
