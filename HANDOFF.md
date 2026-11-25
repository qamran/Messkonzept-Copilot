# HANDOFF

**Last updated:** 25.11.2026, 15:36

This file is how agents resume work after a session restart.

- **Updated:** in every commit, and after every important ticket change: status change, sub-issue created or closed, PR opened or merged, review verdict. A change made outside a branch (e.g. on the board) is recorded in the next commit.
- **This file vs the status doc:** this file is the running log and next steps for agents. `docs/241120261430-project-status.md` is the overview of decisions and documents.

## Read this first

1. `AGENTS.md`: the project rules, roles, ticket flow and the review agent's checklist.
2. This file, top to bottom.
3. The ticket you are about to work on: `gh issue view <n> -R qamran/Messkonzept-Copilot`.
4. Background when needed:
   - design doc: `docs/superpowers/specs/241120261330-messkonzept-copilot-design.md`
   - backlog: `docs/superpowers/plans/241120261500-ticket-backlog.md`
   - ADRs: `docs/adr/`

## Current state

- **Design approved;** ADRs 001–005 accepted; backlog MKC-1 to MKC-60 on the public board (issue number = key). The board's auto-add workflow is on.
- **Remotes:**
  - `origin` = qamran/Messkonzept-Copilot (home, public)
  - `turing` = TuringCollegeSubmissions/qshahz-AE.CAP.AFA.1.1 (code-only mirror, no issues; ADR 005 option (c), decision 35)
  - Both at `35dc1fe` (merge of PR #97).
- **`main` is protected:** PRs only, enforced for admins. Required checks: the `ci` jobs `backend`, `frontend`, `gitleaks`, `dependency-scan` and `docs` (since 25.11.2026 09:50, MKC-6.5) and `image` (since 13:52, MKC-8); the branch must be up to date with `main`. `publish` is not required (skipped on PRs).
- **Agent rules:** `AGENTS.md` (CLAUDE.md imports it). The development agent continues without asking and stops only for genuine decisions (decision 36).
- **Done:**
  - MKC-1: board, labels, tickets, templates, branch protection (PR #65)
  - MKC-2: code-only Turing mirror, README with links, `scripts/check_readme.py` (PR #70)
  - MKC-3: assignment rule (PR #67), HANDOFF.md (PR #69), AGENTS.md + CLAUDE.md + `scripts/check_agents.py` (PR #72)
  - MKC-4: backend skeleton in `backend/` (uv, Python 3.12, package `mkc`): Settings, FastAPI `/health` + `/api/version`, worker with clean SIGTERM shutdown; ruff + mypy strict (PR #75)
  - MKC-5: database layer: compose Postgres 17 + pgvector on `127.0.0.1:5433`, SQLAlchemy 2, Alembic, `python -m mkc.db.check`; Supabase connection checked via the Session pooler (PR #80)
  - MKC-6: secret hygiene (`.gitignore`, `.env.example`, pre-commit), markdown lint, CI (`backend`, `frontend`, `gitleaks`, `dependency-scan`, `docs`) as required checks on `main`; `httpx2` (PR #86)
  - MKC-7: frontend skeleton (`frontend/`: Vite, React, TS, Tailwind, shadcn/ui, `@clerk/react`, `apiFetch`, `RequireAdmin`); backend Clerk token check (`mkc.api.auth`, `/api/me`, `/api/admin/ping`); Clerk development instance everywhere (ADR 002, decision 39) (PR #91)
  - MKC-8: backend image (`backend/Dockerfile`), `compose.yaml` (db, api, worker, frontend), `scripts/compose_smoke.sh`, CI jobs `image` (required check) and `publish`; image `ghcr.io/qamran/messkonzept-copilot-backend` (public, tags `<sha>` and `main`, amd64 + arm64) (decision 41, PR #97)
- **How to run the frontend:** `frontend/.env.local` holds `VITE_CLERK_PUBLISHABLE_KEY` and `VITE_API_URL=http://127.0.0.1:8000` (gitignored). Run the API with `cd backend && uv run --env-file .env uvicorn mkc.api.app:create_app --factory --port 8000` (`backend/.env` has `MKC_CLERK_ISSUER`), then `cd frontend && npm run dev` (`localhost:5173`). Test sign-ins: the user's Google account (admin); a `+clerk_test@example.com` user (code `424242`) and a second Gmail account (both no role).
- **How to run the whole stack in containers:** `docker compose --env-file frontend/.env.local up --build` (repo root; the env file gives the frontend build its Clerk key; without it the page says the key is missing). API on `127.0.0.1:8000`, frontend on `localhost:5173`, db on `127.0.0.1:5433`; `backend/.env` is loaded when present. `bash scripts/compose_smoke.sh` checks the stack as its own project (`mkc-smoke`, ports 15433/18000/15173, images tagged `smoke`) and removes its containers and volume afterwards.
- **How to test the backend:** `docker compose up -d db` (repo root; Postgres 17 + pgvector on `127.0.0.1:5433`), then `cd backend && uv sync && uv run pytest`. The DB tests fail if the db is down; `MKC_SKIP_DB_TESTS=1` skips them on purpose. Windows skips one POSIX-only worker test; run it in Linux with the Docker command in PR #75.

## In progress

- **MKC-9** (#9), Helm chart and kind smoke test. Status `In progress`, assigned to `qamran`. Branch `mkc-9-helm-kind`. Plan: `docs/superpowers/plans/251120261520-mkc-9-helm-kind.md`.
  - Sub-issues (all `In progress`, assigned to `qamran`): MKC-9.1 (#98) worker heartbeat and health command; MKC-9.2 (#99) Helm chart; MKC-9.3 (#100) kind smoke script; MKC-9.4 (#101) CI job `kind` as a required check; MKC-9.5 (#102) docs.
  - Local tools (not in the repo): Helm v4.3.1, kind v0.33.0 and kubectl v1.37.0, checksum-checked, in the session scratchpad. CI downloads its own pinned copies.

## Next steps

1. MKC-9: MKC-9.1 (heartbeat) first, then the chart, the smoke script, the CI job and the docs (order in the plan).
2. Non-blocking follow-ups from the PR #97 review (fold into a later CI-hardening ticket or MKC-9 where they touch the same files):
   - check scripts are substring-based: flow-style `permissions: {…: write}`, `toJSON(secrets)`, `|| true` / `continue-on-error` on the scan, `if: false` on `image`, indented `USER root`, `USER 10001:0`, `COPY --chown --from=<unpinned>`, `!.env` after `.env`, `compose.override.yaml` all pass
   - no kept tests rerun the bad samples (they live only in the PR body and HANDOFF)
   - `cancel-in-progress: true` also applies on `main`: two quick merges can cancel a `publish`
   - the Grype database is not pinned, so a new high finding can turn unrelated PRs red
   - remove `pip` from the runtime image (source of most medium findings); `pgvector/pgvector:pg17` not digest-pinned; `publish` rebuilds instead of pushing the scanned image
   - the MKC-8 plan still lists `docker/metadata-action` (not used)
3. Optional follow-ups from the PR #91 re-review (non-blocking): `apiBase()` could refuse a query, fragment or userinfo in `VITE_API_URL`; an empty `sub` is accepted; falsy non-string roles read as "no role".

## Blocked / waiting on user

- **Docker Desktop** must be running for the local DB tests (`docker compose up -d db`). If it is stopped after a restart, start it again. CI uses its own Postgres service.
- Later setup tasks (listed in design doc section 13): Vercel account, provider API keys with caps, GitHub `production` environment, a domain with TLS. The Supabase project exists (created by the user on 25.11.2026).

## Recent log

Newest first. Times are local (CET), taken from git and GitHub.

- **25.11.2026 15:36** MKC-9.3: `scripts/kind_smoke.sh` (own cluster `mkc-smoke`, temporary `KUBECONFIG`, refuses an existing cluster, image loaded as an archive, `helm install --wait`, `/health` and `/api/version` through the Service, worker Ready with 0 restarts twice 20 s apart, worker pod deleted → `signal SIGTERM received` and `worker stopped`, new worker Ready; diagnostics on failure; cluster delete retried). The chart came first, so the red run used a wrong expected commit: `MKC_EXPECT_COMMIT=wrong-commit` → `FAIL: /api/version does not report commit wrong-commit`, diagnostics printed, exit 1 (15:31). Its cluster delete failed once on Docker Desktop (`did not receive an exit event`); removed by hand, and the script now retries the delete. Green run 15:33:03–15:34:20 (exit 0): commit `green-ebfc204` returned, worker stopped 1 s after the delete. `~/.kube` has no config file afterwards (only a `cache` folder).
- **25.11.2026 15:51** MKC-9.2: chart part 2: API Deployment (replicas from values; startup, readiness and liveness probes on `/health`), worker Deployment (`replicas: 1`, `Recreate`, grace period 300 s with the budget in a comment, `mkc-worker-health` exec probes, heartbeat in `/tmp`), Ingress (class from values; TLS with the cert-manager annotation; host and issuer required). Both pods: uid 10001, read-only root, no privilege escalation, all capabilities dropped, no service-account token. `check_helm.py` green; `helm lint --strict` (v4.3.1) green with `--set image.tag=lint` and with `ci-values.yaml`. `helm template` refuses `latest`, a missing tag, a missing host and a missing issuer. A mutated copy (grace 120, replicas from values, RollingUpdate, no cert-manager annotation, writable root, a secret and `latest` in values, Ingress off in the CI values) gives eight findings.
- **25.11.2026 15:50** MKC-9.2: chart part 1: `Chart.yaml` (0.1.0), `values.yaml` (image tag required, no secrets, requests and limits), `ci-values.yaml` (kind test: local image, Ingress and TLS on, placeholder `DATABASE_URL`), helpers (image tag required and `latest` refused; checksum annotations), ConfigMap from `env`, Secret from `secrets` unless `existingSecret`, Service. `check_helm.py` still red (Deployments and Ingress follow).
- **25.11.2026 15:38** MKC-9.2: `scripts/check_helm.py` added (stdlib text checks: chart files; API replicas from values, three probes on `/health`; worker `replicas: 1`, `Recreate`, grace period ≥ 300, `mkc-worker-health` probes; both non-root, read-only root, `envFrom` Secret; Ingress class, TLS, cert-manager annotation; `values.yaml` without secrets or `latest`, with requests and limits; `ci-values.yaml` with Ingress and TLS on). Red: all nine chart files missing.
- **25.11.2026 15:32** MKC-9.1: `check_secret_hygiene.py` was red after the last commit (`.env.example: missing MKC_WORKER_HEARTBEAT_FILE` and `…_MAX_AGE_SECONDS`); both added to `.env.example`. All `scripts/check_*.py` pass.
- **25.11.2026 15:30** MKC-9.1: settings `MKC_WORKER_HEARTBEAT_FILE` (empty = off) and `MKC_WORKER_HEARTBEAT_MAX_AGE_SECONDS` (30); the worker touches the file on start and every poll (a failed write is logged); `mkc-worker-health` (`mkc.worker.health`). 60 passed, 1 skipped (POSIX-only); ruff and mypy pass.
- **25.11.2026 15:27** MKC-9.1: red tests `tests/worker/test_heartbeat.py` (heartbeat written on start and refreshed on every poll, none when not configured; `mkc-worker-health` exit codes for fresh, stale, missing, not configured). Collection fails: `mkc.worker.health` missing.
- **25.11.2026 15:23** MKC-9 plan written (`251120261520-mkc-9-helm-kind.md`). Checked: Helm v4.3.1, kind v0.33.0 (node `v1.37.0` by digest), kubectl v1.37.0, all older than two weeks; k3s stable is v1.37.2. Grace-period budget 300 s (decision 42 in MKC-9.5).
- **25.11.2026 15:21** MKC-9 sub-issues MKC-9.1 (#98) to 9.5 (#102) created (15:21:35–15:21:55), assigned to `qamran`, linked to #9 and set to `In progress`.
- **25.11.2026 14:38** HANDOFF and status doc caught up after PR #97 (MKC-8 done, MKC-9 current).
- **25.11.2026 14:36** MKC-9 (#9) assigned to `qamran`, to `In progress`; branch `mkc-9-helm-kind` from `35dc1fe`.
- **25.11.2026 14:36** #8 and #92–#96 criteria ticked. MKC-8 complete. The GHCR package is public (anonymous pull token 200, no local login), so MKC-10 needs no pull secret.
- **25.11.2026 14:34** `main` run 45624241353 on `35dc1fe` green; `publish` 13:34:41Z: `:35dc1fee…` and `:main` are the same index `sha256:704a208a…` with `linux/amd64` and `linux/arm64` (plus two attestation entries).
- **25.11.2026 14:31** `main` pushed to `turing` (14:31:07); `origin/main` == `turing/main` == `35dc1fe`.
- **25.11.2026 14:30** PR #97 review **PASS** (comment 14:30:01), merged `35dc1fe` (merge commit, 14:30:11); #8 and #92–#96 closed and `Done`. Non-blocking findings: see Next steps 2. The user gave standing permission to start the review agent and merge on PASS without asking.
- **25.11.2026 13:56** Review agent for PR #97 not started: denied by the session permission check (as for PR #80 and #91). PR #97 waits for the user's go-ahead to run the review agent. This commit stays local until then, so the PR head (`32b92da`) keeps its CI evidence.
- **25.11.2026 13:56** PR #97 body updated: CI run 45618105862 on `32b92da` green (12:55:34Z; publish skipped; smoke test OK, Grype on `mkc-backend:smoke` passed); section "Fixes before review".
- **25.11.2026 13:53** MKC-8 fixes before review: `.gitattributes` keeps `*.sh` LF (a Windows checkout gave `compose_smoke.sh` CRLF); the smoke test builds its own image tag `smoke` (`MKC_IMAGE_TAG`) and CI scans `mkc-backend:smoke`; `check_workflows.py` also requires `--fail-on high` (red on a sample without it); `compose_smoke.sh` green again locally; `docker compose --env-file frontend/.env.local config` gives the frontend a `pk_test_` key and `VITE_API_URL=http://127.0.0.1:8000`. ADR 005, decision 41, status doc and plan record the `image` required check; HANDOFF next steps are the post-merge list; GHCR visibility under "Blocked".
- **25.11.2026 13:52** `image` added to the required checks on `main` (PATCH at 13:52:30; before/after diff of the protection: only the `image` check added).
- **25.11.2026 13:47** PR #97 body updated with the CI evidence of run 45616477619.
- **25.11.2026 13:47** HANDOFF log times for MKC-8 corrected to the git commit times (13:30–13:42); earlier lines had estimated times, against the rule.
- **25.11.2026 13:46** CI run 45616477619 on `7cde086` green (12:46:08Z): backend, frontend, gitleaks, dependency-scan, docs, image; publish skipped. `image`: smoke test OK with the PR merge commit `579d99f`, worker `running restarts=0`; Grype only medium, low and unknown (base `pip` 25.0.1, Python 3.12.16, `libzstd1`); `linux/amd64,linux/arm64` build 12:45:03–12:46:08Z.
- **25.11.2026 13:44** #8 and #92–#96 to `Testing`.
- **25.11.2026 13:43** MKC-8: PR #97 opened (12:43:12Z; assigned to `qamran`; closes #8, #92–#96).
- **25.11.2026 13:42** MKC-8.5: design doc decision 41 (agent) and section 13 local line; ADR 002 section "Images and the GHCR push"; status doc MKC-8 details, the narrowed write rule and the decision count; README names `compose.yaml` and the smoke test; HANDOFF "How to run the whole stack in containers".
- **25.11.2026 13:41** MKC-8.4: `check_workflows.py` allows exactly one write: `packages: write` in ci.yml's job `publish` with the exact job-level guard. `ci.yml` green. Eight samples refused: no guard; guard without the repository check; `contents: write` in publish; `packages: write` in `image`; job renamed; a second `packages: write`; the same job in another workflow; login with `secrets.GITHUB_TOKEN`.
- **25.11.2026 13:40** MKC-8.4: CI job `publish` (needs all jobs; `if:` push to `main` in `qamran/Messkonzept-Copilot`; job-level `packages: write`; login with `github.token`; tags `<sha>` and `main`, both platforms; last step inspects both tags). Red: `check_workflows.py` reports `grants a write permission; CI is read-only`.
- **25.11.2026 13:40** MKC-8.3: CI job `image`: Compose smoke test with `MKC_COMMIT=github.sha`, Grype v0.121.2 (checksum pinned; `--only-fixed --fail-on high`), QEMU + buildx `linux/amd64,linux/arm64` build without push (GHA cache). `check_workflows.py` green. Local Grype run on the image: exit 0, no high or critical (mediums in the base image's `pip` and Python 3.12.16).
- **25.11.2026 13:36** MKC-8.3: `check_workflows.py` requires a job `image` that runs `scripts/compose_smoke.sh`, Grype and a `linux/amd64,linux/arm64` build. Red: `job 'image' missing`; a sample with an empty `image` job reports all three steps.
- **25.11.2026 13:35** MKC-8.2: `docker-compose.yml` → `compose.yaml` (`git mv`) with db, api, worker, frontend; `backend/.env` optional; api and worker use `db:5432`; host ports movable (`MKC_DB_PORT`, `MKC_API_PORT`, `MKC_WEB_PORT`). `frontend/Dockerfile` (node 24 build, `nginx-unprivileged` on 8080, uid 101, SPA fallback). `check_containers.py` green; `compose_smoke.sh` green locally (commit `smoke-1795609974`, worker `running restarts=0`, frontend and `/admin` 200).
- **25.11.2026 13:32** MKC-8.2: `scripts/compose_smoke.sh` added (own project `mkc-smoke` on ports 15433/18000/15173, so the local stack and its db volume are never touched; checks `/health`, `/api/version` commit, worker running, frontend `index.html` and `/admin`). Red: `compose.yaml` missing.
- **25.11.2026 13:31** MKC-8.1: `backend/Dockerfile` (builder + runtime on `python:3.12-slim-trixie`, uv 0.12.18, both by index digest; uid 10001; `MKC_COMMIT` last) and `backend/.dockerignore`. Local build with `MKC_COMMIT=test123`: `/health` 200, `/api/version` gives `test123`, `id` gives uid 10001, `mkc-worker` stops on SIGTERM with exit 0 (container log 13:31). Image 287 MB. `check_containers.py` has no backend findings left (frontend and Compose follow in MKC-8.2).
- **25.11.2026 13:30** MKC-8.1: `scripts/check_containers.py` added (Dockerfiles multi-stage, digest-pinned, numeric non-root `USER`, exec form, `MKC_COMMIT`; `.dockerignore` entries; `compose.yaml` services db, api, worker, frontend, one Compose file). Red: both Dockerfiles and `compose.yaml` missing, `docker-compose.yml` still there.
- **25.11.2026 13:29** MKC-8 sub-issues MKC-8.1 (#92) to 8.5 (#96) created (13:28:34–13:28:49), assigned to `qamran`, linked to #8 and set to `In progress`.
- **25.11.2026 13:27** MKC-8 plan written. Checked: Actions run on the Turing mirror (two `ci` push runs), so the GHCR push needs a repository guard; action SHAs and base-image index digests looked up.
- **25.11.2026 12:15** HANDOFF and status doc caught up after PR #91 (MKC-7 done, MKC-8 current).
- **25.11.2026 12:14** MKC-8 (#8) assigned to `qamran`, to `In progress`; branch `mkc-8-containers-compose` (reflog 12:14:46).
- **25.11.2026 12:14** #7 and #87–#90 criteria ticked. MKC-7 complete.
- **25.11.2026 12:13** `main` pushed to `turing` (12:13:51); `origin/main` == `turing/main` == `02ddb84`.
- **25.11.2026 12:13** PR #91 re-review **PASS** (comment 12:13:01), merged `02ddb84` (merge commit, 12:13:11); #7 and #87–#90 closed and `Done`. The `apiFetch` origin check held against 1,960 attack combinations. Non-blocking: query/fragment in `VITE_API_URL`, `..` within the base path, "`//`" wording (only a leading `//` is refused), empty `sub`, falsy non-string roles, the history notes.
- **25.11.2026 12:03** PR #91 body lists the fixes; #7 and #87–#90 to `Testing`. CI run 45600646478 on `fc0795b` green.

- **25.11.2026 12:02** MKC-7: status doc no longer names PR #86 twice and mentions the `apiFetch` origin rule; ADR 002 lists the 401/403/503 mapping.

- **25.11.2026 12:01** MKC-7.1: `TokenVerifier` rejects a non-string `azp` or `role` (401); `require_user` maps `PyJWKClientConnectionError` to 503 ("Login provider unreachable"). 52 passed, 1 skipped (POSIX-only); ruff and mypy pass.

- **25.11.2026 12:01** MKC-7.1: red tests from the review's non-blocking points: list `azp`, list/object/number `role` → 401 (now 500: `TypeError`, pydantic `ValidationError`); JWKS unreachable → 503 (now 401). Numeric `sub` already gives 401 (PyJWT checks it). 5 failed, 26 passed.

- **25.11.2026 12:00** MKC-7.3: `apiFetch` fix: `VITE_API_URL` must be an absolute http(s) URL; paths with `\`, control characters or `//` are refused; the final URL must have the API origin. 21 frontend tests pass; lint and typecheck pass. `frontend/.env.example` says `VITE_API_URL` is required.

- **25.11.2026 12:00** MKC-7.3: red tests for the review finding: `apiFetch` must reject paths with a backslash, tab, newline or `//`, and refuse to run when `VITE_API_URL` is empty or relative; a base path in `VITE_API_URL` is kept. 5 of 12 fail.
- **25.11.2026 11:59** #7 and #87–#90 back to `In progress`.
- **25.11.2026 11:58** PR #91 review **FAIL** (comment 10:58:49Z): `apiFetch` could send the token to another host when `VITE_API_URL` is empty (`/\evil.example/x`, tab or newline after the first `/`). Non-blocking: list-valued `azp` or `role` gives 500 instead of 401; JWKS outage gives 401 instead of 503; two commits without HANDOFF; three commits over 200 lines; AppShell red and green in one commit; status doc names PR #86 twice; PR body cites an older CI run. Everything else passed (JWT check sound, CORS, RequireAdmin, CI, docs, secrets).

- **25.11.2026 11:50** HANDOFF corrected: `424242` failed because the test user was a real Gmail address, not because test mode was off (Clerk's docs: test mode is on by default for development instances). The user added a `+clerk_test@example.com` user without a role; it signs in with `424242`.
- **25.11.2026 11:42** Review agent for PR #91 not started: denied by the session permission check (as for PR #80). PR #91 waits for the user's go-ahead to run the review agent.

- **25.11.2026 11:41** MKC-7: PR #91 body updated with the local-check evidence; #7 and #87–#90 to `Testing`.
- **25.11.2026 11:41** MKC-7.4 (log read at 11:41; the access log has no timestamps): local check of the three login states with the user, against the real Clerk development instance:
  - signed out: start page shows the sign-in hint; `/admin` redirects to `/sign-in` (user confirmed)
  - test user (no role): `GET /api/me` 200, card shows role none, admin no; `/admin` shows "Admin role required" (client guard; the backend 403 is covered by `test_admin_route_rejects_a_normal_user`)
  - user's Google account (admin): `GET /api/me` 200 with role admin; `/admin` shows "Backend admin check passed", `GET /api/admin/ping` 200
  - the test user in this check was a real Gmail address, so Clerk sent a real code and rejected `424242` (that code only works for `+clerk_test` addresses)
- **25.11.2026 11:35** MKC-7: PR #91 opened (assigned to `qamran`; closes #7, #87–#90). CI run 45596478608 green: backend, frontend, dependency-scan, docs, gitleaks.

- **25.11.2026 11:35** MKC-7.4: ADR 002 section "Clerk instance" (decision, why, options, accepted limits, wiring); design doc decisions 39 (user) and 40 (agent), section 13 updated; status doc and README updated; plan corrected (`apiFetch` uses `getToken()`). markdownlint 0 errors; all `scripts/check_*.py` pass.
- **25.11.2026 11:33** Branch pushed to `origin` (`a6b57bf`). Local run: API on `127.0.0.1:8000` with `MKC_CLERK_ISSUER` from `backend/.env` (`/api/me` gives 401 without and with a bad token), Vite on `localhost:5173` (200).

- **25.11.2026 11:33** MKC-7.3: pages and routes: `/` `HomePage` (shows `/api/me`), `/sign-in/*` Clerk `SignIn`, `/admin` `AdminPage` behind `RequireAdmin` (calls `/api/admin/ping`). 14 tests pass; lint and build pass.

- **25.11.2026 11:33** MKC-7.3: `HomePage` test added; red (`./HomePage` missing). Covers: signed out → sign-in hint and no protected call; signed in → shows `/api/me`; backend error → status shown.

- **25.11.2026 11:32** MKC-7.3: `src/lib/api.ts` (`apiFetch` with Clerk's `getToken()`, which works outside React, so no token bridge is needed), `src/lib/roles.ts` (`isAdmin`: `role` exactly `admin`, as in the backend), `src/components/RequireAdmin.tsx`. 11 tests pass; lint and typecheck pass.

- **25.11.2026 11:31** MKC-7.3: red tests for `apiFetch` (Bearer token, no header when signed out, `VITE_API_URL` prefix, caller headers kept, absolute URLs rejected) and `RequireAdmin` (loading, signed out → sign-in, non-admin blocked, other role blocked, admin renders); both files fail to resolve (`./api`, `./RequireAdmin` missing).

- **25.11.2026 11:31** MKC-7.2: CI frontend job runs `npm ci`, lint, typecheck, test and build (the "no frontend yet" switch is gone); dependency-scan runs `npm audit --omit=dev` (any level) and `npm audit --audit-level=high` (all packages). `check_workflows.py` and `check_secret_hygiene.py` green.
- **25.11.2026 11:30** MKC-7.2: frontend scaffold committed (`572c915`, without a HANDOFF change; logged here). Vite react-ts template, Tailwind 4, shadcn/ui `radix-nova` (button, card), ESLint, vitest + jsdom + Testing Library, `@clerk/react` 6, `react-router` 8; TypeScript stays 5.9 (template). AppShell smoke test red (module missing), then green. `shadcn` moved to dev dependencies: as a runtime dependency it pulled `ts-morph` → `minimatch` (4 moderate advisories); now `npm audit --omit=dev` 0 and `--audit-level=high` 0. lint, typecheck, test and build pass.

- **25.11.2026 11:24** MKC-7.2: `check_secret_hygiene.py` requires `frontend/.env.example` (both `VITE_` names, no values); `check_workflows.py` requires `npm audit` in the dependency-scan job. Both red (`frontend/.env.example: file missing`; `job 'dependency-scan' must run 'npm audit'`).

- **25.11.2026 11:23** MKC-7.1: `mkc.api.auth` (`TokenVerifier`, `require_user`, `require_admin`, JWKS resolver), `GET /api/me`, `GET /api/admin/ping`, CORS allow-list; settings `MKC_CLERK_ISSUER`, `MKC_CLERK_AUTHORIZED_PARTIES`, `MKC_CORS_ORIGINS` in `.env.example`. 46 passed, 1 skipped (POSIX-only); ruff, mypy and `check_secret_hygiene.py` pass.
- **25.11.2026 11:21** MKC-7.1: plan and red tests committed (`2e01edb`): `tests/api/test_auth.py` fails at collection (`mkc.api.auth` missing); 3 config tests fail (`Settings` has no Clerk fields). PyJWT 2.15.1 with `cryptography` added.
- **25.11.2026 11:20** #87–#90 linked to #7 and set to `In progress`.
- **25.11.2026 11:19** MKC-7 sub-issues MKC-7.1 (#87), 7.2 (#88), 7.3 (#89), 7.4 (#90) created (11:19:46–11:20:02), assigned to `qamran`.
- **25.11.2026** User decision: Clerk development instance for all environments, permanently; user set up the instance, the `role` claim, the admin and a test user. Instance JWKS checked: one RS256 key.

- **25.11.2026 10:15** HANDOFF and status doc caught up after PR #86 (MKC-6 done, MKC-7 current; Clerk application needed from the user).
- **25.11.2026 10:14** MKC-7 (#7) assigned to `qamran`, to `In progress`; branch `mkc-7-frontend-skeleton` (reflog 10:14:55).
- **25.11.2026 10:14** #6 and #81–#85 criteria ticked. MKC-6 complete.
- **25.11.2026 10:13** `main` pushed to `turing` (reflog 10:13:59); `origin/main` == `turing/main` == `410a178`.
- **25.11.2026 10:13** PR #86 third review **PASS** (comment 10:13:28), merged `410a178` (merge commit, 10:13:32); #6 and #81–#85 closed and `Done`. Non-blocking: service image not pinned by digest; `Refs:` not parsed as a git trailer (same on `main`); the 09:50 protection time can't be checked from git or the API.
- **25.11.2026 10:11** MKC-6: status doc test count replaced by "every backend test runs on Linux, none skipped"; status doc notes empty = default and the MKC-10 deploy exception; HANDOFF names both FAIL rounds; PR #86 body updated; #6 and #81–#85 to `Testing`.
- **25.11.2026 10:10** #6 and #81–#85 back to `In progress`.
- **25.11.2026 10:10** PR #86 re-review **FAIL** (comment 09:10:01Z): all four findings fixed, but the status doc still said "all 17 tests" while the head has 19.
- **25.11.2026 10:05** MKC-6: PR #86 body lists the review fixes; #6 and #81–#85 to `Testing` for the re-review.
- **25.11.2026 10:04** MKC-6: HANDOFF fixes from the PR #86 review: "Current state" names the required checks; the Docker line no longer says MKC-5; the 09:34 line split into 09:33 and 09:34 by event time; FAIL and status changes logged.
- **25.11.2026 10:03** MKC-6.4: `check_workflows.py` also rejects `secrets['x']`, `secrets: inherit` and any `write`/`write-all` permission (review observation). Before: a sample workflow with all three reported nothing; after: both rules fire; `ci.yml` still green.
- **25.11.2026 10:02** MKC-6.2: `.env.example` lists `MKC_DATABASE_URL` and says an empty value means the default; `check_secret_hygiene.py` green; config tests pass.
- **25.11.2026 10:02** MKC-6.2: `check_secret_hygiene.py` now requires every `validation_alias` name, not only the first; red (`.env.example: missing MKC_DATABASE_URL`).
- **25.11.2026 10:02** MKC-6.2: `Settings` uses `env_ignore_empty=True`; 18 passed, 1 skipped; a copy of `.env.example` loaded with `uv run --env-file` gives the defaults and `python -m mkc.db.check` reaches the compose db.
- **25.11.2026 10:01** MKC-6.2: two config tests added (empty variables fall back to defaults; `.env.example` as-is gives the defaults); red (`ValidationError` on the empty `MKC_WORKER_POLL_SECONDS`).
- **25.11.2026 10:01** #6 and #81–#85 back to `In progress`.
- **25.11.2026 10:00** PR #86 review **FAIL** (comment 09:00:43Z): (1) `.env.example` says empty = default, but `Settings` read `""` as a value and crashed; (2) `.env.example` missed `MKC_DATABASE_URL`, which the check couldn't see; (3) stale HANDOFF lines on required checks and Docker; (4) the 09:34 log line mixed two minutes. CI, red-to-green, protection and secrets passed.
- **25.11.2026 09:53** Status doc header set to the time of its last commit.
- **25.11.2026 09:53** MKC-6: PR #86 body filled in (criteria with evidence); #6 and #81–#85 to `Testing`. HANDOFF: the 09:51 log line corrected to the commit time 09:52 (`fdddf8b`).
- **25.11.2026 09:52** MKC-6: design doc decisions 37 (`httpx2`, user) and 38 (CI and required checks, agent); ADR 005 branch-protection note; status doc and README updated.
- **25.11.2026 09:50** MKC-6.5: required status checks set on `main` (`backend`, `frontend`, `gitleaks`, `dependency-scan`, `docs`; GitHub Actions app 15368; branch must be up to date). The API's PATCH needs checks already on, so a full PUT built from the saved settings was used; before/after diff: only `required_status_checks` changed (PR reviews, admin enforcement, no force-push, no deletion, conversation resolution unchanged). PR #86 `CLEAN`.
- **25.11.2026 09:49** MKC-6.4: CI run 45579604956 on `a7cb041` green: backend 17 passed (none skipped, incl. the SIGTERM test), gitleaks self-test caught the fake key and 71 commits had no leaks, pip-audit found no known vulnerabilities, markdownlint 0 errors, all six check scripts pass, frontend reports "No frontend/ yet".
- **25.11.2026 09:48** MKC-6: PR #86 opened (assigned to `qamran`; closes #6, #81–#85).
- **25.11.2026 09:48** MKC-6.4: `.github/workflows/ci.yml` with jobs backend (pgvector service, ruff, mypy, pytest), frontend (reports success until MKC-7), gitleaks (v8.30.1 binary, checksum pinned; self-test with a runtime-built fake key; full-history scan), dependency-scan (pip-audit 2.10.1 on the hashed `uv export`; locally: no known vulnerabilities) and docs (markdownlint, check scripts). Actions pinned to SHAs. `check_workflows.py` green.
- **25.11.2026 09:46** MKC-6.4: `scripts/check_workflows.py` added; red (`ci.yml` missing). Against a bad sample workflow it reports `pull_request_target`, `secrets.`, a `paths` filter, missing `contents: read`, an unpinned action and the missing jobs.
- **25.11.2026 09:46** MKC-6.3: HANDOFF log line moved below the blank line the lint fixer added (MD032); lint 0 errors.
- **25.11.2026 09:43** MKC-6.3: markdownlint-cli2 0.18.1 on all 18 tracked Markdown files: 0 errors (was about 270). Fixes: blank lines around headings and lists, `text` on four code fences, `<>` around bare URLs. Config: MD029 off (the design doc numbers features across sections); `.github/.markdownlint.jsonc` allows the template placeholders (MD033) and the PR template's `##` start (MD041). The fixer had flattened the nested list under design doc feature 7; restored by hand. All `scripts/check_*.py` pass.
- **25.11.2026 09:41** MKC-6.2: `.gitignore` (PDFs, `.env*` except `.env.example`, renders, caches, `node_modules`, `dist`), `.env.example` (no values), `.pre-commit-config.yaml` (gitleaks v8.30.1, ruff-check and ruff-format v0.17.6, end-of-file-fixer v6.0.0); `check_secret_hygiene.py` green; `uvx pre-commit run --all-files` passes; no tracked file is ignored.
- **25.11.2026 09:37** MKC-6.2: `scripts/check_secret_hygiene.py` added; red (PDFs, `.env.local`, renders, caches and `node_modules` not ignored; `.env.example` and `.pre-commit-config.yaml` missing).
- **25.11.2026 09:36** MKC-6.1: dev dependency `httpx` → `httpx2` 2.16.2 (adds `truststore` 0.10.5); 16 passed, 1 skipped, **no warnings**; ruff and mypy pass.
- **25.11.2026 09:35** MKC-6.1: pytest turns `StarletteDeprecationWarning` into an error; red (`tests/api/test_health.py` fails at collection: "Using `httpx` with `starlette.testclient` is deprecated").
- **25.11.2026 09:35** MKC-6: plan written; status doc (MKC-5 done, MKC-6 current) and HANDOFF caught up after PR #80. Pre-checks: gitleaks v8.30.1 finds no leaks in the 62 commits of history and does flag a runtime-built fake `ghp_` token; `httpx2` 2.16.2 is from the pydantic org; the `gh` token has the `workflow` scope; markdownlint-cli2 0.18.1 reports about 270 errors on tracked Markdown.
- **25.11.2026 09:34** #85 assigned to `qamran` (09:34:01); #81–#85 linked to #6 (09:34:10–09:34:18) and set to `In progress` (09:34:22–09:34:42).
- **25.11.2026 09:33** Branch `mkc-6-secret-hygiene-ci` created (reflog 09:33:20); MKC-6 sub-issues MKC-6.1 (#81), 6.2 (#82), 6.3 (#83), 6.4 (#84), 6.5 (#85) created (09:33:43–09:33:59), #81–#84 assigned to `qamran`.
- **25.11.2026 09:33** MKC-6 (#6) assigned to `qamran`, to `In progress`.
- **25.11.2026 09:30** #5 and #76–#79 criteria ticked. MKC-5 complete.
- **25.11.2026 09:30** `main` pushed to `turing` (reflog 09:30:03); `origin/main` == `turing/main` == `8d88c38`.
- **25.11.2026 09:29** PR #80 re-review **PASS**, merged `8d88c38` (merge commit); #5 and #76–#79 closed and set to `Done` by the board's automation. Non-blocking: `8e6dc56` and `a497afb` did not touch HANDOFF.md.
- **25.11.2026** User decision: switch to `httpx2` now, after the PR #80 review (MKC-6.1).
- **25.11.2026 09:26** PR #80 text: skip count with `MKC_SKIP_DB_TESTS=1` updated (`9 passed, 8 skipped`); #5 and #76–#79 back to `Testing` for the re-review.
- **25.11.2026 09:26** Fixes for the PR #80 review: status doc header from git; plan default URL `127.0.0.1` and closing line (#5 and #79 now closed by the PR); the 24.11. 21:30 log line split by event time (board status at 21:31); 09:16 line sourced.
- **25.11.2026 09:25** #5 and #76–#79 back to `In progress`.
- **25.11.2026 09:25** PR #80 review **FAIL** (docs only; code, tests and secrets pass): status doc header stale, plan contradicts code and PR, one HANDOFF log time off by a minute.
- **25.11.2026 09:17** PR #80 updated to cover MKC-5.4 (title `MKC-5: Database layer`; now closes #5, #76, #77, #78, #79); #5 and #79 to `Testing`.
- **25.11.2026 09:17** MKC-5.4: Supabase result recorded in the status doc and the MKC-5 plan; HANDOFF updated.
- **25.11.2026 09:16** MKC-5.4 (same shell command as commit `a497afb`, 09:16): live check against the user's Supabase project (Session pooler, port 5432, eu-west-1): PostgreSQL 17.12, `vector` 0.8.2 available, not installed; exit 0. Password masked in the output.
- **25.11.2026 09:16** MKC-5.4: `mkc.db.check` added; 16 passed, 1 skipped (POSIX-only); ruff and mypy pass. The password test now checks `user:password@`, because the local password `mkc` also occurs in the test database name.
- **25.11.2026 09:15** MKC-5.4: `tests/db/test_check.py` added; red (`mkc.db.check` missing).
- **25.11.2026** User decisions: run the review agent for PR #80; the user created the Supabase project and put the Session pooler string in `backend/.env`; `httpx2` still open.
- **24.11.2026 21:50** Review agent for PR #80 not started: denied by the session permission check. Stopped: PR #80 waits for review and merge; no `Ready` ticket; MKC-6 depends on MKC-5 (see Blocked).
- **24.11.2026 21:49** MKC-5: HANDOFF records PR #80.
- **24.11.2026 21:49** MKC-5: PR #80 opened (assigned to `qamran`; closes #76, #77, #78; #5 and #79 stay open for the Supabase check); #76, #77 and #78 to `Testing`; #5 stays `In progress`.
- **24.11.2026 21:48** MKC-5.2: with Postgres unreachable the DB tests hung (timeout at 90 s, Windows retries refused connections); the fixture now uses `connect_timeout=5` and fails in about 5 s with "Postgres not reachable … start it with `docker compose up -d db`". Linux container on the compose network: 13 passed (incl. the POSIX SIGTERM test and a live `postgresql://` URL).
- **24.11.2026 21:41** MKC-5: status doc (MKC-4 done, MKC-5 current with Postgres 17, psycopg 3, port 5433, Supabase check open) and README (start the db before the tests) updated; HANDOFF test instructions and next steps updated.
- **24.11.2026 21:41** MKC-5.3: Alembic in `backend/migrations/` (`env.py` takes the URL from `Settings` and passes the engine directly; `script_location = %(here)s/migrations`); revision `0001` enables `vector`. Round-trip test green; `uv run alembic upgrade head`, `current`, `downgrade base` work from `backend/` and with `-c backend/alembic.ini` from the repo root. 12 passed; ruff and mypy pass.
- **24.11.2026 21:40** MKC-5.3: `tests/db/test_migrations.py::test_upgrade_downgrade_roundtrip` added; red (no `alembic.ini`, "No script_location").
- **24.11.2026 21:40** MKC-5.2: `mkc.db.base.Base`, `mkc.db.session.get_engine()` (lazy, one engine per URL) and `get_session()` (commit, rollback, close); all 11 tests green incl. the 3 DB tests against the compose db (throwaway database dropped afterwards); ruff and mypy pass.
- **24.11.2026 21:40** MKC-5.2: default `DATABASE_URL` uses `127.0.0.1:5433`; plan notes why; config tests green.
- **24.11.2026 21:40** MKC-5.2: default-URL test now expects `127.0.0.1:5433`; red. Found because the session tests hung: `localhost` tries IPv6 first and stalls (5 s with `connect_timeout`, open-ended without), while compose binds IPv4 only.
- **24.11.2026 21:36** MKC-5.2: `tests/db/conftest.py` (throwaway database per test session; fails if Postgres is unreachable unless `MKC_SKIP_DB_TESTS=1`) and `tests/db/test_session.py` added; red (`mkc.db` missing).
- **24.11.2026 21:35** MKC-5.2: `Settings.database_url` from `DATABASE_URL` (or `MKC_DATABASE_URL`), default the compose db, `postgres://` and `postgresql://` mapped to `postgresql+psycopg://`; config tests green; ruff and mypy pass.
- **24.11.2026 21:35** MKC-5.2: `tests/test_config.py` added; red (`Settings` has no `database_url`).
- **24.11.2026 21:35** MKC-5.2: plan written; `docker-compose.yml` with service `db` (`pgvector/pgvector:pg17`, `127.0.0.1:5433`, because a native Postgres holds 5432); `docker compose up -d --wait db` gives PostgreSQL 17.12 with `vector` 0.8.7 available. Dependencies: SQLAlchemy 2, psycopg 3, Alembic.
- **24.11.2026 21:33** MKC-5.1: `test_run_stops_on_sigterm` cancels the `sigterm` timer in `finally` and asserts on a `timed_out` event. Red shown: with a `run()` that ignores SIGTERM the test fails via `timed_out`; with a `run()` that fails early the old test let SIGTERM kill pytest (exit 3, no summary), the new one reports the failure.
- **24.11.2026 21:31** MKC-5 sub-issues #76–#79 to `In progress` on the board (GitHub 20:31:01Z–20:31:04Z).
- **24.11.2026 21:30** MKC-5 sub-issues MKC-5.1 (#76), 5.2 (#77), 5.3 (#78), 5.4 (#79) created, linked to #5, assigned to `qamran`.
- **24.11.2026 16:46** MKC-5 (#5) to `In progress`, assigned to `qamran`; branch `mkc-5-database-layer`; HANDOFF.md caught up after PR #75.
- **24.11.2026 16:46** #4, #73 and #74 criteria ticked. MKC-4 complete.
- **24.11.2026 16:45** `main` pushed to `turing` (reflog 16:45:54); `origin/main` == `turing/main` == `1555a92`.
- **24.11.2026 16:45** PR #75 review **PASS**, merged `1555a92` (merge commit); #4, #73, #74 closed and set to `Done` by the board's automation. Two non-blocking test findings (see In progress).
- **24.11.2026 16:34** MKC-4: PR #75 opened (assigned to `qamran`; closes #4, #73, #74); #4, #73 and #74 to `Testing`.
- **24.11.2026 16:34** MKC-4: README status line updated (backend skeleton); HANDOFF: the MKC-3 close-out line split by event time, `httpx2` decision and Docker moved under Blocked.
- **24.11.2026 16:34** MKC-4.2: worker tests enforce their timeout (watchdog stop event, bounded stderr read); `run()` takes an optional stop event. Docker Desktop started; in a Linux container all 5 tests pass, incl. the real SIGTERM test.
- **24.11.2026 16:29** MKC-4: status doc updated (MKC-3 done, MKC-4 current, first application code).
- **24.11.2026 16:29** MKC-4.2: `mkc.worker.main:run()` with SIGTERM/SIGINT stop flag and `mkc-worker` script; tests green on Windows (POSIX subprocess test skipped); ruff and mypy pass.
- **24.11.2026 16:29** MKC-4.2: `tests/worker/test_worker.py` added; red (`mkc.worker` missing).
- **24.11.2026 16:28** MKC-4.1: `mkc.config.Settings` and `mkc.api.app:create_app()`; API tests green; ruff, ruff format and mypy strict pass.
- **24.11.2026 16:28** MKC-4.1: `tests/api/test_health.py` added; red (`mkc.api` missing).
- **24.11.2026 16:28** MKC-4.1: uv project `backend/` (package `mkc`, Python 3.12, FastAPI, pydantic-settings, uvicorn; ruff, mypy strict, pytest); `uv sync` works.
- **24.11.2026 16:27** MKC-4: branch `mkc-4-backend-skeleton`; HANDOFF.md caught up after PR #72; plan written.
- **24.11.2026 16:26** MKC-4 (#4) to `In progress`, assigned to `qamran`; sub-issues MKC-4.1 (#73) and MKC-4.2 (#74) created, assigned, `In progress`. Board auto-add found to be on.
- **24.11.2026 16:25** `main` pushed to `turing` (git reflog 16:25:11); `origin/main` == `turing/main` == `6650cbd`. MKC-3 complete.
- **24.11.2026 16:24** #3 and #71 criteria ticked and board `Done` (GitHub 15:24:51Z–15:24:53Z; the local and GitHub clocks differ by about 20 s).
- **24.11.2026 16:24** PR #72 re-review **PASS**, merged `6650cbd` (merge commit); #3 and #71 closed.
- **24.11.2026 16:23** MKC-3.3: fix commit for the PR #72 findings (15:56 log time; status doc names PR #72; AGENTS.md roles wording); #3 and #71 back to `Testing`.
- **24.11.2026 16:23** #3 and #71 back to `In progress`.
- **24.11.2026 16:22** PR #72 review **FAIL**: the log line for the Turing push and #2 `Done` said 15:57; the events were at 15:56.
- **24.11.2026 16:18** MKC-3.3: PR #72 opened (assigned to `qamran`, closes #71 and #3); #3 and #71 to `Testing`.
- **24.11.2026 16:17** MKC-3.3: docs updated: HANDOFF "Read this first" points to AGENTS.md (roles moved there); status doc; ADR 005 and design doc decision 36 (user: continue without asking, stop only for genuine decisions).
- **24.11.2026 16:17** MKC-3.3: CLAUDE.md added (one line importing AGENTS.md); `check_agents.py` passes (green); lint 0 errors.
- **24.11.2026 16:17** MKC-3.3: AGENTS.md added (sections, rules, review checklist); markdown lint config with line length off.
- **24.11.2026 16:15** MKC-3.3: `scripts/check_agents.py` added; fails while AGENTS.md and CLAUDE.md are missing (red).
- **24.11.2026 16:15** MKC-3: branch `mkc-3-agents-md`; HANDOFF.md caught up after PR #70; design doc "Remotes" line updated.
- **24.11.2026 16:15** MKC-3.3 (#71) created as sub-issue of #3, assigned to `qamran`, on the board as `In progress`.
- **24.11.2026 15:56** `main` pushed to `turing`; `origin/main` == `turing/main` == `7b11612`. #2 criteria ticked, board `Done`.
- **24.11.2026 15:56** PR #70 review **PASS**, merged `7b11612` (merge commit); #2 closed.
- **24.11.2026 15:53** MKC-2: PR #70 fix commit `29bb105` (HANDOFF log times corrected from git, PR #70 logged, ADR 005 context reworded, status doc points to PR #70).
- **24.11.2026 15:52** MKC-2: PR #70 opened (assigned to `qamran`); #2 to `Testing`.
- **24.11.2026 15:51** MKC-2: status doc updated (current ticket, decision 35, README, remotes at `cb35b4b`).
- **24.11.2026 15:51** MKC-2: README.md with intro and links; `check_readme.py` passes (green).
- **24.11.2026 15:51** MKC-2: `scripts/check_readme.py` added; fails on the old one-line README (red).
- **24.11.2026 15:50** MKC-2: design doc (section 14, decisions 32 and 35, feature 0) and backlog MKC-2 entry updated.
- **24.11.2026 15:50** MKC-2: ADR 005 updated to fallback (c), code-only Turing mirror, no token.
- **24.11.2026 15:48** MKC-2 to `In progress`; branch `mkc-2-code-only-mirror`; HANDOFF.md brought up to date. Session restart recommended by the development agent (context high).
- **24.11.2026 15:47** PR #69 re-review **PASS**, merged `cb35b4b`, pushed to `turing`; #68 closed and `Done`, criteria ticked.
- **24.11.2026 15:46** Fix commit for the PR #69 review findings: status doc updated, HANDOFF.md times corrected from git/GitHub, missing log lines added.
- **24.11.2026 15:45** PR #69 review **FAIL** (status doc not updated; wrong clock times in this log; missing log lines). #68 back to `In progress`.
- **24.11.2026 15:44** MKC-2 (#2) redefined by user decision: no issue mirror, Turing repo is code-only, README links to the board; no token needed. Issue body rewritten, `user-task` label removed, assigned to `qamran`.
- **24.11.2026 15:41** PR #69 (MKC-3.2) opened; #68 to `Testing`.
- **24.11.2026 15:41** Commits `86a33f5` (check_handoff.py), `aea4d25` (HANDOFF.md), `3e20f51` (rule in ADR 005 + design doc, decision 34) on `mkc-3-handoff`.
- **24.11.2026 15:40** MKC-3.2 (#68) created, added to the board as `In progress`.
- **24.11.2026 15:39** PR #67 (MKC-3.1) review PASS, merged `7609490`, pushed to `turing`; #66 closed.
- **24.11.2026 15:38** PR #67 opened (assignment rule in ADR 005 + design doc, decision 33; status doc refreshed).
- **24.11.2026 15:37** MKC-3 to `In progress`; sub-issue MKC-3.1 (#66) created; MKC-1 and its sub-issues assigned to `qamran`.
- **24.11.2026 15:35** PR #65 (MKC-1) review PASS, merged `8f9b7d0`, pushed to `turing`; #1 closed. MKC-2 and MKC-3 set to `Ready`.
- **24.11.2026 15:32** PR #65 opened; MKC-1 to `Testing`.
- **24.11.2026 15:24** MKC-1: 60 tickets created (#1–#60); sub-issues #61–#64; templates, repo metadata, branch protection.
- **24.11.2026** Ticket backlog approved and committed; design doc approved after an independent review; ADRs 001–005 written.

## Key links

- Board: <https://github.com/users/qamran/projects/1>
- Repo: <https://github.com/qamran/Messkonzept-Copilot>
- Design doc: `docs/superpowers/specs/241120261330-messkonzept-copilot-design.md`
- Backlog: `docs/superpowers/plans/241120261500-ticket-backlog.md`
- Status doc: `docs/241120261430-project-status.md`
- ADRs: `docs/adr/`
- Board ids for `gh project item-edit`:
  - project `PVT_kwHOAM81l84BtCBN`, Status field `PVTSSF_lAHOAM81l84BtCBNzhrNWmA`
  - options: Backlog `d2ea50c1`, Ready `b02572c8`, In progress `43f5d3e6`, Testing `ba411698`, Done `c7c37bbb`
