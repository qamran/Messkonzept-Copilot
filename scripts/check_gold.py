"""Check the MKC-24 user task: the first Berlin gold batch is verified and its hours are
logged in the status doc (design 11.2).

The status doc's section whose `## ` heading starts with `## Lane A2` and names `MKC-24`
must hold the line

    - **Berlin gold batch 1:** <N> concepts verified, <H> h of the user's time

with N a whole number of at least 1 and H a number above 0 (dot as decimal mark). More
text may follow. Red until the user has verified the batch.

Usage: python scripts/check_gold.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
STATUS = Path("docs/241120261430-project-status.md")
LINE = "- **Berlin gold batch 1:** <N> concepts verified, <H> h of the user's time"
PATTERN = re.compile(
    r"^- \*\*Berlin gold batch 1:\*\* (\d+) concepts verified, (\d+(?:\.\d+)?) h of the "
    r"user's time(?:\W|$)"
)


def _section(text: str) -> list[str] | None:
    """The lines of the Lane A2 MKC-24 section, or None."""
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if line.startswith("## Lane A2") and "MKC-24" in line:
            body = []
            for following in lines[start + 1 :]:
                if following.startswith("## "):
                    break
                body.append(following)
            return body
    return None


def problems(root: Path = ROOT) -> list[str]:
    path = root / STATUS
    if not path.is_file():
        return [f"{STATUS}: file missing"]
    body = _section(path.read_text(encoding="utf-8"))
    if body is None:
        return [f"{STATUS}: no '## Lane A2 ...' section that names MKC-24"]
    for line in body:
        match = PATTERN.match(line)
        if match and int(match.group(1)) >= 1 and float(match.group(2)) > 0:
            return []
    return [f"{STATUS}: the Lane A2 MKC-24 section needs '{LINE}' (N >= 1, H > 0)"]


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
