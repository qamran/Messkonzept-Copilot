"""Check the container files against the MKC-8 rules.

- `backend/Dockerfile` is multi-stage, pins every base image by digest, runs as a
  numeric non-root user, takes the build argument `MKC_COMMIT` and sets it as env,
  and uses exec-form commands (so SIGTERM reaches the process).
- `backend/.dockerignore` keeps `.env*`, `.venv`, caches and tests out of the build context.
- `compose.yaml` has the services db, api, worker and frontend, and is the only Compose file.
- `frontend/Dockerfile` pins its base images by digest and runs as non-root;
  `frontend/.dockerignore` keeps `.env*` and `node_modules` out.

Standard library only (CI runs it with bare python3).

Usage: python scripts/check_containers.py  (exit code 0 = ok, 1 = problems)
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DOCKERFILE = Path("backend/Dockerfile")
BACKEND_DOCKERIGNORE = Path("backend/.dockerignore")
FRONTEND_DOCKERFILE = Path("frontend/Dockerfile")
FRONTEND_DOCKERIGNORE = Path("frontend/.dockerignore")
COMPOSE = Path("compose.yaml")
OLD_COMPOSE = ["docker-compose.yml", "docker-compose.yaml", "compose.yml"]
SERVICES = ["db", "api", "worker", "frontend"]

FROM = re.compile(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+\S+)?\s*$", re.I | re.M)
PINNED = re.compile(r"@sha256:[0-9a-f]{64}$")
COPY_FROM_IMAGE = re.compile(r"^COPY\s+--from=(\S+)", re.I | re.M)
USER = re.compile(r"^USER\s+(\S+)\s*$", re.I | re.M)
SHELL_FORM = re.compile(r"^(CMD|ENTRYPOINT)\s+[^\[\s]", re.I | re.M)


def _lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _base_problems(rel: str, text: str, min_stages: int) -> list[str]:
    found: list[str] = []
    images = FROM.findall(text)
    stage_names = set(re.findall(r"^FROM\s+.*\s+AS\s+(\S+)\s*$", text, re.I | re.M))
    if len(images) < min_stages:
        found.append(f"{rel}: needs a multi-stage build ({min_stages}+ FROM lines)")
    for image in images + COPY_FROM_IMAGE.findall(text):
        if image in stage_names:
            continue
        if not PINNED.search(image):
            found.append(f"{rel}: image '{image}' is not pinned by digest")
    users = USER.findall(text)
    if not users:
        found.append(f"{rel}: no USER; the image must not run as root")
    elif not re.fullmatch(r"[1-9]\d*(:\d+)?", users[-1]):
        found.append(f"{rel}: last USER '{users[-1]}' must be a numeric non-root uid")
    if SHELL_FORM.search(text):
        found.append(f"{rel}: CMD/ENTRYPOINT must use exec form ([\"...\"])")
    return found


def _ignore_problems(rel: str, path: Path, required: list[str]) -> list[str]:
    if not path.is_file():
        return [f"{rel}: file missing"]
    entries = {line.strip().rstrip("/") for line in path.read_text(encoding="utf-8").splitlines()}
    return [f"{rel}: must ignore '{entry}'" for entry in required if entry not in entries]


def backend_problems(root: Path) -> list[str]:
    rel = BACKEND_DOCKERFILE.as_posix()
    path = root / BACKEND_DOCKERFILE
    if not path.is_file():
        return [f"{rel}: file missing"]
    text = _lines(path.read_text(encoding="utf-8"))
    found = _base_problems(rel, text, min_stages=2)
    if not re.search(r"^ARG\s+MKC_COMMIT\b", text, re.M):
        found.append(f"{rel}: needs 'ARG MKC_COMMIT'")
    if not re.search(r"^ENV\s+.*\bMKC_COMMIT=\$\{?MKC_COMMIT\}?", text, re.M):
        found.append(f"{rel}: needs 'ENV MKC_COMMIT=${{MKC_COMMIT}}'")
    found += _ignore_problems(
        BACKEND_DOCKERIGNORE.as_posix(),
        root / BACKEND_DOCKERIGNORE,
        [".env", ".env.*", ".venv", "tests", "**/__pycache__", ".pytest_cache", ".mypy_cache"],
    )
    return found


def frontend_problems(root: Path) -> list[str]:
    rel = FRONTEND_DOCKERFILE.as_posix()
    path = root / FRONTEND_DOCKERFILE
    if not path.is_file():
        return [f"{rel}: file missing"]
    found = _base_problems(rel, _lines(path.read_text(encoding="utf-8")), min_stages=2)
    found += _ignore_problems(
        FRONTEND_DOCKERIGNORE.as_posix(),
        root / FRONTEND_DOCKERIGNORE,
        [".env", ".env.*", "node_modules", "dist"],
    )
    return found


def compose_problems(root: Path) -> list[str]:
    found = [f"{old}: replaced by {COMPOSE}; keep one Compose file" for old in OLD_COMPOSE
             if (root / old).exists()]
    path = root / COMPOSE
    if not path.is_file():
        return [*found, f"{COMPOSE}: file missing"]
    text = path.read_text(encoding="utf-8")
    block = re.search(r"^services:\s*\n((?:[ \t].*\n|\s*\n)*)", text + "\n", re.M)
    services = set(re.findall(r"^  ([\w-]+):", block.group(1), re.M)) if block else set()
    found += [f"{COMPOSE}: service '{s}' missing" for s in SERVICES if s not in services]
    return found


def problems(root: Path = ROOT) -> list[str]:
    return backend_problems(root) + frontend_problems(root) + compose_problems(root)


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
