"""Check that scripts/pre_pr.sh runs exactly CI's `backend` and `docs` commands (MKC-168.1).

Every command line of every `run:` step in the `backend` and `docs` jobs of
.github/workflows/ci.yml must appear, as a whole line, in scripts/pre_pr.sh. Only the
environment may differ from CI (database port, the python3 shim), never the commands.

Usage: python scripts/check_pre_pr.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
JOBS = ("backend", "docs")


def job_block(workflow: str, job: str) -> str:
    """The text of one job under `jobs:` (two-space indent), up to the next job."""
    match = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow, re.M | re.S)
    return match.group(1) if match else ""


def run_commands(block: str) -> list[str]:
    """Each command line of the `run:` steps of a job, without comments and blank lines."""
    commands: list[str] = []
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        match = re.match(r"^(\s*)(?:- )?run: ?(.*)$", lines[i])
        i += 1
        if not match:
            continue
        indent, rest = len(match.group(1)), match.group(2).strip()
        if not rest:  # `defaults: run:` is a mapping, not a step
            continue
        if rest not in ("|", ">", "|-", ">-"):
            commands.append(rest)
            continue
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
            line = lines[i].strip()
            i += 1
            if line and not line.startswith("#"):
                commands.append(line)
    return commands


def problems(root: Path = ROOT) -> list[str]:
    workflow_path = root / ".github" / "workflows" / "ci.yml"
    gate_path = root / "scripts" / "pre_pr.sh"
    if not workflow_path.is_file():
        return ["ci.yml: file missing"]
    if not gate_path.is_file():
        return ["scripts/pre_pr.sh: file missing"]
    workflow = workflow_path.read_text(encoding="utf-8")
    gate_lines = {line.strip() for line in gate_path.read_text(encoding="utf-8").splitlines()}
    found: list[str] = []
    for job in JOBS:
        commands = run_commands(job_block(workflow, job))
        if not commands:
            found.append(f"ci.yml: job '{job}' has no run commands (parser out of date?)")
        found += [f"pre_pr.sh: missing CI {job} command: {c}" for c in commands if c not in gate_lines]
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
