"""Check that the runbook's inventory names every external setting and secret (MKC-11.5).

The runbook section "Where every setting and secret lives" is the one place that says,
for each outside service, what is set there, where to find it and how to make it again.
It must name:

- every secret the workflows read (`secrets.<NAME>`, except the built-in GITHUB_TOKEN),
- every key the production values keep in the Kubernetes Secret `mkc-secrets`,
- every `VITE_*` variable the frontend build reads,
- the local-only files that hold keys.

The section "Worker lease and outages" (MKC-17.4) must name every worker timing setting in
`backend/src/mkc/config.py` (`worker_*` and `database_connect_timeout_seconds`) by its
`MKC_` variable.

Usage: python scripts/check_runbook.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = "docs/251120261645-runbook.md"
HEADING = "## Where every setting and secret lives"

SECRET_KEYS = [
    "DATABASE_URL",
    "MKC_BACKUP_UPLOAD_URL",
    # Provider keys (MKC-13): local in backend/.env for the live contract tests.
    "MKC_OPENROUTER_API_KEY",
    "MKC_GOOGLE_API_KEY",
    "MKC_ANTHROPIC_API_KEY",
    "MKC_META_API_KEY",
]
LOCAL_FILES = ["backend/.env", "frontend/.env.local", "~/.ssh/oracle_mkc"]
SERVICES = ["Oracle", "Supabase", "Clerk", "Vercel", "GitHub"]
WORKER_HEADING = "## Worker lease and outages"
CONFIG = "backend/src/mkc/config.py"


def section(text: str, heading: str = HEADING) -> str | None:
    start = text.find(heading + "\n")
    if start < 0:
        return None
    rest = text[start + len(heading) :]
    end = re.search(r"^## ", rest, flags=re.MULTILINE)
    return rest[: end.start()] if end else rest


def required_names(root: Path) -> list[str]:
    names: set[str] = set(SECRET_KEYS) | set(LOCAL_FILES) | set(SERVICES)
    for workflow in sorted((root / ".github" / "workflows").glob("*.yml")):
        found = re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", workflow.read_text(encoding="utf-8"))
        names.update(name for name in found if name != "GITHUB_TOKEN")
    for source in sorted((root / "frontend" / "src").rglob("*.ts*")):
        names.update(re.findall(r"import\.meta\.env\.(VITE_[A-Z0-9_]+)", source.read_text(encoding="utf-8")))
    return sorted(names)


def worker_settings(root: Path) -> list[str]:
    """The `MKC_` names of the worker timing settings, read from the Settings class."""
    source = (root / CONFIG).read_text(encoding="utf-8")
    fields = re.findall(r"^    (worker_\w+|database_connect_timeout_seconds):", source, flags=re.MULTILINE)
    return sorted(f"MKC_{name.upper()}" for name in fields)


def problems(root: Path = ROOT) -> list[str]:
    path = root / RUNBOOK
    if not path.is_file():
        return [f"{RUNBOOK}: file missing"]
    text = path.read_text(encoding="utf-8")
    body = section(text)
    if body is None:
        return [f"{RUNBOOK}: section '{HEADING}' missing"]
    found = [f"{RUNBOOK}: the inventory does not name '{name}'" for name in required_names(root) if name not in body]
    worker = section(text, WORKER_HEADING)
    if worker is None:
        return [*found, f"{RUNBOOK}: section '{WORKER_HEADING}' missing"]
    missing = [name for name in worker_settings(root) if name not in worker]
    return found + [f"{RUNBOOK}: '{WORKER_HEADING}' does not name '{name}'" for name in missing]


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
