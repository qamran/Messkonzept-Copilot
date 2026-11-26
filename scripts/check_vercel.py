"""Check frontend/vercel.json (MKC-10.2).

- Vercel's Git integration must not deploy `main` to production: CD deploys the backend
  first, then the frontend (design doc section 13). Previews for other branches stay on.
- Every path is served by `index.html`, so a reload on `/admin` works (single-page app).
- No `env` or `build.env` block: build values live in the Vercel project, never in the repo.

Usage: python scripts/check_vercel.py  (exit code 0 = ok, 1 = problems)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERCEL_JSON = "frontend/vercel.json"
SPA_REWRITE = {"source": "/(.*)", "destination": "/index.html"}


def problems(root: Path = ROOT) -> list[str]:
    path = root / VERCEL_JSON
    if not path.is_file():
        return [f"{VERCEL_JSON}: file missing"]
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"{VERCEL_JSON}: not valid JSON ({error})"]
    if not isinstance(config, dict):
        return [f"{VERCEL_JSON}: must be a JSON object"]

    found = []
    git = config.get("git")
    enabled = git.get("deploymentEnabled") if isinstance(git, dict) else None
    if not isinstance(enabled, dict) or enabled.get("main") is not False:
        found.append(f"{VERCEL_JSON}: git.deploymentEnabled.main must be false (CD deploys main)")
    elif any(value is False for key, value in enabled.items() if key != "main"):
        found.append(f"{VERCEL_JSON}: only main may be turned off (previews stay on)")
    if SPA_REWRITE not in (config.get("rewrites") or []):
        found.append(f"{VERCEL_JSON}: rewrites must include {json.dumps(SPA_REWRITE)}")
    build = config.get("build")
    if "env" in config or (isinstance(build, dict) and "env" in build):
        found.append(f"{VERCEL_JSON}: no env values in the repo (use the Vercel project)")
    return found


def main() -> int:
    found = problems()
    for problem in found:
        print(problem)
    if not found:
        print(f"{VERCEL_JSON}: ok")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
