"""Check the GitHub Actions workflows against the CI safety rules (MKC-6.4, AGENTS.md safety rules).

- `.github/workflows/ci.yml` exists and has the jobs backend, frontend, gitleaks,
  dependency-scan and docs.
- No workflow uses `pull_request_target` or reads `secrets.` (fork PRs get no secrets).
- Every workflow sets top-level `permissions: contents: read`.
- Every action is pinned to a full commit SHA (docker images to a digest).
- No `paths:` / `paths-ignore:` filters: a required check that never runs would block PRs.

Usage: python scripts/check_workflows.py  (exit code 0 = ok, 1 = problems)
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = Path(".github/workflows")
CI = WORKFLOWS / "ci.yml"
REQUIRED_JOBS = ["backend", "frontend", "gitleaks", "dependency-scan", "docs"]

USES = re.compile(r"^\s*(?:-\s+)?uses:\s*['\"]?([^\s'\"#]+)", re.MULTILINE)
PINNED_ACTION = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
PINNED_IMAGE = re.compile(r"^docker://.+@sha256:[0-9a-f]{64}$")
TOP_PERMISSIONS = re.compile(r"^permissions:\s*\n\s+contents:\s*read\s*$", re.MULTILINE)


def _strip_comments(text: str) -> str:
    return "\n".join(line.split(" #", 1)[0] if not line.lstrip().startswith("#") else ""
                     for line in text.splitlines())


def workflow_problems(path: Path, rel: str) -> list[str]:
    text = _strip_comments(path.read_text(encoding="utf-8"))
    found: list[str] = []
    if "pull_request_target" in text:
        found.append(f"{rel}: uses pull_request_target")
    if re.search(r"\bsecrets\.", text):
        found.append(f"{rel}: reads secrets.*; CI must not need secrets")
    if re.search(r"^\s*paths(-ignore)?:", text, re.MULTILINE):
        found.append(f"{rel}: has a paths filter; required checks must always run")
    if not TOP_PERMISSIONS.search(text):
        found.append(f"{rel}: needs top-level 'permissions:' with 'contents: read'")
    for ref in USES.findall(text):
        if ref.startswith("./"):
            continue
        if not (PINNED_ACTION.match(ref) or PINNED_IMAGE.match(ref)):
            found.append(f"{rel}: '{ref}' is not pinned to a commit SHA or digest")
    return found


def ci_jobs(text: str) -> set[str]:
    jobs = re.search(r"^jobs:\s*\n((?:[ \t].*\n|\s*\n)*)", text + "\n", re.MULTILINE)
    if not jobs:
        return set()
    return set(re.findall(r"^  ([\w-]+):", jobs.group(1), re.MULTILINE))


def problems(root: Path = ROOT) -> list[str]:
    ci = root / CI
    if not ci.is_file():
        return [f"{CI.as_posix()}: file missing"]
    found: list[str] = []
    for path in sorted((root / WORKFLOWS).glob("*.y*ml")):
        found += workflow_problems(path, path.relative_to(root).as_posix())
    jobs = ci_jobs(ci.read_text(encoding="utf-8"))
    found += [f"{CI.as_posix()}: job '{job}' missing" for job in REQUIRED_JOBS if job not in jobs]
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
