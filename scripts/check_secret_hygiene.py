"""Check the secret-hygiene files (MKC-6.2, design doc feature 6).

- `.gitignore` ignores PDFs, caches, renders and every `.env*` file, but not `.env.example`.
- `.env.example` lists every environment variable the backend `Settings` reads, with no values.
- `.pre-commit-config.yaml` runs gitleaks, ruff and the end-of-file fixer, each at a pinned rev.

Usage: python scripts/check_secret_hygiene.py  (exit code 0 = ok, 1 = problems)
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MUST_IGNORE = [
    "operator.pdf",
    "docs/scan.PDF",
    "backend/data/messkonzept.pdf",
    ".env",
    "backend/.env",
    ".env.local",
    "backend/.env.production",
    "renders/page-1.png",
    "backend/renders/page-1.png",
    ".cache/x",
    "backend/.venv/x",
    "backend/src/mkc/__pycache__/x.pyc",
    "backend/.pytest_cache/x",
    "backend/.mypy_cache/x",
    "backend/.ruff_cache/x",
    "node_modules/x",
    "frontend/node_modules/x",
    "frontend/dist/x",
]
MUST_TRACK = [".env.example", "backend/.env.example"]

PRE_COMMIT_HOOKS = {
    "https://github.com/gitleaks/gitleaks": "gitleaks",
    "https://github.com/astral-sh/ruff-pre-commit": "ruff-check",
    "https://github.com/pre-commit/pre-commit-hooks": "end-of-file-fixer",
}
UNPINNED_REVS = {"main", "master", "head", "latest", "stable"}


def _ignored(root: Path, path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", path], cwd=root, check=False
    )
    return result.returncode == 0


def gitignore_problems(root: Path = ROOT) -> list[str]:
    found = [f".gitignore: '{p}' is not ignored" for p in MUST_IGNORE if not _ignored(root, p)]
    found += [f".gitignore: '{p}' must not be ignored" for p in MUST_TRACK if _ignored(root, p)]
    return found


def settings_env_names(config: Path) -> set[str]:
    """Environment variable names of the fields of `Settings` in backend/src/mkc/config.py."""
    tree = ast.parse(config.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "Settings"):
            continue
        for stmt in node.body:
            if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
                continue
            field = stmt.target.id
            if field == "model_config":
                continue
            alias = _first_alias(stmt.value)
            names.add(alias or f"MKC_{field.upper()}")
    return names


def _first_alias(value: ast.expr | None) -> str | None:
    if not isinstance(value, ast.Call):
        return None
    for kw in value.keywords:
        if kw.arg != "validation_alias":
            continue
        alias = kw.value
        if isinstance(alias, ast.Constant) and isinstance(alias.value, str):
            return alias.value
        if isinstance(alias, ast.Call) and alias.args:
            first = alias.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return first.value
    return None


def env_example_problems(root: Path = ROOT) -> list[str]:
    path = root / ".env.example"
    if not path.is_file():
        return [".env.example: file missing"]
    listed: set[str] = set()
    found: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(.*)", stripped)
        if not match:
            found.append(f".env.example:{n}: not a NAME= line")
            continue
        name, value = match.groups()
        listed.add(name)
        if value.strip():
            found.append(f".env.example:{n}: {name} has a value; leave it empty")
    expected = settings_env_names(root / "backend" / "src" / "mkc" / "config.py")
    found += [f".env.example: missing {name}" for name in sorted(expected - listed)]
    return found


def pre_commit_problems(root: Path = ROOT) -> list[str]:
    path = root / ".pre-commit-config.yaml"
    if not path.is_file():
        return [".pre-commit-config.yaml: file missing"]
    text = path.read_text(encoding="utf-8")
    found: list[str] = []
    blocks = re.split(r"^\s*-\s+repo:\s*", text, flags=re.MULTILINE)[1:]
    repos = {}
    for block in blocks:
        url = block.split()[0]
        rev = re.search(r"^\s*rev:\s*['\"]?([^\s'\"]+)", block, flags=re.MULTILINE)
        hooks = set(re.findall(r"^\s*-\s+id:\s*([\w-]+)", block, flags=re.MULTILINE))
        repos[url] = (rev.group(1) if rev else None, hooks)
    for url, hook in PRE_COMMIT_HOOKS.items():
        if url not in repos:
            found.append(f".pre-commit-config.yaml: repo {url} missing")
            continue
        rev, hooks = repos[url]
        if not rev or rev.lower() in UNPINNED_REVS:
            found.append(f".pre-commit-config.yaml: {url} needs a pinned rev, got {rev!r}")
        if hook not in hooks:
            found.append(f".pre-commit-config.yaml: hook '{hook}' missing in {url}")
    return found


def problems(root: Path = ROOT) -> list[str]:
    return gitignore_problems(root) + env_example_problems(root) + pre_commit_problems(root)


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
