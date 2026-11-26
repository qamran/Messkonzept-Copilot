"""Check that AGENTS.md holds the project rules and CLAUDE.md is one line pointing to it (MKC-3).

Usage: python scripts/check_agents.py  (exit code 0 = ok, 1 = problems)
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

SECTIONS = [
    "## Project purpose",
    "## Roles",
    "## Ticket flow",
    "## Commits",
    "## Tests first",
    "## Docs stay current",
    "## Data rules",
    "## Model rules",
    "## Safety rules",
    "## Review agent checklist",
]

# Rules that must be stated somewhere in AGENTS.md (case-insensitive).
TERMS = [
    "Opus 5.5",
    "Fable",
    "HANDOFF.md",
    "qamran",
    "MKC-<n>: <summary>",
    "Refs: qamran/Messkonzept-Copilot#",
    "200 lines",
    "mako",
    "PDF",
    "synthetic",
    "ModelClient",
    "zero-data-retention",
    "side-effect",
    "pending_deployments",  # the development agent approves the deploy gates (decision 51)
]

# The review agent checklist must cover these (case-insensitive), inside its section.
CHECKLIST = [
    "success criteria",
    "tests prove",
    "global constraints",
    "docs updated",
    "no secrets",
]


def problems(root: Path = ROOT) -> list[str]:
    found: list[str] = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        found.append("AGENTS.md: file missing")
    else:
        text = agents.read_text(encoding="utf-8")
        lower = text.lower()
        found += [f"AGENTS.md: missing section '{s}'" for s in SECTIONS if s not in text]
        found += [f"AGENTS.md: missing rule term '{t}'" for t in TERMS if t.lower() not in lower]
        start = text.find("## Review agent checklist")
        if start != -1:
            end = text.find("\n## ", start + 1)
            section = text[start : end if end != -1 else len(text)].lower()
            found += [f"AGENTS.md: review checklist missing '{c}'" for c in CHECKLIST if c not in section]

    claude = root / "CLAUDE.md"
    if not claude.is_file():
        found.append("CLAUDE.md: file missing")
    else:
        lines = [l for l in claude.read_text(encoding="utf-8").splitlines() if l.strip()]
        if len(lines) != 1:
            found.append(f"CLAUDE.md: expected exactly one line, found {len(lines)}")
        if not any("AGENTS.md" in l for l in lines):
            found.append("CLAUDE.md: does not point to AGENTS.md")
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
