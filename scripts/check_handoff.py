"""Check that HANDOFF.md exists and has the sections agents rely on after a session restart.

Usage: python scripts/check_handoff.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

SECTIONS = [
    "## Read this first",
    "## Current state",
    "## In progress",
    "## Next steps",
    "## Blocked / waiting on user",
    "## Recent log",
    "## Key links",
]


def problems(root: Path = ROOT) -> list[str]:
    path = root / "HANDOFF.md"
    if not path.is_file():
        return ["HANDOFF.md: file missing"]
    text = path.read_text(encoding="utf-8")
    found = [f"HANDOFF.md: missing section '{s}'" for s in SECTIONS if s not in text]
    if not re.search(r"\*\*Last updated:\*\* \d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}", text):
        found.append("HANDOFF.md: missing '**Last updated:** dd.MM.yyyy, HH:mm'")
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
