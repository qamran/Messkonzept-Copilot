"""MKC-24 user task "the first Berlin gold batch verified; hours logged in the status doc":
`scripts/check_gold.py` (lane A2).

Pinned format. In `docs/241120261430-project-status.md`, the section whose `## ` heading
starts with `## Lane A2` and names `MKC-24` holds this line:

    - **Berlin gold batch 1:** <N> concepts verified, <H> h of the user's time

N is a whole number of at least 1; H is a number above 0 with a dot as decimal mark (`2.5`).
More text may follow on the line. `problems(root) -> list[str]` is empty when the line is
there; the script exits 1 otherwise. It stays red until the user has verified the batch.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

STATUS = Path("docs/241120261430-project-status.md")
HEADING = "## Lane A2: SachsenNetze (MKC-27) and gold tooling (MKC-24)"
GOOD = "- **Berlin gold batch 1:** 12 concepts verified, 2.5 h of the user's time (E1)."


def problems(root: Path) -> list[str]:
    import check_gold

    found = check_gold.problems(root)
    assert isinstance(found, list)
    return found


def status(tmp_path: Path, *sections: str) -> Path:
    path = tmp_path / STATUS
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(("# Project status", "## Where we are\n\n- something", *sections))
    path.write_text(body + "\n", encoding="utf-8")
    return tmp_path


def lane_a2(*lines: str) -> str:
    return "\n".join((HEADING, "", "- **State:** in progress", *lines))


def test_the_repo_passes() -> None:
    assert problems(ROOT) == []


def test_the_line_in_the_lane_a2_section_passes(tmp_path: Path) -> None:
    assert problems(status(tmp_path, lane_a2(GOOD), "## Open items\n\n- none")) == []


def test_a_whole_number_of_hours_passes(tmp_path: Path) -> None:
    line = "- **Berlin gold batch 1:** 3 concepts verified, 1 h of the user's time"
    assert problems(status(tmp_path, lane_a2(line))) == []


def test_no_mkc_24_section_fails(tmp_path: Path) -> None:
    assert problems(status(tmp_path, "## Lane D: RAG (MKC-49)\n\n" + GOOD))


def test_a_lane_a2_section_without_mkc_24_fails(tmp_path: Path) -> None:
    section = "## Lane A2: SachsenNetze segmentation (MKC-27)\n\n" + GOOD
    assert problems(status(tmp_path, section))


def test_the_line_in_another_section_fails(tmp_path: Path) -> None:
    assert problems(status(tmp_path, lane_a2(), "## Open items\n\n" + GOOD))


def test_a_section_without_the_line_fails(tmp_path: Path) -> None:
    found = problems(status(tmp_path, lane_a2("- **LLM spend (MKC-24):** EUR 0.10")))
    assert found
    assert any("Berlin gold batch 1" in p for p in found)


@pytest.mark.parametrize(
    "line",
    [
        "- **Berlin gold batch 1:** 0 concepts verified, 2.5 h of the user's time",
        "- **Berlin gold batch 1:** 12 concepts verified, 0 h of the user's time",
        "- **Berlin gold batch 1:** 12 concepts verified, 0.0 h of the user's time",
        "- **Berlin gold batch 1:** <N> concepts verified, <H> h of the user's time",
        "- **Berlin gold batch 1:** 12 concepts verified, 2,5 h of the user's time",
        "- **Berlin gold batch 1:** 12 concepts verified",
        "- Berlin gold batch 1: 12 concepts verified, 2.5 h of the user's time",
    ],
    ids=["no-concepts", "no-hours", "zero-hours", "placeholder", "comma", "no-hours-part", "plain"],
)
def test_an_incomplete_line_fails(tmp_path: Path, line: str) -> None:
    assert problems(status(tmp_path, lane_a2(line)))


def test_the_script_exits_1_on_problems(tmp_path: Path) -> None:
    import subprocess

    script = ROOT / "scripts" / "check_gold.py"
    assert script.is_file()
    result = subprocess.run(
        [sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == (1 if problems(ROOT) else 0), result.stdout + result.stderr
