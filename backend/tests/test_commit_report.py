"""MKC-168.1: `scripts/commit_report.py` checks subjects and `Refs:` trailers and lists big commits.

Runs against a throwaway git repository, never the project's history.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "scripts" / "commit_report.py"
GOOD_REFS = "Refs: qamran/Messkonzept-Copilot#169"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "tag", "base")
    return tmp_path


def _commit(repo: Path, message: str, lines: int = 1, *flags: str) -> None:
    path = repo / f"f{len(list(repo.glob('f*.txt')))}.txt"
    path.write_text("".join(f"{i}\n" for i in range(lines)), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", *flags, "-m", message)


def _report(repo: Path) -> tuple[int, str]:
    done = subprocess.run(
        [sys.executable, str(REPORT), "base"], cwd=repo, capture_output=True, text=True
    )
    return done.returncode, done.stdout + done.stderr


def test_good_commits_pass(repo: Path) -> None:
    _commit(repo, f"MKC-168: add a\n\nBody.\n\n{GOOD_REFS}\n\nCo-Authored-By: X <x@example.com>")
    # verbatim: without it git strips the carriage returns before the script sees them
    _commit(repo, f"MKC-168.1: add b\r\n\r\n{GOOD_REFS}\r\n", 1, "--cleanup=verbatim")
    raw = subprocess.run(
        ["git", "show", "-s", "--format=%B", "HEAD"], cwd=repo, capture_output=True
    )
    assert b"\r" in raw.stdout
    code, out = _report(repo)
    assert code == 0, out
    assert "2 commits" in out


@pytest.mark.parametrize(
    "message",
    [
        "MKC-168: no trailer\n\nBody.",
        "MKC-168: wrong owner\n\nRefs: qamra/Messkonzept-Copilot#169",
        "MKC-168: wrong repo\n\nRefs: qamran/Other#169",
        "MKC-168: no number\n\nRefs: qamran/Messkonzept-Copilot#",
        "Add a thing\n\n" + GOOD_REFS,
    ],
)
def test_bad_subject_or_trailer_fails(repo: Path, message: str) -> None:
    _commit(repo, message)
    code, out = _report(repo)
    assert code != 0, out
    assert "FAILED" in out


def test_big_commits_are_listed_but_do_not_fail(repo: Path) -> None:
    _commit(repo, f"MKC-168: big\n\n{GOOD_REFS}", lines=201)
    _commit(repo, f"MKC-168: small\n\n{GOOD_REFS}", lines=200)
    code, out = _report(repo)
    assert code == 0, out
    big = _git(repo, "rev-parse", "--short=7", "HEAD~1")
    small = _git(repo, "rev-parse", "--short=7", "HEAD")
    assert f"{big} 201 lines" in out
    assert small not in out.split("over 200 lines", 1)[1]


def test_merge_commits_are_skipped(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, f"MKC-168: side\n\n{GOOD_REFS}")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, f"MKC-168: main\n\n{GOOD_REFS}")
    _git(repo, "merge", "-q", "--no-ff", "side", "-m", "Merge branch 'side'")
    code, out = _report(repo)
    assert code == 0, out
