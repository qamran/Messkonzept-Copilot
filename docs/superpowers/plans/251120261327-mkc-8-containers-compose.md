# MKC-8 plan: containers and local Compose

**Ticket:** MKC-8 (#8). **Branch:** `mkc-8-containers-compose`.

**Goal:** one backend image (API + worker) that runs locally in Compose and is built multi-arch in CI and pushed to GHCR from `main`.

## Sub-issues

| Key | What |
|---|---|
| MKC-8.1 | `backend/Dockerfile` (multi-stage, non-root, `MKC_COMMIT`), `backend/.dockerignore`, `scripts/check_containers.py` |
| MKC-8.2 | `compose.yaml` (db, api, worker, frontend), `frontend/Dockerfile`, `scripts/compose_smoke.sh` |
| MKC-8.3 | CI job `image` on every PR and push: amd64 build, Compose smoke test, image scan, amd64 + arm64 build without push |
| MKC-8.4 | CI job `publish` on `main` only: push to GHCR with `packages: write`; `check_workflows.py` narrowed to exactly that job |
| MKC-8.5 | Docs: design doc decision log, ADR 002, status doc, README, HANDOFF "how to run" |

## Checked before starting (25.11.2026)

- Actions run on the Turing mirror too (two `ci` runs on `push` to `main`). The push job needs a repository guard, or it would try to push from the mirror.
- Action versions (all older than two weeks, SHAs from `gh api`, lightweight tags):
  - `docker/setup-qemu-action` v4.4.0, `docker/setup-buildx-action` v4.4.1, `docker/login-action` v4.8.0, `docker/metadata-action` v6.2.0, `docker/build-push-action` v7.4.0
- Image scan: Grype v0.121.2 release binary, checksum pinned (the same way as gitleaks). v0.122.x is less than two weeks old.
- Base images pinned by their multi-arch index digest: `python:3.12-slim-trixie`, `ghcr.io/astral-sh/uv:0.12.18` (same uv as CI), `node:24-alpine`, `nginxinc/nginx-unprivileged:1.30-alpine`.

## Design choices

- **One backend image.** Two stages on the same Python base:
  - builder: uv copied from its image; `uv sync --locked --no-dev --no-editable` into `/app/.venv`. The `mkc` package must be installed, because `create_app` reads `version("mkc")`.
  - runtime: only the venv, numeric non-root user `10001`, exec-form commands (SIGTERM reaches the worker).
  - default command: the API (`uvicorn mkc.api.app:create_app --factory --host 0.0.0.0 --port 8000`); the worker runs the same image with `mkc-worker`.
  - `ARG MKC_COMMIT=dev` → `ENV MKC_COMMIT`, late in the final stage so a new commit does not bust the dependency layer.
  - `alembic.ini` and `migrations/` go into the image now, so a later deploy can run `alembic upgrade head` from the same image.
- **`compose.yaml` replaces `docker-compose.yml`** (`git mv`; one file only). `db` stays on `127.0.0.1:5433`. api and worker reach it as `db:5432`. `backend/.env` is loaded if it exists (`required: false`), so Compose starts without it (as in CI).
- **Frontend container only for local Compose:** Vite build, served by `nginx-unprivileged` on `localhost:5173`, so the CORS and `azp` defaults fit. `VITE_CLERK_PUBLISHABLE_KEY` is a build argument read from the shell or a root `.env` (a publishable key, not a secret). Without it the page loads and shows the missing-key error; the smoke test only checks that the page is served.
- **Smoke test** `scripts/compose_smoke.sh`: `docker compose up -d --build --wait`, then `/health` 200, `/api/version` returns the commit passed as build argument, the worker container still running after a few seconds, the frontend serves `index.html`. Red first (no `compose.yaml` services yet).
- **CI on PRs (`image` job, read-only token):** build amd64 with `load` for the smoke test and the scan; then build `linux/amd64,linux/arm64` without push (a multi-platform build can't be loaded). Grype fails on `high` or worse with a fix available.
- **Push on `main` (`publish` job):**
  - `needs` all CI jobs; `if: github.event_name == 'push' && github.ref == 'refs/heads/main' && github.repository == 'qamran/Messkonzept-Copilot'`.
  - job-level `permissions: contents: read, packages: write`; login with `github.token`, not `secrets.GITHUB_TOKEN`, so the "no secrets in CI" rule stays as it is.
  - image `ghcr.io/qamran/messkonzept-copilot-backend` (lower case, written out, not from `github.repository`); tags `<full commit sha>` and `main`.
  - the last step inspects both tags and prints both platforms, as evidence in the `main` run's log.
- **`check_workflows.py` narrowing:** `packages: write` is allowed only in the job `publish` of `ci.yml`, only with that exact `if:` guard. Every other write permission is still refused. Red samples first.
- **Required checks:** `image` is a required check on `main` (set during the PR on 25.11.2026 13:52, as MKC-6.5 did for the first five). `publish` is never required (it is skipped on PRs).

## What the reviewer can check before the merge

Criterion 3 ("tagged with the commit SHA and `main` in GHCR") is only true after the merge. Before the merge, the evidence is:

- the PR's `image` job: green multi-arch build, the smoke test, the scan
- the `publish` job: shown as skipped on the PR, its guard and tags in the diff, `check_workflows.py` red/green for the narrowing

After the merge, the development agent ticks criterion 3 only when the `main` run's `publish` job is green and its log lists both tags and both platforms. If it fails, fix forward under MKC-8.

## Order

1. MKC-8.1: red `check_containers.py`, then the Dockerfile; local build and run.
2. MKC-8.2: red smoke script, then `compose.yaml` and the frontend image; local smoke test green.
3. MKC-8.3: red `check_workflows.py` rule (job `image` required), then the job.
4. MKC-8.4: red samples for the narrowed rule, then the `publish` job.
5. MKC-8.5: docs; PR.

## Done when

- `docker compose up` locally gives `/health` 200 and a running worker.
- CI builds `linux/amd64,linux/arm64` on the PR and is green.
- After the merge: `<commit sha>` and `main` tags in GHCR for both platforms.
