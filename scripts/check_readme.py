"""Check that README.md links to the places reviewers of either repo need (ADR 005, option (c)).

The Turing repo is a code-only mirror with no issues, so the README must point to the
home repo's board and issue list, plus the design doc, the ADRs and HANDOFF.md.

Usage: python scripts/check_readme.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_LINKS = [
    "https://github.com/users/qamran/projects/1",
    "https://github.com/qamran/Messkonzept-Copilot/issues",
    "docs/superpowers/specs/241120261330-messkonzept-copilot-design.md",
    "docs/adr/",
    "HANDOFF.md",
]


def problems(root: Path = ROOT) -> list[str]:
    path = root / "README.md"
    if not path.is_file():
        return ["README.md: file missing"]
    text = path.read_text(encoding="utf-8")
    found = [f"README.md: missing link '{link}'" for link in REQUIRED_LINKS if f"]({link})" not in text]
    for rel in REQUIRED_LINKS[2:]:
        if not (root / rel).exists():
            found.append(f"README.md: link target '{rel}' does not exist")
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
