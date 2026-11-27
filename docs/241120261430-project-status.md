# Project status: Messkonzept-Copilot

**Last updated:** 27.11.2026, 19:25

This is the living status document. It is updated whenever a decision is made or work is completed. Older brainstorming material lives in `brainstorming internal/` (gitignored and frozen).

## Where we are

- **Phase:** implementation, Phase 0 (foundation). The design doc was **approved by the user on 24.11.2026** (after an independent review, verdict "approve with changes", all required changes applied). The backend skeleton (MKC-4) is the first application code; MKC-5 added the database layer; MKC-6 added secret hygiene and CI; MKC-7 added the frontend and the login check; MKC-8 added containers; MKC-9 added the Helm chart and the kind test; MKC-10 added continuous deployment (merged in PR #109; the first `cd.yml` run deployed the merge commit on 26.11.2026). MKC-11 added nightly backups and a proven restore; MKC-12 added the Codeliste research and the LBS reference data (PR #120). Phase 0 is done; Phase 1 started with MKC-13 (provider layer), MKC-14 (tool registry) and MKC-15 (item loop), all done, and continues with MKC-16 (checkpoints and resume), MKC-17 (run executor), MKC-18 (limits and retries), MKC-19 (tracing) and MKC-20 (baseline, faults, CLI), all done.
- **Restart files:** `HANDOFF.md` (repo root) is the coordinator's running log and next steps, updated with every commit and important ticket change (decision 34); from MKC-168 each parallel lane keeps its own `handoff/lane-<x>.md` (decision 61). This status doc stays the overview of decisions and documents.
- **Board:** <https://github.com/users/qamran/projects/1> (public). Tickets MKC-1 to MKC-60 exist as issues #1 to #60 (issue number = key).
- **Done:** MKC-1 (ticket workflow and repo setup, PR #65), MKC-2 (code-only Turing mirror, README with links, PR #70), MKC-3 (agent instructions: assignment rule PR #67, HANDOFF.md PR #69, AGENTS.md + CLAUDE.md PR #72), MKC-4 (backend skeleton: uv project `backend/`, package `mkc`, FastAPI `/health` and `/api/version`, worker with clean SIGTERM shutdown, ruff and mypy strict, PR #75), MKC-5 (database layer: compose Postgres 17 + pgvector, SQLAlchemy 2, Alembic, `python -m mkc.db.check`, Supabase connection checked; PR #80), MKC-6 (secret hygiene, markdown lint, CI with required checks; PR #86), MKC-7 (frontend skeleton with Clerk; PR #91), MKC-8 (containers, Compose, GHCR image; PR #97), MKC-9 (Helm chart and kind test; PR #103), MKC-10 (continuous deployment; PR #109), MKC-11 (backups and restore drill; PRs #115 and #116), MKC-12 (PR #120), MKC-13 (PR #127), MKC-14 (PR #131), MKC-15 (PR #138), MKC-16 (PR #145). Each after a review-agent PASS; both remotes at the latest merge commit.
- **MKC-5 details** (database layer, PR #80, plan `docs/superpowers/plans/241120262130-mkc-5-database-layer.md`):
  - `docker compose up db` (repo root; the file is `compose.yaml` since MKC-8): Postgres 17 with pgvector (`pgvector/pgvector:pg17`; Supabase hosts Postgres 17) on `127.0.0.1:5433`, dev-only credentials
  - `DATABASE_URL` setting, mapped to the psycopg 3 driver; SQLAlchemy 2; `mkc.db.base.Base`, `mkc.db.session.get_session()`
  - Alembic in `backend/migrations/`; revision `0001` enables `vector`; the round-trip test runs in a throwaway database
  - DB tests fail when Postgres is unreachable (`MKC_SKIP_DB_TESTS=1` skips them on purpose); MKC-6 needs a pgvector service container in CI
  - Supabase check (MKC-5.4), 25.11.2026: `python -m mkc.db.check` (read-only) against the user's Supabase project, via the Session pooler (port 5432, IPv4; region eu-west-1). Result: PostgreSQL 17.12, `vector` 0.8.2 available, not yet installed (the migrations install it; running them on Supabase belongs to the deploy tickets). The connection string lives only in the gitignored `backend/.env`; `Settings` does not read `.env`, so the tests never touch Supabase. Run it with `cd backend && uv run --env-file .env python -m mkc.db.check`.
  - Supabase project settings: use the Session pooler, not the direct connection (IPv6 only) or the Transaction pooler (port 6543, no session state). The Data API is not used by the backend.
- **MKC-6 details** (secret hygiene and CI, merged in PR #86; plan `docs/superpowers/plans/251120260935-mkc-6-secret-hygiene-ci.md`), sub-issues MKC-6.1 to MKC-6.5 (#81–#85):
  - `httpx2` for the test client; Starlette deprecation warnings fail the tests (decision 37)
  - `.gitignore` (PDFs, `.env*` except `.env.example`, renders, caches), `.env.example` (an empty value means "use the default": `Settings` ignores empty variables), `.pre-commit-config.yaml` (gitleaks, ruff, end-of-file fixer; install with `uvx pre-commit install`)
  - all tracked Markdown passes markdownlint
  - `.github/workflows/ci.yml`: backend (pgvector service; every backend test runs on Linux, none skipped), frontend (placeholder until MKC-7), gitleaks (fake-key self-test, full history), dependency-scan (pip-audit), docs (markdownlint, check scripts)
  - the five jobs are required checks on `main`, branch must be up to date (decision 38, ADR 005)
  - `scripts/check_workflows.py` bans secrets and write permissions in every workflow. MKC-8 narrowed it for one job only (`packages: write` in `publish`, decision 41). MKC-10 narrowed it again: secrets only in `cd.yml`, only in jobs in the `production` environment (decision 47).
- **MKC-7 details** (frontend skeleton with Clerk, merged in PR #91; plan `docs/superpowers/plans/251120261119-mkc-7-frontend-skeleton.md`), sub-issues MKC-7.1 to MKC-7.4 (#87–#90):
  - Clerk development instance for every environment (decision 39, ADR 002); the user created it, with the `role` session-token claim, the admin (the user's Google account) and a test user
  - backend `mkc.api.auth`: `require_user`, `require_admin`, `GET /api/me`, `GET /api/admin/ping`; tokens checked with the public JWKS only (decision 40); `apiFetch` keeps every request on the `VITE_API_URL` origin (review fix); CORS allow-list for the local Vite dev server
  - `frontend/`: Vite, React, TypeScript, Tailwind, shadcn/ui, `@clerk/react`, `react-router`; `apiFetch`, `RequireAdmin`; vitest
  - CI: the frontend job runs lint, typecheck, test and build; the dependency scan adds `npm audit`
- **MKC-8 details** (containers and local Compose, merged in PR #97; plan `docs/superpowers/plans/251120261327-mkc-8-containers-compose.md`), sub-issues MKC-8.1 to MKC-8.5 (#92–#96):
  - `backend/Dockerfile`: one image, multi-stage, uid 10001, base images pinned by digest, `MKC_COMMIT` build argument; API by default, `mkc-worker` for the worker
  - `compose.yaml` (replaces `docker-compose.yml`): db, api, worker, frontend; `backend/.env` optional; `scripts/compose_smoke.sh` checks the whole stack as its own project on other ports
  - CI job `image` (a required check on `main` since 25.11.2026 13:52): smoke test, Grype scan, `linux/amd64,linux/arm64` build; CI job `publish`: pushes `ghcr.io/qamran/messkonzept-copilot-backend` (`<commit sha>`, `main`) on `main` only
  - `scripts/check_containers.py`; `scripts/check_workflows.py` allows `packages: write` only in the guarded `publish` job (decision 41, ADR 002)
  - first push from `main` (`35dc1fe`): `ghcr.io/qamran/messkonzept-copilot-backend:35dc1fe…` and `:main`, amd64 + arm64; the package is public
- **MKC-9 details** (Helm chart and kind test, merged in PR #103; plan `docs/superpowers/plans/251120261520-mkc-9-helm-kind.md`), sub-issues MKC-9.1 to MKC-9.5 (#98–#102):
  - worker heartbeat file (`MKC_WORKER_HEARTBEAT_FILE`) and `mkc-worker-health`, so the worker pod has a real probe
  - `deploy/helm/mkc/`: API Deployment (replicas from values), worker Deployment (`replicas: 1`, `Recreate`, grace period 300 s), Service, Ingress (cert-manager TLS), Secret from values or `existingSecret`, ConfigMap from `env`; probes, limits, uid 10001, read-only root (decision 42, ADR 002)
  - `scripts/check_helm.py` (static chart rules) and `scripts/kind_smoke.sh` (install on kind)
  - CI job `kind`: `helm lint --strict` and the kind smoke test; a required check on `main`; `publish` needs it
- **MKC-10 details** (continuous deployment, merged in PR #109; plan `docs/superpowers/plans/251120261710-mkc-10-cd.md`), sub-issues MKC-10.1 (#106), 10.2 (#105), 10.3 (#104), 10.4 (#107), 10.5 (#108):
  - `MKC_CORS_ORIGIN_REGEX`: the Vercel previews pass CORS and the `azp` check (decision 45)
  - `VersionWarning`: the page warns when the API runs another commit (decision 46); `frontend/vercel.json`
  - VM: user `mkc-deploy` with a forced command (`deploy/vm/mkc-deploy`, commits on `main` only), rights in namespace `mkc` only (Pod Security `restricted`), `/etc/mkc/values.yaml`, Secret `mkc-secrets`
  - `.github/workflows/cd.yml` and `scripts/cd_deploy.sh`: image wait, SSH deploy, smoke test, rollback, then Vercel production (decision 47)
  - first deploy and rollback drill on 25.11.2026: `https://92-6-240-17.sslip.io/api/version` live (Let's Encrypt certificate); a forced failing smoke test rolled back to revision 1
  - `check_workflows.py` now allows secrets in `cd.yml` only, only in `production` jobs (the change MKC-6 asked for)
  - first `cd.yml` run (26.11.2026, run 45777350297, merge commit `edd4406`): `/api/version` = `edd4406…`; Vercel production built by the CLI with the same commit (no warning), no Git-made production deployment; a preview signed in and `/api/me` answered (role admin)
  - the preview-origin risk (decision 45) was accepted by the user on 26.11.2026; non-blocking review findings are listed in HANDOFF.md
- **MKC-11 details** (backups and restore drill, done; PR #115 merged as `0b6f49a`, PR #116 as `33a3a65`; plan `docs/superpowers/plans/261120260951-mkc-11-backups.md`), sub-issues MKC-11.1 (#110) to 11.5 (#114). Two PRs: code first, then the drill results:
  - table `backup_runs` (migration 0002); a Helm hook Job runs `alembic upgrade head` on every install and upgrade; migrations are additive only (decision 48)
  - `mkc-backup`: pg_dump 17 of schema `public` → gzip → write-only Object Storage link; `postgresql-client-17` in the image (decision 49)
  - `GET /api/admin/backup-status` with a `stale` flag (26 h)
  - Helm CronJob (03:30 Europe/Berlin, on in production); `scripts/restore_backup.sh`, run by the Compose smoke test on every CI run
  - done on 26.11.2026 (MKC-11.5): the Oracle bucket, lifecycle rule and upload link (user); the first production backup (`nightly/mkc-20261126T115613Z.sql.gz`, 1139 bytes, 8 s); the restore drill (row counts match production: `alembic_version` 1, `backup_runs` 1; 4 s). Steps and numbers: runbook "First backup and restore drill"
  - the runbook also lists where every outside setting and secret lives ("Where every setting and secret lives"; `scripts/check_runbook.py` checks that it names every workflow secret, both keys of `mkc-secrets`, the frontend's `VITE_` variables and the local key files)
- **Server setup** (25.11.2026, for MKC-10; decisions 43 and 44; runbook `docs/251120261645-runbook.md`):
  - Oracle VM `mkc-k3s` (4 OCPUs, 24 GB, arm64, `92.6.240.17`); ports 80 and 443 open, 6443 closed
  - k3s v1.37.2 with Traefik; cert-manager v1.21.3 with Let's Encrypt staging and prod issuers
  - API host `92-6-240-17.sslip.io`
  - Vercel project `messkonzept-copilot`; GitHub environment `production` with `VERCEL_TOKEN`
- **Current ticket:** MKC-168 (#168), parallel lanes: workflow, gate and checks (plan `docs/superpowers/plans/271120261901-parallel-lanes.md`, decision 61), sub-issues MKC-168.1 to 168.5 (#169–#173). Built on the branch: `scripts/pre_pr.sh` with `check_pre_pr.py` and `commit_report.py`; lane restart files `handoff/` checked by `check_handoff.py`; `test_single_migration_head`; AGENTS.md roles (coordinator, test agent, development agent, review agent) and section "Parallel lanes"; decision 61; ADR 005 amendment; backlog lanes and wave 1; decision-number blocks below. No model spend.
- **MKC-20 done** (PR #167 merged as `4dc0302` on 27.11.2026, review PASS after one FAIL round on red CI, deployed the same day). Built: `mkc.harness.mode` (`MKC_HARNESS_MODE`, migration 0011 `run.mode`), baseline as the same loop with five switches off (`RunMemory`, `execute_run`), `mkc.harness.faults` and `backend/data/e4_faults.yaml`, the CLI `mkc run start|resume|status|inspect` (Typer 0.29.3) with the resume edge `stopped -> running`, and the PR #161 tracing findings 1 to 3; runbook section "Baseline, faults and the CLI"; decision 60. No model spend.
- **MKC-19 done** (PR #161 merged as `21f5eb8` on 27.11.2026, review PASS, deployed the same day; production has the Langfuse keys). Built: migration 0010 (`run.trace_id`, table `run_log`), `mkc.observability` (`Tracer`, `LangfuseSink`, the demo run), the worker sends every run to the tracer; runbook section "Tracing"; decision 59; finding 18#1 fixed. **Real run in Langfuse (27.11.2026, 15:55):** local run 1, trace [`768b021193b64891963f3b0c9fd74ea2`](https://cloud.langfuse.com/project/cmwumgc8c03ohad0g3b3holvp/traces/768b021193b64891963f3b0c9fd74ea2) (private project, so the evidence is the demo's read-back: Langfuse holds 3 generations and 3 tool observations, the same as `run_log`, none with input or output). **Spend for the ticket:** €0.003364 (three live calls). Langfuse setup: runbook "Set up Langfuse".
- **MKC-18 done** (PR #155 merged as `16beb56` on 27.11.2026, review PASS, deployed the same day). Built: migration 0009 (`run.started_at`, `item.attempts_without_progress`), `mkc.harness.limits` (`Limits` from ten new settings, `StopReason`, `StopEvent`, `stop_run`), `mkc.harness.retry` (backoff 2/4/8/16 s, `Retry-After`, 180 s turn deadline), `TransientModelError` and `ModelAuthError` from `ModelClient` (`classify_error`), one corrective re-prompt, tool-retry and resume caps, setup errors and provider outages stop the run; the executor's error holes closed; runbook section "Limits and retries"; decision 58. No model spend.
- **MKC-17 done** (PR #150 merged as `0f9a413` on 27.11.2026, review PASS, deployed the same day). Built: migration 0008 (`run.lease_owner`, `run.lease_expires_at`), `mkc.worker.lease` (`claim_run`, `renew_lease`, `release_lease`, `fence`, `mark_waiting`), `mkc.worker.executor.Executor` (heartbeat thread, `graceful_shutdown`, waits out database outages), run state `waiting_for_database`, the worker runs the executor; runbook section "Worker lease and outages"; decision 57. No model spend.
- **MKC-16 done** (PR #145 merged as `266c37d` on 27.11.2026, review PASS after one FAIL round, deployed the same day). Built: `mkc.harness.checkpoint` (`save_turn`, `load_resume_context`), `mkc.harness.blobs` (migration 0005, `blob`), `mkc.harness.cache` (migration 0006, `tool_cache`), `mkc.harness.drafts` (migration 0007, `draft`), `process_run` resumes `running` items, `scripts/check_text_files.py`; decision 56. No model spend. The Supabase Storage bucket `mkc-storage` and its S3 key exist since 27.11.2026, for MKC-21.
- **MKC-15 done** (PR #138 merged as `ff76b94` on 27.11.2026, review PASS, deployed the same day). Built: `mkc.harness.states` (edge table, `transition`), `ToolEnv`, migration 0004 (`run`, `item`, `turn`), `mkc.harness.queue` (`next_item`, `settle_run`), `mkc.harness.loop` (`run_item`, `process_run`); decision 54. No model spend.
- **MKC-14 done** (PR #131 merged as `1a42369` on 26.11.2026, review PASS, deployed the same day). Built: `mkc.harness.tools` (`Tool`, `ToolResult`, `ToolError`, `ToolTrace`, `ToolRegistry`) and `mkc.harness.registry.default_registry()` (the six item tools and four run-level operations of design 8.1, as `not_implemented` placeholders until their tickets); decision 53 (what `side_effect` means; `save_draft` is an item tool, harness code enqueues the approval), confirmed by the user on 27.11.2026; AGENTS.md points to it.
- **MKC-13 done** (PR #127 merged as `ab62236` on 26.11.2026, review PASS, deployed the same day). Built: `mkc.models` (`ModelClient` with `chat`, `chat_with_tools`, `vision`, `chat_structured`; role mapping and prices in `models.yaml`; record/replay; provider factory with OpenRouter zero-data-retention routing); decision 52.
- **Live contract tests (MKC-13.6), 26.11.2026 15:58–16:00:** `cd backend && uv run --env-file .env pytest -m live tests/models/test_contract_live.py -v -s`: **12 passed**. Tool-call round-trip, structured output and vision (not a criterion; a 64×64 red PNG) for OpenRouter (`google/gemini-3.5-flash-lite`, zero-data-retention routing), Gemini (`gemini-3.5-flash-lite`, free tier), Anthropic (`claude-haiku-5-5`) and the Meta API (`muse-spark-1.3` on `api.meta.ai/v1`). The first runs (15:39–15:46) had no Meta key; Meta said "white" for a 16×16 image and "red" at 64×64, so the test image is 64 px. **Spend for the ticket:** under €0.02 by the price table (all runs plus two Meta probe calls; Anthropic prices are an OpenRouter stand-in, Gemini counted as free tier).
- **MKC-36 (lane B), on branch `mkc-36-site-facts`:** sub-issues MKC-36.1 to 36.5 (#176, #177, #178, #180, #183). Built: `mkc.advisor.facts` (`SiteFacts`, `FactsExtraction`, `extract_facts`), `mkc.advisor.questions` (`required_questions`), `mkc.advisor.api` (`POST /api/advisor/facts`, `POST /api/advisor/questions`); the UI `FactsCard` (confirm and edit) and `AdvisorPage` on `/advisor`; decisions 65 and 66. **Spend:** €0.013138 (three live calls on synthetic text to check the schema with the real provider, 27.11.2026 20:49).
- **MKC-46 (lane C), decision-layer spike, 27.11.2026: the Jev call path via OpenRouter works** (ADR 004 amendment, decisions 68 and 69; sub-issues MKC-46.1 to 46.3, #192–#194). Built: `langchain-typesafe==0.1.0`, `MKC_DECISION_BACKEND` (default `llm`, the fallback stays the default) and `MKC_DECISION_MODEL`, `build_decision_model` (base URL `https://openrouter.ai/api`, path `/api/v1/systemone`, zero-data-retention routing in every body), `mkc.decision` (`DecisionClient`, typed answers, `DecisionError`). Live: `uv run --env-file .env pytest -m live tests/decision/test_jev_live.py -v`: "1 passed in 10.26s" (20:47:56); `~typesafe/jev-latest` resolved to `typesafe/jev-1.14-20261014`. **Spend for the ticket (six live calls, 20:40–20:48):** three printed `usage.cost` 0.000011886, 0.000011886 and 0.000017934 USD; two 404 routing probes and the pytest run printed no cost. Call log: `handoff/lane-c.md`.
- **Next:** merge MKC-168, then wave 1 (MKC-21, MKC-36, MKC-46, MKC-49 in parallel lanes).

## Key documents

| Document | Path |
|---|---|
| Capstone grading criteria (shares, new evals criterion, evidence per criterion) | `docs/271120261003-eval-criteria-capstone.md` |
| Design doc | `docs/superpowers/specs/241120261330-messkonzept-copilot-design.md` |
| Architecture Decision Record (ADR) 001: custom harness on LangChain plumbing | `docs/adr/241120261430-adr-001-harness.md` |
| ADR 002: Vercel frontend, k3s backend (+ worker, CD hardening) | `docs/adr/241120261430-adr-002-hosting.md` |
| ADR 003: Supabase instead of SQLite (+ restore drill) | `docs/adr/241120261430-adr-003-database.md` |
| ADR 004: narrow RAG corpus and decision layer with LLM fallback | `docs/adr/241120261441-adr-004-rag-and-decision-layer.md` |
| ADR 005: ticket workflow (GitHub Issues + public Projects board) | `docs/adr/241120261456-adr-005-ticket-workflow.md` |
| AGENTS.md (project rules for agents; CLAUDE.md imports it) | `AGENTS.md` |
| HANDOFF.md (agents' restart file) | `HANDOFF.md` |
| Runbook (server setup; deploy and rollback; restore drill) | `docs/251120261645-runbook.md` |
| Ticket backlog (implementation plan, MKC-1 to MKC-60) | `docs/superpowers/plans/241120261500-ticket-backlog.md` |
| README (intro + links for both repos) | `README.md` |
| Official brief | `AE.CAP_afa.md` |

## Decisions so far (summary; the full log of 61 decisions is in design doc section 18)

- **Idea:** Messkonzept-Copilot. It extracts operator Messkonzept PDFs into structured, LBS-keyed records with human approval, and gives household site advice with citations.
- **Primary user:** MSB, VNB and energy-IT staff working across grid areas; installers are secondary; plus a public read-only demo.
- **Operators:** Stromnetz Berlin + SachsenNetze (both low voltage). §14a Modul 3 is out of scope.
- **Harness (ADR 001):**
  - custom loop and control; LangChain only for model and tool plumbing; no LangGraph
  - run-level operations are code, never model tools; a side-effect tool can't be registered in the item context (decision 53)
  - one transition function for every run and item state; tools get the item's ids from the harness, not the model (decision 54)
  - checkpoints at turn boundaries; an interrupted item resumes from its last complete turn; large results as blob refs; a tool cache keyed by code version; `save_draft` idempotent by a key from the harness (decision 56)
  - a single-replica worker with a Postgres lease
  - limits on steps, wall time, cost, tool retries and resumes, each with its own stop reason; transient model errors retried with backoff under a turn deadline; setup errors and outages stop the run (decision 58)
- **Core also includes (ADR 004):**
  - RAG over a narrow corpus: EnWG §14a, MsbG, BK6-22-300, BK8-22/010-A, operator texts
  - a decision layer (Jev via OpenRouter after a spike; LLM fallback by default)
- **New grading criterion (27.11.2026, decision 55):** Turing College added "effective use of evals" (13 % of the score; evals are now required; the other weights dropped, see `docs/271120261003-eval-criteria-capstone.md`). The plan adds E9 (agent trajectory), per-case regression in the runner and CI gate, and the improvement log `eval/iterations.md`.
- **Evaluation:**
  - E1–E9 (E9 agent trajectory, decision 55)
  - independent gold: a different drafting model, blind subsets, a dev/test split
  - E4 with a no-fault arm and replayed fault runs
  - a CI eval gate
- **Stack:**
  - FastAPI + React (Vite, shadcn/ui), Clerk login
  - Supabase Postgres + Storage (ADR 003)
  - Langfuse tracing
  - providers: OpenRouter (default, zero data retention), Gemini, Anthropic, Meta API (the Meta Llama API closed on 6 July 2026; decision 52)
- **DevOps (ADR 002):**
  - Docker, GitHub Actions (CI + eval gate + CD in a protected environment, SSH deploy), GHCR, Helm
  - kind in CI, k3s on Oracle Always Free, Vercel for the frontend
  - nightly backups to Oracle Object Storage plus one restore drill
  - deploy approvals: the coordinator (the development agent when no lanes run) approves both `production` gates after a PASS merge with green CI; the user can still reject (decisions 51 and 61)
- **Repos:** `origin` = <https://github.com/qamran/Messkonzept-Copilot> (personal, public, home); `turing` = the Turing submission mirror. `main` is pushed to both after every merge; both at the latest merge commit (named in HANDOFF.md). Turing's initial commit incl. their brief `AE.CAP_afa.md` was pushed to `origin` on 24.11.2026 with the user's OK.
- **Ticket workflow (ADR 005):** GitHub Issues + sub-issues on a public Projects board (`Backlog → Ready → In progress → Testing → Done`); `MKC-<n>` keys in titles, branches and commits; the Turing repo as a code-only mirror with no issues and no token, the README linking the board (ADR 005 option (c), decision 35); tickets, sub-issues and PRs assigned to `qamran` (decision 33); the development agent continues without asking and stops only for genuine decisions (decision 36); rules for both agents in `AGENTS.md`; one branch per ticket; the **development agent (Opus 5.5)** builds and moves tickets to Testing, the **review agent (Fable)** reviews, merges after green CI and closes; started in-session with "next ticket". **Parallel lanes (decision 61, ADR 005 amendment):** a coordinator, a test agent and a development agent per lane, a review agent per PR after green checks; tickets that can run in parallel are built now regardless of phase; PRs merge as soon as they are ready; Phase 7 code may reach production before the Phase 6 release, and the release notes say which parts are unused; `scripts/pre_pr.sh` runs CI's exact commands before every PR.
- **Not used:** hupe1980/mako, in any form.
- **Budgets:** LLM €20–30; user verification 10–12 h.
- **Feature list:** 82 features across Phases 0–8, plus a deferred list. **Phase 6 is the submittable release;** RAG and the decision layer follow in Phase 7.

## Decision numbers per lane

Parallel lanes write the design doc's decision log at the same time, so each lane uses only its block (decision 61). Unused numbers are marked "not used" at the wave's end.

| Numbers | Owner | Wave |
|---|---|---|
| 61 | coordinator (parallel lanes, MKC-168) | setup |
| 62–64 | lane A, extraction (MKC-21 and on) | 1 |
| 65–67 | lane B, advisor (MKC-36 and on) | 1 |
| 68–70 | lane C, decision layer (MKC-46 and on) | 1 |
| 71–73 | lane D, RAG (MKC-49 and on) | 1 |

## Open items

- [x] User approval of the design doc (24.11.2026)
- [x] Development plan written: ticket backlog MKC-1 to MKC-60, each with goal, scope, test and success criteria (24.11.2026)
- [x] User review of the ticket backlog (approved 24.11.2026)
- [x] Tickets created on the board (MKC-1, 24.11.2026)
- [ ] User setup tasks:
  - [x] Supabase project (Postgres + private bucket) (25.11.2026)
  - [x] Vercel account linked to the personal repo (25.11.2026, project `messkonzept-copilot`)
  - [ ] provider API keys with spending caps
  - [x] GitHub Secrets and the protected `production` environment (25.11.2026, `VERCEL_TOKEN`)
  - [x] a host name with TLS for the backend API (25.11.2026, `92-6-240-17.sslip.io`, decision 43)
  - [x] Oracle VM with k3s (25.11.2026, decision 44)
- [x] Research: BDEW Codeliste der Lokationsbündelstrukturen (version, format, licence) (26.11.2026, `docs/261120261404-codeliste-research.md`, decision 50)
- [x] Spike: the Jev call path via OpenRouter (start of Phase 7) (27.11.2026, MKC-46: works, ADR 004 amendment)

## Evidence from spikes (24.11.2026)

- **Stromnetz Berlin:**
  - text is clean
  - plain pdftotext tables shift rows (wrong data), while pdfplumber reads them correctly
  - vector diagrams are readable by vision
  - the stated LBS codes match the LBS table
- **SachsenNetze:** 11 concepts, two per page; diagrams are raster images (vision only); no LBS codes, so they must be inferred.
- **Netze Heidelberg (dropped):** a medium-voltage form with raster diagrams and printed formulas.
- **OpenRouter:** `~typesafe/jev-latest` is listed (text + image → decisions); `typesafe/jev-router` is callable as a chat model.

## Independent review (24.11.2026)

A Fable reviewer judged the design "approve with changes". Applied:

- harness consistency
- the decision-layer spike first
- the submittable cut line
- independent gold
- an informative E4
- fixed references
- a public demo
- CI/CD hardening
- the Clerk preview check (done in MKC-7: development instance everywhere, decision 39)
- the primary user
- Modul 3 out of scope

User choices:

- 10–12 h of verification
- a narrow RAG corpus
- one restore drill
- cut features moved to the deferred list
