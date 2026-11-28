"""MKC-25: `scripts/check_go_no_go.py` turns the ticket's two docs criteria into a check.

Pinned (assumptions for the coordinator):

- Status doc `docs/241120261430-project-status.md`, section `## Go/no-go vision check
  (MKC-25)`, holds the result table with the header
  `| concept | meters correct | upstream correct | components correct |`, a separator row,
  then exactly 5 rows, one per concept of the truth sheet
  (`backend/data/go_no_go/truth.yaml`, read for its `concept:` values), each cell `yes` or
  `no`.
- The same section has one decision line, `**Decision:** go (the user, dd.MM.yyyy)` or
  `**Decision:** Berlin only (the user, dd.MM.yyyy)`, optionally ending in a full stop. The
  decision is the user's (no threshold is in the design); a placeholder or an unattributed
  decision fails.
- `Berlin only`: design doc section `## 15. Build order` has a line naming both `MKC-25` and
  `Berlin only` (the existing "narrows to Berlin only" line does not count). `go`: no such
  line.
- Like every `scripts/check_*.py`, it runs in CI's `docs` job with plain `python3` (stdlib
  only), so it stays red on the branch until the user's results and decision are in.

The concept numbers below are synthetic; the real five are only in the sheet.
"""

import importlib
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def script() -> ModuleType:
    """Imported per test, so a missing script fails each test instead of the collection."""
    return importlib.import_module("check_go_no_go")


STATUS = Path("docs/241120261430-project-status.md")
DESIGN = Path("docs/superpowers/specs/241120261330-messkonzept-copilot-design.md")
SHEET = Path("backend/data/go_no_go/truth.yaml")
CONCEPTS = ["1", "3", "4.4", "7", "11.1"]
HEADER = "| concept | meters correct | upstream correct | components correct |"
SECTION = "## Go/no-go vision check (MKC-25)"
GO = "**Decision:** go (the user, 28.11.2026)."
BERLIN = "**Decision:** Berlin only (the user, 28.11.2026)."
SECTION_15_LINE = "- **Decided (MKC-25): Berlin only.** SachsenNetze is out of scope.\n"


def sheet_text(concepts: list[str]) -> str:
    entries = "".join(
        f'  - operator: stromnetz-berlin\n    concept: "{c}"\n    page: {8 + i}\n'
        "    meters: null\n    components: null\n"
        for i, c in enumerate(concepts)
    )
    return "concepts:\n" + entries


def table(rows: list[list[str]], header: str = HEADER) -> str:
    lines = [header, "| --- | --- | --- | --- |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def good_rows() -> list[list[str]]:
    return [[c, "yes", "yes" if i % 2 else "no", "yes"] for i, c in enumerate(CONCEPTS)]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for path in (STATUS, DESIGN):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, tmp_path / path)
    (tmp_path / SHEET).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / SHEET).write_text(sheet_text(CONCEPTS), encoding="utf-8")
    return tmp_path


def write_section(root: Path, body: str) -> None:
    path = root / STATUS
    text = path.read_text(encoding="utf-8")
    path.write_text(text.rstrip("\n") + f"\n\n{SECTION}\n\n{body}\n", encoding="utf-8")


def add_to_section_15(root: Path, line: str = SECTION_15_LINE) -> None:
    path = root / DESIGN
    text = path.read_text(encoding="utf-8")
    assert "\n## 16. Risks" in text
    path.write_text(text.replace("\n## 16. Risks", f"{line}\n## 16. Risks", 1), encoding="utf-8")


def problems(root: Path) -> list[str]:
    found: list[str] = script().problems(root)
    return found


def test_the_repo_passes() -> None:
    """Red until the user's results and decision are in (expected on the MKC-25 branch)."""
    assert problems(ROOT) == []


def test_a_go_passes(root: Path) -> None:
    write_section(root, table(good_rows()) + "\n" + GO)
    assert problems(root) == []


def test_berlin_only_with_section_15_passes(root: Path) -> None:
    write_section(root, table(good_rows()) + "\n" + BERLIN)
    add_to_section_15(root)
    assert problems(root) == []


def test_the_real_docs_alone_fail(root: Path) -> None:
    assert problems(root)


def test_a_missing_sheet_fails(root: Path) -> None:
    write_section(root, table(good_rows()) + "\n" + GO)
    (root / SHEET).unlink()
    assert problems(root)


def test_a_table_outside_the_section_does_not_count(root: Path) -> None:
    path = root / STATUS
    text = path.read_text(encoding="utf-8")
    assert "\n## Key documents" in text
    moved = text.replace("\n## Key documents", "\n" + table(good_rows()) + "\n## Key documents")
    path.write_text(moved, encoding="utf-8")
    write_section(root, GO)
    assert problems(root)


@pytest.mark.parametrize(
    "header",
    [
        "| concept | meters | upstream | components |",
        "| concept | meters correct | components correct | upstream correct |",
        "| meters correct | upstream correct | components correct |",
    ],
)
def test_a_wrong_header_fails(root: Path, header: str) -> None:
    write_section(root, table(good_rows(), header) + "\n" + GO)
    assert problems(root)


@pytest.mark.parametrize("n", [4, 6])
def test_not_five_rows_fails(root: Path, n: int) -> None:
    rows = good_rows()
    rows = rows[:n] if n < 5 else [*rows, ["12", "yes", "yes", "yes"]]
    write_section(root, table(rows) + "\n" + GO)
    assert problems(root)


@pytest.mark.parametrize("cell", ["maybe", "", "Yes", "true", "1"])
def test_a_cell_other_than_yes_or_no_fails(root: Path, cell: str) -> None:
    rows = good_rows()
    rows[2][3] = cell
    write_section(root, table(rows) + "\n" + GO)
    assert problems(root)


def test_a_concept_not_on_the_sheet_fails(root: Path) -> None:
    rows = good_rows()
    rows[0][0] = "9.9"
    write_section(root, table(rows) + "\n" + GO)
    assert problems(root)


def test_a_concept_twice_fails(root: Path) -> None:
    rows = good_rows()
    rows[1][0] = rows[0][0]
    write_section(root, table(rows) + "\n" + GO)
    assert problems(root)


@pytest.mark.parametrize(
    "line",
    [
        "",
        "**Decision:** go or Berlin only (the user, 28.11.2026).",
        "**Decision:** go",
        "**Decision:** pending (the user, 28.11.2026).",
        "**Decision:** go (the lane, 28.11.2026).",
        "**Recommendation:** go (lane A, 28.11.2026).",
    ],
    ids=["none", "placeholder", "unattributed", "pending", "not-the-user", "only-a-recommendation"],
)
def test_no_recorded_user_decision_fails(root: Path, line: str) -> None:
    write_section(root, table(good_rows()) + "\n" + line)
    assert problems(root)


def test_two_decisions_fail(root: Path) -> None:
    write_section(root, table(good_rows()) + "\n" + GO + "\n\n" + BERLIN)
    add_to_section_15(root)
    assert problems(root)


def test_a_recommendation_line_beside_the_decision_is_fine(root: Path) -> None:
    write_section(
        root, table(good_rows()) + "\n**Recommendation:** go (lane A, 28.11.2026).\n\n" + GO
    )
    assert problems(root) == []


def test_berlin_only_without_section_15_fails(root: Path) -> None:
    """Section 15 already says "narrows to Berlin only": that line alone does not count."""
    assert "Berlin only" in (root / DESIGN).read_text(encoding="utf-8")
    write_section(root, table(good_rows()) + "\n" + BERLIN)
    assert problems(root)


def test_berlin_only_noted_outside_section_15_fails(root: Path) -> None:
    write_section(root, table(good_rows()) + "\n" + BERLIN)
    path = root / DESIGN
    text = path.read_text(encoding="utf-8")
    after = text.replace("\n## 16. Risks", "\n## 16. Risks\n\n" + SECTION_15_LINE, 1)
    path.write_text(after, encoding="utf-8")
    assert problems(root)


def test_go_with_a_berlin_only_note_in_section_15_fails(root: Path) -> None:
    write_section(root, table(good_rows()) + "\n" + GO)
    add_to_section_15(root)
    assert problems(root)


def test_the_modules_table_passes_the_check(root: Path) -> None:
    """`vision_check.results_table` and this check agree on the table's format."""
    from mkc.extraction.vision_check import compare, results_table

    meters = [{"label": "Z1", "upstream": None}]
    entry = {"operator": "stromnetz-berlin", "page": 8, "meters": meters, "components": []}
    rows = [
        (c, compare(entry | {"concept": c}, {"meters": meters, "components": []})) for c in CONCEPTS
    ]
    write_section(root, results_table(rows) + "\n" + GO)
    assert problems(root) == []
