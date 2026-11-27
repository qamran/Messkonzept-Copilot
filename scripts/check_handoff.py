"""Check HANDOFF.md and the lane handoff files that agents rely on after a session restart.

- HANDOFF.md (the coordinator's file): its sections and `**Last updated:**`.
- handoff/TEMPLATE.md and every handoff/lane-*.md (MKC-168.2, decision 61): a
  `**Last updated:**` line and the sections In progress, Next steps and Recent log.
  No lane files is valid (no lane running).

Usage: python scripts/check_handoff.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

SECTIONS = [
    "## Read this first",
    "## Current state",
    "## Lanes",
    "## In progress",
    "## Next steps",
    "## Blocked / waiting on user",
    "## Recent log",
    "## Key links",
]

LANE_SECTIONS = [
    "## In progress",
    "## Next steps",
    "## Recent log",
]

LAST_UPDATED = re.compile(r"\*\*Last updated:\*\* \d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}")


def _check(path: Path, name: str, sections: list[str]) -> list[str]:
    if not path.is_file():
        return [f"{name}: file missing"]
    text = path.read_text(encoding="utf-8")
    found = [f"{name}: missing section '{s}'" for s in sections if s not in text]
    if not LAST_UPDATED.search(text):
        found.append(f"{name}: missing '**Last updated:** dd.MM.yyyy, HH:mm'")
    return found


def problems(root: Path = ROOT) -> list[str]:
    found = _check(root / "HANDOFF.md", "HANDOFF.md", SECTIONS)
    found += _check(root / "handoff" / "TEMPLATE.md", "handoff/TEMPLATE.md", LANE_SECTIONS)
    for lane in sorted((root / "handoff").glob("lane-*.md")):
        found += _check(lane, f"handoff/{lane.name}", LANE_SECTIONS)
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
