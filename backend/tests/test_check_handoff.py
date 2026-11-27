"""MKC-168.2: `scripts/check_handoff.py` checks HANDOFF.md and every lane file."""

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import check_handoff  # noqa: E402


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copy(ROOT / "HANDOFF.md", tmp_path / "HANDOFF.md")
    shutil.copytree(ROOT / "handoff", tmp_path / "handoff")
    for lane in (tmp_path / "handoff").glob("lane-*.md"):
        lane.unlink()
    return tmp_path


def test_the_repo_passes() -> None:
    assert check_handoff.problems(ROOT) == []


def test_no_lane_files_is_valid(root: Path) -> None:
    assert check_handoff.problems(root) == []


def test_a_lane_file_made_from_the_template_passes(root: Path) -> None:
    shutil.copy(root / "handoff" / "TEMPLATE.md", root / "handoff" / "lane-a.md")
    assert check_handoff.problems(root) == []


@pytest.mark.parametrize(
    "drop",
    ["## In progress", "## Next steps", "## Recent log", "**Last updated:** 27.11.2026, 19:20"],
)
def test_a_lane_file_without_a_part_fails(root: Path, drop: str) -> None:
    text = (root / "handoff" / "TEMPLATE.md").read_text(encoding="utf-8")
    text = text.replace("dd.MM.yyyy, HH:mm", "27.11.2026, 19:20")
    assert drop in text
    (root / "handoff" / "lane-b.md").write_text(text.replace(drop, ""), encoding="utf-8")
    found = check_handoff.problems(root)
    assert found and all(p.startswith("handoff/lane-b.md:") for p in found), found


def test_the_template_must_exist(root: Path) -> None:
    (root / "handoff" / "TEMPLATE.md").unlink()
    assert "handoff/TEMPLATE.md: file missing" in check_handoff.problems(root)


def test_handoff_must_list_the_lanes(root: Path) -> None:
    text = (root / "HANDOFF.md").read_text(encoding="utf-8")
    (root / "HANDOFF.md").write_text(text.replace("## Lanes", "## Other"), encoding="utf-8")
    assert "HANDOFF.md: missing section '## Lanes'" in check_handoff.problems(root)
