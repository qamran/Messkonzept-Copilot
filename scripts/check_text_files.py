"""Every tracked text file is stored with LF line endings and holds no NUL byte.

A NUL byte makes git treat a file as binary: line endings are then not normalised, the file
is stored with CRLF, and ripgrep stops searching it (review of PR #145, finding B1).

Usage:
    python scripts/check_text_files.py          # the files staged in the index
    python scripts/check_text_files.py <rev>    # the files of a commit

Kept bad sample: commit 0c1f966 (a NUL byte and CRLF in the backlog) fails this check.
"""

import subprocess
import sys

TEXT_SUFFIXES = (
    ".md", ".py", ".sh", ".sql", ".yaml", ".yml", ".toml", ".json", ".jsonc",
    ".ts", ".tsx", ".js", ".css", ".html", ".ini", ".cfg", ".txt", ".mako",
)  # fmt: skip
TEXT_NAMES = (".gitignore", ".env.example", "Dockerfile", ".gitattributes")
NUL = b"\x00"
CRLF = b"\r\n"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def tracked_blobs(rev: str | None) -> list[tuple[str, str]]:
    """(path, blob sha) of every tracked file, from the index or from `rev`."""
    if rev is None:
        lines = _git("ls-files", "-s", "-z").split("\0")
        return [(line.split("\t", 1)[1], line.split()[1]) for line in lines if line]
    lines = _git("ls-tree", "-r", "-z", rev).split("\0")
    return [(line.split("\t", 1)[1], line.split()[2]) for line in lines if line]


def is_text(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.endswith(TEXT_SUFFIXES) or name in TEXT_NAMES


def problems(rev: str | None) -> list[str]:
    files = [(path, sha) for path, sha in tracked_blobs(rev) if is_text(path)]
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],
        input="".join(f"{sha}\n" for _, sha in files).encode(),
        capture_output=True,
        check=True,
    ).stdout
    found, offset = [], 0
    for path, _ in files:
        header_end = batch.index(b"\n", offset)
        size = int(batch[offset:header_end].split()[2])
        data = batch[header_end + 1 : header_end + 1 + size]
        offset = header_end + 1 + size + 1
        if NUL in data:
            found.append(f"{path}: NUL byte at offset {data.index(NUL)}")
        if CRLF in data:
            found.append(f"{path}: CRLF line endings ({data.count(CRLF)} lines)")
    return found


def main(argv: list[str]) -> int:
    rev = argv[1] if len(argv) > 1 else None
    found = problems(rev)
    for line in found:
        print(f"check_text_files: {line}")
    if found:
        return 1
    print(f"check_text_files: ok ({rev or 'index'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
