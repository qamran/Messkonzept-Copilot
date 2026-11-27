"""Check that the backlog and the status doc show the parallel lanes (MKC-168.5, decision 61).

- Backlog: a section "## Parallel lanes and waves" naming every lane and wave 1
  (MKC-21, MKC-36, MKC-46, MKC-49).
- Status doc: the decision-number blocks of wave 1, per lane.

Usage: python scripts/check_lanes.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = Path("docs/superpowers/plans/241120261500-ticket-backlog.md")
STATUS = Path("docs/241120261430-project-status.md")

LANES = [
    "A. Extraction",
    "A2. SachsenNetze",
    "B. Advisor",
    "C. Decision layer",
    "D. RAG",
]
WAVE_1 = ["MKC-21", "MKC-36", "MKC-46", "MKC-49"]
BLOCKS = {
    "61": "coordinator",
    "62–64": "lane A",
    "65–67": "lane B",
    "68–70": "lane C",
    "71–73": "lane D",
}


def section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def problems(root: Path = ROOT) -> list[str]:
    found: list[str] = []
    backlog = (root / BACKLOG).read_text(encoding="utf-8")
    lanes = section(backlog, "## Parallel lanes and waves")
    if not lanes:
        return ["backlog: missing section '## Parallel lanes and waves'"]
    found += [f"backlog: lane '{lane}' not named" for lane in LANES if lane not in lanes]
    wave = re.search(r"^\*\*Wave 1[^\n]*", lanes, re.M)
    if not wave:
        found.append("backlog: missing the '**Wave 1' line")
    else:
        listed = wave[0].split(";")[0]  # the ticket list, before any note
        found += [f"backlog: wave 1 misses {t}" for t in WAVE_1 if not re.search(rf"{t}\b", listed)]

    status = section((root / STATUS).read_text(encoding="utf-8"), "## Decision numbers per lane")
    if not status:
        return found + ["status doc: missing section '## Decision numbers per lane'"]
    for numbers, owner in BLOCKS.items():
        if not re.search(rf"^\|\s*{numbers}\s*\|\s*{owner}\b", status, re.M | re.I):
            found.append(f"status doc: missing block '{numbers}' for {owner}")
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
