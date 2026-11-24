"""Check that the issue and PR templates contain the ticket format required by ADR 005.

Usage: python scripts/check_templates.py  (exit code 0 = ok, 1 = missing parts)
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = {
    ".github/ISSUE_TEMPLATE/ticket.md": [
        "Key:",
        "Phase:",
        "Goal:",
        "Scope:",
        "Depends on:",
        "Interfaces:",
        "Test:",
        "Success criteria",
    ],
    ".github/ISSUE_TEMPLATE/config.yml": ["blank_issues_enabled: false"],
    ".github/pull_request_template.md": [
        "MKC-",
        "Closes #",
        "Success criteria",
        "Test evidence",
        "Docs updated",
    ],
}


def missing_parts(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for rel, needles in REQUIRED.items():
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: file missing")
            continue
        text = path.read_text(encoding="utf-8")
        problems += [f"{rel}: missing '{n}'" for n in needles if n not in text]
    return problems


if __name__ == "__main__":
    found = missing_parts()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
