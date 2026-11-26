"""Check that the runbook's inventory names every external setting and secret (MKC-11.5).

The runbook section "Where every setting and secret lives" is the one place that says,
for each outside service, what is set there, where to find it and how to make it again.
It must name:

- every secret the workflows read (`secrets.<NAME>`, except the built-in GITHUB_TOKEN),
- every key the production values keep in the Kubernetes Secret `mkc-secrets`,
- every `VITE_*` variable the frontend build reads,
- the local-only files that hold keys.

Usage: python scripts/check_runbook.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = "docs/251120261645-runbook.md"
HEADING = "## Where every setting and secret lives"

SECRET_KEYS = ["DATABASE_URL", "MKC_BACKUP_UPLOAD_URL"]
LOCAL_FILES = ["backend/.env", "frontend/.env.local", "~/.ssh/oracle_mkc"]
SERVICES = ["Oracle", "Supabase", "Clerk", "Vercel", "GitHub"]


def section(text: str) -> str | None:
    start = text.find(HEADING + "\n")
    if start < 0:
        return None
    rest = text[start + len(HEADING) :]
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


def problems(root: Path = ROOT) -> list[str]:
    path = root / RUNBOOK
    if not path.is_file():
        return [f"{RUNBOOK}: file missing"]
    body = section(path.read_text(encoding="utf-8"))
    if body is None:
        return [f"{RUNBOOK}: section '{HEADING}' missing"]
    return [f"{RUNBOOK}: the inventory does not name '{name}'" for name in required_names(root) if name not in body]


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
