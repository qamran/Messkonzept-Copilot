"""Check the branch's commits before a PR (MKC-168.1): subject, `Refs:` trailer, size.

- Subject: `MKC-<n>: <summary>` or `MKC-<n>.<m>: <summary>`.
- Body: a line `Refs: qamran/Messkonzept-Copilot#<issue>`, and no other `Refs:` line.
  The body is searched as text: a blank line before `Co-Authored-By:` stops git from
  parsing `Refs` as a trailer (MKC-15 finding 11). Carriage returns are stripped first.
- Size: commits over 200 lines (insertions plus deletions) are listed, not failed.
Merge commits are skipped.

Usage: python scripts/commit_report.py [BASE]   (default origin/main; exit 1 = a bad commit)
"""

import re
import subprocess
import sys

SUBJECT = re.compile(r"^MKC-\d+(\.\d+)?: \S")
REFS = re.compile(r"^Refs: qamran/Messkonzept-Copilot#\d+$")
MAX_LINES = 200


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return done.stdout


def size(sha: str) -> int:
    total = 0
    for line in git("show", "--numstat", "--format=", sha).splitlines():
        added, deleted, _ = line.split("\t", 2)
        if added != "-":  # binary files count as 0
            total += int(added) + int(deleted)
    return total


def report(base: str) -> tuple[list[str], list[str]]:
    """(problems, big commits) for the non-merge commits in base..HEAD."""
    problems: list[str] = []
    big: list[str] = []
    shas = git("rev-list", "--no-merges", "--reverse", f"{base}..HEAD").split()
    for sha in shas:
        short = sha[:7]
        message = git("show", "-s", "--format=%B", sha).replace("\r", "")
        lines = message.splitlines()
        subject = lines[0] if lines else ""
        if not SUBJECT.match(subject):
            problems.append(f"{short} subject is not 'MKC-<n>: <summary>': {subject!r}")
        refs = [line.strip() for line in lines[1:] if line.strip().startswith("Refs:")]
        if not refs:
            problems.append(f"{short} has no 'Refs: qamran/Messkonzept-Copilot#<issue>' line")
        problems += [f"{short} bad trailer: {r!r}" for r in refs if not REFS.match(r)]
        lines_changed = size(sha)
        if lines_changed > MAX_LINES:
            big.append(f"{short} {lines_changed} lines  {subject}")
    print(f"{len(shas)} commits in {base}..HEAD (merges skipped)")
    return problems, big


def main(argv: list[str]) -> int:
    base = argv[1] if len(argv) > 1 else "origin/main"
    problems, big = report(base)
    print(f"Commits over {MAX_LINES} lines (insertions plus deletions; disclose in the PR):")
    for line in big or ["none"]:
        print(f"  {line}")
    for p in problems:
        print(f"FAILED: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
