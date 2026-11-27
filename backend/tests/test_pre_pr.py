"""MKC-168.1: the pre-PR gate (`scripts/pre_pr.sh`) fails when any CI step fails.

The gate runs with stub `uv`, `npx`, `python3` and `bash` on the PATH, so the real suite does
not run inside itself. One case passes `uv run ruff format --check .` through to the real uv
with a mis-formatted probe file in backend/.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "pre_pr.sh"

sys.path.insert(0, str(ROOT / "scripts"))
import check_pre_pr  # noqa: E402


def _git_bash(git: str | None) -> str | None:
    """Git for Windows' bin/bash.exe from its git.exe (cmd/ or mingw64/bin/), never WSL's."""
    if not git:
        return None
    for parent in Path(git).resolve().parents[:3]:
        candidate = parent / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def _bash() -> str | None:
    return _git_bash(shutil.which("git")) if os.name == "nt" else shutil.which("bash")


BASH = _bash()


@pytest.mark.parametrize("git", ["cmd/git.exe", "mingw64/bin/git.exe"])
def test_git_bash_is_found_from_either_git(tmp_path: Path, git: str) -> None:
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "bash.exe").write_bytes(b"")
    (tmp_path / git).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / git).write_bytes(b"")
    assert _git_bash(str(tmp_path / git)) == str((tmp_path / "bin" / "bash.exe").resolve())


needs_bash = pytest.mark.skipif(BASH is None, reason="no POSIX bash (Git Bash on Windows)")

# POSIX sh, so the `bash` stub does not find itself through `env bash`.
STUB = """#!/bin/sh
call="{name} $*"
echo "$call" >> "$STUB_LOG"
if [ -n "${{STUB_FAIL:-}}" ]; then
  case "$call" in *"$STUB_FAIL"*) exit 1 ;; esac
fi
if [ -n "${{REAL_UV:-}}" ] && [ "$call" = "uv run ruff format --check ." ]; then
  exec "$REAL_UV" "$@"
fi
exit 0
"""


@pytest.fixture
def stubs(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("uv", "npx", "python3", "bash"):
        path = bin_dir / name
        path.write_text(STUB.format(name=name), encoding="utf-8", newline="\n")
        path.chmod(0o755)
    return bin_dir


def _run_gate(stubs: Path, **env: str) -> tuple[int, str, list[str]]:
    assert BASH is not None
    log = stubs.parent / "stub.log"
    full_env = {
        **os.environ,
        "STUB_LOG": str(log),
        "STUB_DIR": str(stubs),
        "PRE_PR_SKIP_COMMITS": "1",
        **env,
    }
    # The stubs go first on the PATH inside the shell: Git for Windows' bash.exe launcher
    # puts /usr/bin (with the real bash) ahead of the PATH it was given.
    prepend = (
        'd="$STUB_DIR"; '
        'case "$d" in [A-Za-z]:*) d="$(cygpath -u "$d")" ;; esac; '
        'PATH="$d:$PATH"; export PATH; exec "$BASH" "$0"'
    )
    done = subprocess.run(
        [BASH, "-c", prepend, str(GATE)],
        cwd=ROOT,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return done.returncode, done.stdout + done.stderr, calls


@needs_bash
def test_gate_passes_when_every_step_passes(stubs: Path) -> None:
    code, out, calls = _run_gate(stubs)
    assert code == 0, out
    for expected in (
        "uv sync --locked",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run mypy",
        "uv run pytest -v",
        "bash scripts/test_mkc_deploy.sh",
        "bash scripts/test_cd_deploy.sh",
    ):
        assert expected in calls, (expected, calls)
    assert any(c.startswith("npx --yes markdownlint-cli2@0.18.1") for c in calls), calls
    assert any(c.startswith("python3 scripts/check_") for c in calls), calls


@needs_bash
@pytest.mark.parametrize(
    "failing",
    [
        "uv sync --locked",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run mypy",
        "uv run pytest -v",
        "npx --yes markdownlint-cli2",
        "python3 scripts/check_handoff.py",
        "bash scripts/test_mkc_deploy.sh",
        "bash scripts/test_cd_deploy.sh",
    ],
)
def test_gate_fails_when_one_step_fails(stubs: Path, failing: str) -> None:
    code, out, _ = _run_gate(stubs, STUB_FAIL=failing)
    assert code != 0, out
    assert "FAILED" in out


@needs_bash
def test_gate_fails_on_a_misformatted_file(stubs: Path) -> None:
    real_uv = shutil.which("uv")
    if real_uv is None:
        pytest.skip("uv not on the PATH")
    probe = ROOT / "backend" / "_pre_pr_probe.py"
    probe.write_text("x  =  [1,2 ,3]\n", encoding="utf-8")
    try:
        code, out, _ = _run_gate(stubs, REAL_UV=real_uv)
    finally:
        probe.unlink()
    assert code != 0, out
    assert "_pre_pr_probe.py" in out


def test_check_pre_pr_reports_a_missing_ci_command(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / ".github" / "workflows" / "ci.yml", tmp_path / ".github" / "workflows")
    gate = GATE.read_text(encoding="utf-8").replace("uv run mypy\n", "uv run mypy src\n")
    (tmp_path / "scripts" / "pre_pr.sh").write_text(gate, encoding="utf-8")
    assert check_pre_pr.problems(tmp_path) == ["pre_pr.sh: missing CI backend command: uv run mypy"]
    assert check_pre_pr.problems(ROOT) == []
