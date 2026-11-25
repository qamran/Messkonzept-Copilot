# HANDOFF

**Last updated:** 25.11.2026, 11:33

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
  - Both at `410a178` (merge of PR #86).
- **`main` is protected:** PRs only, enforced for admins. Required checks since 25.11.2026 09:50 (MKC-6.5): the `ci` jobs `backend`, `frontend`, `gitleaks`, `dependency-scan` and `docs`; the branch must be up to date with `main`.
- **Agent rules:** `AGENTS.md` (CLAUDE.md imports it). The development agent continues without asking and stops only for genuine decisions (decision 36).
- **Done:**
  - MKC-1: board, labels, tickets, templates, branch protection (PR #65)
  - MKC-2: code-only Turing mirror, README with links, `scripts/check_readme.py` (PR #70)
  - MKC-3: assignment rule (PR #67), HANDOFF.md (PR #69), AGENTS.md + CLAUDE.md + `scripts/check_agents.py` (PR #72)
  - MKC-4: backend skeleton in `backend/` (uv, Python 3.12, package `mkc`): Settings, FastAPI `/health` + `/api/version`, worker with clean SIGTERM shutdown; ruff + mypy strict (PR #75)
  - MKC-5: database layer: compose Postgres 17 + pgvector on `127.0.0.1:5433`, SQLAlchemy 2, Alembic, `python -m mkc.db.check`; Supabase connection checked via the Session pooler (PR #80)
  - MKC-6: secret hygiene (`.gitignore`, `.env.example`, pre-commit), markdown lint, CI (`backend`, `frontend`, `gitleaks`, `dependency-scan`, `docs`) as required checks on `main`; `httpx2` (PR #86)
- **How to test the backend:** `docker compose up -d db` (repo root; Postgres 17 + pgvector on `127.0.0.1:5433`), then `cd backend && uv sync && uv run pytest`. The DB tests fail if the db is down; `MKC_SKIP_DB_TESTS=1` skips them on purpose. Windows skips one POSIX-only worker test; run it in Linux with the Docker command in PR #75.

## In progress

- **MKC-7** (#7), frontend skeleton with Clerk. Status `In progress`, assigned to `qamran`. Branch `mkc-7-frontend-skeleton`. Plan: `docs/superpowers/plans/251120261119-mkc-7-frontend-skeleton.md`.
  - Sub-issues (all `In progress`, assigned to `qamran`, linked to #7): MKC-7.1 (#87) backend token check, MKC-7.2 (#88) frontend scaffold and CI, MKC-7.3 (#89) `apiFetch` and `RequireAdmin`, MKC-7.4 (#90) Clerk decision and local check.
  - **User decision (25.11.2026):** Clerk development instance for every environment, permanently (no Vercel Pro, so production keys can't run on `*.vercel.app` previews). Sign-in by email and Google; the user's Google account is the admin. Still to be written into ADR 002 and the design doc (MKC-7.4).
  - **Clerk setup done by the user:** development instance; session-token claim `"role": "{{user.public_metadata.role}}"`; admin = public metadata `{"role": "admin"}`; one test non-admin (`mkc-user+clerk_test@example.com`, code `424242`). Publishable key in `frontend/.env.local` (gitignored). Issuer `https://better-cicada-5480.clerk.accounts.dev` (public) in `backend/.env` as `MKC_CLERK_ISSUER`.

## Next steps

1. MKC-7.2: frontend scaffold (`frontend/`: Vite + React + TS + Tailwind + shadcn/ui, ESLint, vitest); the CI frontend job turns on with `frontend/package.json`.
2. MKC-7.3: `apiFetch` and `RequireAdmin`, test-first.
3. MKC-7.4: ADR 002, design doc, status doc; local check of the three login states with the user.
4. MKC-8 (backend container image on GHCR; image scan in CI).

## Blocked / waiting on user

- **Local login check for MKC-7.4:** the user signs in once as admin (Google) and once as the test user, when the frontend is ready.
- **Docker Desktop** must be running for the local DB tests (`docker compose up -d db`). If it is stopped after a restart, start it again. CI uses its own Postgres service.
- Later setup tasks (listed in design doc section 13): Vercel account, provider API keys with caps, GitHub `production` environment, a domain with TLS. The Supabase project exists (created by the user on 25.11.2026).

## Recent log

Newest first. Times are local (CET), taken from git and GitHub.

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
