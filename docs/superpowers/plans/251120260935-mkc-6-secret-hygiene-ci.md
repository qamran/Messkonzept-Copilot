# MKC-6 plan: secret hygiene and CI

**Ticket:** MKC-6 (#6). **Branch:** `mkc-6-secret-hygiene-ci`.

**Goal:** every PR is linted, typed, tested and scanned, with no secrets reachable from fork PRs.

## Sub-issues

| Key | Issue | What |
|---|---|---|
| MKC-6.1 | #81 | `httpx` → `httpx2` for the test client; `StarletteDeprecationWarning` is an error |
| MKC-6.2 | #82 | `.gitignore`, `.env.example`, `.pre-commit-config.yaml`, `scripts/check_secret_hygiene.py` |
| MKC-6.3 | #83 | all tracked Markdown passes markdownlint |
| MKC-6.4 | #84 | `.github/workflows/ci.yml`, `scripts/check_workflows.py` |
| MKC-6.5 | #85 | CI jobs as required checks on `main` |

## Checked before starting (25.11.2026)

- **gitleaks v8.30.1 over the full history:** 62 commits, no leaks. No allowlist needed. The compose `mkc:mkc` URLs and the `secret-pw` test string are not flagged.
- **Fake key:** a GitHub token pattern (`ghp_` + 36 random characters), built at runtime, is flagged (exit 1). The pattern is never written into a committed file, so neither our own scan nor GitHub push protection sees it.
- **`httpx2`:** Starlette 1.10 imports `httpx2` first and falls back to `httpx` with a `StarletteDeprecationWarning`. `httpx2` 2.16.2 on PyPI comes from the pydantic org (author Tom Christie, who wrote `httpx` and Starlette).
- **Token scope:** the `gh` token has the `workflow` scope, so pushes with `.github/workflows/` work on both remotes.
- **markdownlint-cli2 0.18.1 on tracked Markdown:** about 270 errors, mostly missing blank lines (MD022, MD032), the design doc's running feature numbers (MD029), HTML comments in the GitHub templates (MD033), bare URLs (MD034) and code fences without a language (MD040).

## Design choices

- **No `paths:` filters** on `ci.yml`. A required check that never reports would block docs-only PRs forever.
- **Frontend job reports success while `frontend/` doesn't exist.** The condition is on the steps, not on the job, so the check always reports. MKC-7 turns it on.
- **gitleaks as the release binary, pinned by version and checksum,** not the gitleaks GitHub Action. No token is passed, and the scan covers the full history (`fetch-depth: 0`).
- **Dependency scan:** `pip-audit` over `uv export --frozen` (backend). The image scan follows with the image in MKC-8.
- **Actions pinned to commit SHAs;** top-level `permissions: contents: read`; triggers `pull_request` and `push` to `main`; no secrets in the workflow. Fork PRs therefore get nothing secret.
- **Postgres in CI:** service container `pgvector/pgvector:pg17`, `DATABASE_URL` pointing at it. On Linux the POSIX SIGTERM worker test runs too.
- **Required checks:** set only after the jobs are green on the PR, with the exact check names from `gh pr checks`. Only the `required_status_checks` part of branch protection changes, and the protection is read back before and after.

## Order

1. MKC-6.1: pytest `filterwarnings` (red with `httpx`) → swap to `httpx2` (green).
2. MKC-6.2: `scripts/check_secret_hygiene.py` (red) → `.gitignore`, `.env.example`, `.pre-commit-config.yaml` (green).
3. MKC-6.3: markdownlint config with justified rule changes, then `--fix` and manual fixes until 0 errors; the check scripts still pass.
4. MKC-6.4: `scripts/check_workflows.py` (red) → `ci.yml` (green); push and get CI green on the PR.
5. MKC-6.5: required checks; read the protection back.

## Done when

- CI is green on the PR, with jobs backend, frontend, gitleaks, dependency scan and docs.
- The gitleaks job proves that it catches a fake key.
- `scripts/check_workflows.py` and `scripts/check_secret_hygiene.py` pass.
- The jobs are required checks on `main`, and the rest of the protection is unchanged.
