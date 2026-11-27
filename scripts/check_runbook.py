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

The section "Limits and retries" (MKC-18.4) must name every limit setting (`item_max_steps`,
`run_max_*`, `tool_max_retries`, `model_max_retries`, `model_backoff_*`,
`turn_timeout_seconds`, `item_max_resumes`) by its `MKC_` variable.

The section "Tracing" (MKC-19.4) must name every Langfuse setting (`langfuse_*`) by its
`MKC_` variable; the inventory must name Langfuse and its two keys.

The section "Baseline, faults and the CLI" (MKC-20) must name `MKC_HARNESS_MODE`, the five
baseline switches, the four `mkc run` commands, every fault plan field and the E4 fault file.

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
    # Langfuse keys (MKC-19): local in backend/.env, production in mkc-secrets.
    "MKC_LANGFUSE_PUBLIC_KEY",
    "MKC_LANGFUSE_SECRET_KEY",
]
LOCAL_FILES = ["backend/.env", "frontend/.env.local", "~/.ssh/oracle_mkc"]
SERVICES = ["Oracle", "Supabase", "Clerk", "Vercel", "GitHub", "Langfuse"]
WORKER_HEADING = "## Worker lease and outages"
LIMITS_HEADING = "## Limits and retries"
LIMIT_FIELDS = r"item_max_steps|run_max_\w+|tool_max_retries|model_max_retries|model_backoff_\w+|turn_timeout_seconds|item_max_resumes"
TRACING_HEADING = "## Tracing"
BASELINE_HEADING = "## Baseline, faults and the CLI"
BASELINE_NAMES = [
    "MKC_HARNESS_MODE",
    "checkpoints", "tool_cache", "durable_queue", "idempotency", "durable_approvals",
    "mkc run start", "mkc run resume", "mkc run status", "mkc run inspect",
    "timeout_at", "rate_limit_at", "malformed_at", "kill_at_turn", "kill_during_approval",
    "backend/data/e4_faults.yaml",
]
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


def worker_settings(root: Path, pattern: str = r"worker_\w+|database_connect_timeout_seconds") -> list[str]:
    """The `MKC_` names of the Settings fields that match `pattern`, read from the Settings class."""
    source = (root / CONFIG).read_text(encoding="utf-8")
    fields = re.findall(rf"^    ({pattern}):", source, flags=re.MULTILINE)
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
    found += [f"{RUNBOOK}: '{WORKER_HEADING}' does not name '{name}'" for name in missing]
    limits = section(text, LIMITS_HEADING)
    if limits is None:
        return [*found, f"{RUNBOOK}: section '{LIMITS_HEADING}' missing"]
    settings = worker_settings(root, LIMIT_FIELDS)
    if len(settings) < 10:
        found.append(f"{CONFIG}: expected the 10 limit settings, found {len(settings)}")
    missing = [name for name in settings if name not in limits]
    found += [f"{RUNBOOK}: '{LIMITS_HEADING}' does not name '{name}'" for name in missing]
    tracing = section(text, TRACING_HEADING)
    if tracing is None:
        return [*found, f"{RUNBOOK}: section '{TRACING_HEADING}' missing"]
    settings = worker_settings(root, r"langfuse_\w+")
    if len(settings) < 5:
        found.append(f"{CONFIG}: expected the 5 Langfuse settings, found {len(settings)}")
    missing = [name for name in settings if name not in tracing]
    found += [f"{RUNBOOK}: '{TRACING_HEADING}' does not name '{name}'" for name in missing]
    baseline = section(text, BASELINE_HEADING)
    if baseline is None:
        return [*found, f"{RUNBOOK}: section '{BASELINE_HEADING}' missing"]
    missing = [name for name in BASELINE_NAMES if name not in baseline]
    return found + [f"{RUNBOOK}: '{BASELINE_HEADING}' does not name '{name}'" for name in missing]


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
