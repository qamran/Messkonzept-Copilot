# HANDOFF

**Last updated:** 25.11.2026, 09:41

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
  - Both at `8d88c38` (merge of PR #80).
- **`main` is protected:** PRs only, enforced for admins. No required CI checks until MKC-6.
- **Agent rules:** `AGENTS.md` (CLAUDE.md imports it). The development agent continues without asking and stops only for genuine decisions (decision 36).
- **Done:**
  - MKC-1: board, labels, tickets, templates, branch protection (PR #65)
  - MKC-2: code-only Turing mirror, README with links, `scripts/check_readme.py` (PR #70)
  - MKC-3: assignment rule (PR #67), HANDOFF.md (PR #69), AGENTS.md + CLAUDE.md + `scripts/check_agents.py` (PR #72)
  - MKC-4: backend skeleton in `backend/` (uv, Python 3.12, package `mkc`): Settings, FastAPI `/health` + `/api/version`, worker with clean SIGTERM shutdown; ruff + mypy strict (PR #75)
  - MKC-5: database layer: compose Postgres 17 + pgvector on `127.0.0.1:5433`, SQLAlchemy 2, Alembic, `python -m mkc.db.check`; Supabase connection checked via the Session pooler (PR #80)
- **How to test the backend:** `docker compose up -d db` (repo root; Postgres 17 + pgvector on `127.0.0.1:5433`), then `cd backend && uv sync && uv run pytest`. The DB tests fail if the db is down; `MKC_SKIP_DB_TESTS=1` skips them on purpose. Windows skips one POSIX-only worker test; run it in Linux with the Docker command in PR #75.

## In progress

- **MKC-6** (#6), secret hygiene and CI. Status `In progress`, assigned to `qamran`. Branch `mkc-6-secret-hygiene-ci`. Plan: `docs/superpowers/plans/251120260935-mkc-6-secret-hygiene-ci.md`.
  - MKC-6.1 (#81): `httpx` → `httpx2`; `StarletteDeprecationWarning` is an error in pytest (user decision 25.11.2026: switch now). Done on the branch.
  - MKC-6.2 (#82): `.gitignore`, `.env.example`, `.pre-commit-config.yaml`, `scripts/check_secret_hygiene.py`. Done on the branch.
  - MKC-6.3 (#83): all tracked Markdown passes markdownlint.
  - MKC-6.4 (#84): `.github/workflows/ci.yml`, `scripts/check_workflows.py`.
  - MKC-6.5 (#85): CI jobs as required checks on `main` (only after CI is green on the PR).

## Next steps

1. MKC-6 (checklist above).
2. MKC-7 (frontend skeleton; turns on the CI frontend job).

## Blocked / waiting on user

- **Docker Desktop** must be running for MKC-5 (`docker compose up db`). The development agent started it on 24.11.2026; if it is stopped after a restart, start it again.
- Later setup tasks (listed in design doc section 13): Vercel account, provider API keys with caps, GitHub `production` environment, a domain with TLS. The Supabase project exists (created by the user on 25.11.2026).

## Recent log

Newest first. Times are local (CET), taken from git and GitHub.
- **25.11.2026 09:41** MKC-6.2: `.gitignore` (PDFs, `.env*` except `.env.example`, renders, caches, `node_modules`, `dist`), `.env.example` (no values), `.pre-commit-config.yaml` (gitleaks v8.30.1, ruff-check and ruff-format v0.17.6, end-of-file-fixer v6.0.0); `check_secret_hygiene.py` green; `uvx pre-commit run --all-files` passes; no tracked file is ignored.
- **25.11.2026 09:37** MKC-6.2: `scripts/check_secret_hygiene.py` added; red (PDFs, `.env.local`, renders, caches and `node_modules` not ignored; `.env.example` and `.pre-commit-config.yaml` missing).
- **25.11.2026 09:36** MKC-6.1: dev dependency `httpx` → `httpx2` 2.16.2 (adds `truststore` 0.10.5); 16 passed, 1 skipped, **no warnings**; ruff and mypy pass.
- **25.11.2026 09:35** MKC-6.1: pytest turns `StarletteDeprecationWarning` into an error; red (`tests/api/test_health.py` fails at collection: "Using `httpx` with `starlette.testclient` is deprecated").
- **25.11.2026 09:35** MKC-6: plan written; status doc (MKC-5 done, MKC-6 current) and HANDOFF caught up after PR #80. Pre-checks: gitleaks v8.30.1 finds no leaks in the 62 commits of history and does flag a runtime-built fake `ghp_` token; `httpx2` 2.16.2 is from the pydantic org; the `gh` token has the `workflow` scope; markdownlint-cli2 0.18.1 reports about 270 errors on tracked Markdown.
- **25.11.2026 09:34** MKC-6 sub-issues MKC-6.1 (#81), 6.2 (#82), 6.3 (#83), 6.4 (#84), 6.5 (#85) created, linked to #6, assigned to `qamran`, `In progress`; branch `mkc-6-secret-hygiene-ci`.
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

- Board: https://github.com/users/qamran/projects/1
- Repo: https://github.com/qamran/Messkonzept-Copilot
- Design doc: `docs/superpowers/specs/241120261330-messkonzept-copilot-design.md`
- Backlog: `docs/superpowers/plans/241120261500-ticket-backlog.md`
- Status doc: `docs/241120261430-project-status.md`
- ADRs: `docs/adr/`
- Board ids for `gh project item-edit`:
  - project `PVT_kwHOAM81l84BtCBN`, Status field `PVTSSF_lAHOAM81l84BtCBNzhrNWmA`
  - options: Backlog `d2ea50c1`, Ready `b02572c8`, In progress `43f5d3e6`, Testing `ba411698`, Done `c7c37bbb`
