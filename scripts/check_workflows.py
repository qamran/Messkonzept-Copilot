"""Check the GitHub Actions workflows against the CI safety rules (MKC-6.4, AGENTS.md safety rules).

- `.github/workflows/ci.yml` exists and has the jobs backend, frontend, gitleaks,
  dependency-scan and docs.
- No workflow uses `pull_request_target` or secrets (`secrets.x`, `secrets['x']`,
  `secrets: inherit`), so fork PRs get no secrets.
- Every workflow sets top-level `permissions: contents: read` and grants no write
  permission anywhere (`write`, `write-all`), also not per job. One exception (MKC-8.4):
  the job `publish` in `ci.yml` may have `packages: write`, and only with the exact
  job-level guard PUBLISH_GUARD (a push to main in the home repo).
- Every action is pinned to a full commit SHA (docker images to a digest).
- The dependency-scan job audits the frontend packages with `npm audit` (MKC-7.2).
- The image job (MKC-8.3) runs the Compose smoke test, scans the image with Grype
  (`--fail-on high`) and builds `linux/amd64,linux/arm64`.
- No `paths:` / `paths-ignore:` filters: a required check that never runs would block PRs.

Usage: python scripts/check_workflows.py  (exit code 0 = ok, 1 = problems)
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = Path(".github/workflows")
CI = WORKFLOWS / "ci.yml"
REQUIRED_JOBS = ["backend", "frontend", "gitleaks", "dependency-scan", "docs", "image"]
IMAGE_STEPS = {
    "scripts/compose_smoke.sh": "run the Compose smoke test",
    "grype": "scan the image with Grype",
    "--fail-on high": "fail the scan on high or critical (--fail-on high)",
    "linux/amd64,linux/arm64": "build linux/amd64,linux/arm64",
}

USES = re.compile(r"^\s*(?:-\s+)?uses:\s*['\"]?([^\s'\"#]+)", re.MULTILINE)
PINNED_ACTION = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
PINNED_IMAGE = re.compile(r"^docker://.+@sha256:[0-9a-f]{64}$")
TOP_PERMISSIONS = re.compile(r"^permissions:\s*\n\s+contents:\s*read\s*$", re.MULTILINE)
# secrets.X, secrets['X'] and `secrets: inherit` for reusable workflows.
SECRETS = re.compile(r"\bsecrets\s*[.\[]|^\s*secrets:\s*inherit\b", re.MULTILINE)
# Any `<scope>: write` or `permissions: write-all`, top-level or per job.
WRITE_PERMISSION = re.compile(r":\s*write(-all)?\s*$", re.MULTILINE)
PUBLISH_JOB = "publish"
PUBLISH_GUARD = (
    "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    " && github.repository == 'qamran/Messkonzept-Copilot'"
)


def _strip_comments(text: str) -> str:
    return "\n".join(line.split(" #", 1)[0] if not line.lstrip().startswith("#") else ""
                     for line in text.splitlines())


def workflow_problems(path: Path, rel: str) -> list[str]:
    text = _strip_comments(path.read_text(encoding="utf-8"))
    found: list[str] = []
    if "pull_request_target" in text:
        found.append(f"{rel}: uses pull_request_target")
    if SECRETS.search(text):
        found.append(f"{rel}: uses secrets; CI must not need secrets")
    if WRITE_PERMISSION.search(_without_allowed_publish(text, rel)):
        found.append(f"{rel}: grants a write permission; CI is read-only")
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


def _without_allowed_publish(text: str, rel: str) -> str:
    """Drop the one allowed `packages: write` line: in ci.yml's publish job, with the guard."""
    if rel != CI.as_posix():
        return text
    job = job_text(text, PUBLISH_JOB)
    if not re.search(rf"^    if:\s*{re.escape(PUBLISH_GUARD)}\s*$", job, re.MULTILINE):
        return text
    allowed = re.sub(r"^      packages:\s*write\s*$", "", job, count=1, flags=re.MULTILINE)
    # job_text matches on text + newline (the job may end the file without one).
    return (text + "\n").replace(job, allowed, 1)


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
    scan = job_text(ci.read_text(encoding="utf-8"), "dependency-scan")
    if "dependency-scan" in jobs and not re.search(r"\bnpm audit\b", _strip_comments(scan)):
        found.append(f"{CI.as_posix()}: job 'dependency-scan' must run 'npm audit'")
    image = _strip_comments(job_text(ci.read_text(encoding="utf-8"), "image"))
    if "image" in jobs:
        found += [f"{CI.as_posix()}: job 'image' must {what}"
                  for needle, what in IMAGE_STEPS.items() if needle not in image]
    return found


def job_text(text: str, job: str) -> str:
    """The lines of one job, up to the next job at the same indent."""
    pattern = rf"^  {re.escape(job)}:\s*\n((?:    .*\n|\s*\n)*)"
    match = re.search(pattern, text + "\n", re.MULTILINE)
    return match.group(1) if match else ""


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
