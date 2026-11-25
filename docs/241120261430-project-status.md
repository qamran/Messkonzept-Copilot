# Project status: Messkonzept-Copilot

**Last updated:** 25.11.2026, 12:15

This is the living status document. It is updated whenever a decision is made or work is completed. Older brainstorming material lives in `brainstorming internal/` (gitignored and frozen).

## Where we are

- **Phase:** implementation, Phase 0 (foundation). The design doc was **approved by the user on 24.11.2026** (after an independent review, verdict "approve with changes", all required changes applied). The backend skeleton (MKC-4) is the first application code; MKC-5 added the database layer; MKC-6 added secret hygiene and CI; MKC-7 added the frontend and the login check; MKC-8 adds containers.
- **Restart file:** `HANDOFF.md` (repo root) is the agents' running log and next steps, updated with every commit and important ticket change (decision 34). This status doc stays the overview of decisions and documents.
- **Board:** <https://github.com/users/qamran/projects/1> (public). Tickets MKC-1 to MKC-60 exist as issues #1 to #60 (issue number = key).
- **Done:** MKC-1 (ticket workflow and repo setup, PR #65), MKC-2 (code-only Turing mirror, README with links, PR #70), MKC-3 (agent instructions: assignment rule PR #67, HANDOFF.md PR #69, AGENTS.md + CLAUDE.md PR #72), MKC-4 (backend skeleton: uv project `backend/`, package `mkc`, FastAPI `/health` and `/api/version`, worker with clean SIGTERM shutdown, ruff and mypy strict, PR #75), MKC-5 (database layer: compose Postgres 17 + pgvector, SQLAlchemy 2, Alembic, `python -m mkc.db.check`, Supabase connection checked; PR #80), MKC-6 (secret hygiene, markdown lint, CI with required checks; PR #86), MKC-7 (frontend skeleton with Clerk; PR #91). Each after a review-agent PASS; both remotes at the latest merge commit.
- **MKC-5 details** (database layer, PR #80, plan `docs/superpowers/plans/241120262130-mkc-5-database-layer.md`):
  - `docker compose up db` (repo root): Postgres 17 with pgvector (`pgvector/pgvector:pg17`; Supabase hosts Postgres 17) on `127.0.0.1:5433`, dev-only credentials
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
  - `scripts/check_workflows.py` bans secrets and write permissions in every workflow. The deploy workflow (MKC-10) will need both, in the protected `production` environment; that ticket must narrow the rule to the deploy workflow on `main` and record it as a decision.
- **MKC-7 details** (frontend skeleton with Clerk, merged in PR #91; plan `docs/superpowers/plans/251120261119-mkc-7-frontend-skeleton.md`), sub-issues MKC-7.1 to MKC-7.4 (#87–#90):
  - Clerk development instance for every environment (decision 39, ADR 002); the user created it, with the `role` session-token claim, the admin (the user's Google account) and a test user
  - backend `mkc.api.auth`: `require_user`, `require_admin`, `GET /api/me`, `GET /api/admin/ping`; tokens checked with the public JWKS only (decision 40); `apiFetch` keeps every request on the `VITE_API_URL` origin (review fix); CORS allow-list for the local Vite dev server
  - `frontend/`: Vite, React, TypeScript, Tailwind, shadcn/ui, `@clerk/react`, `react-router`; `apiFetch`, `RequireAdmin`; vitest
  - CI: the frontend job runs lint, typecheck, test and build; the dependency scan adds `npm audit`
- **Current ticket:** MKC-8 (containers and local Compose, #8).
- **Next:** MKC-9 (Helm chart and kind smoke test).

## Key documents

| Document | Path |
|---|---|
| Design doc | `docs/superpowers/specs/241120261330-messkonzept-copilot-design.md` |
| Architecture Decision Record (ADR) 001: custom harness on LangChain plumbing | `docs/adr/241120261430-adr-001-harness.md` |
| ADR 002: Vercel frontend, k3s backend (+ worker, CD hardening) | `docs/adr/241120261430-adr-002-hosting.md` |
| ADR 003: Supabase instead of SQLite (+ restore drill) | `docs/adr/241120261430-adr-003-database.md` |
| ADR 004: narrow RAG corpus and decision layer with LLM fallback | `docs/adr/241120261441-adr-004-rag-and-decision-layer.md` |
| ADR 005: ticket workflow (GitHub Issues + public Projects board) | `docs/adr/241120261456-adr-005-ticket-workflow.md` |
| AGENTS.md (project rules for agents; CLAUDE.md imports it) | `AGENTS.md` |
| HANDOFF.md (agents' restart file) | `HANDOFF.md` |
| Ticket backlog (implementation plan, MKC-1 to MKC-60) | `docs/superpowers/plans/241120261500-ticket-backlog.md` |
| README (intro + links for both repos) | `README.md` |
| Official brief | `AE.CAP_afa.md` |

## Decisions so far (summary; the full log of 36 decisions is in design doc section 18)

- **Idea:** Messkonzept-Copilot. It extracts operator Messkonzept PDFs into structured, LBS-keyed records with human approval, and gives household site advice with citations.
- **Primary user:** MSB, VNB and energy-IT staff working across grid areas; installers are secondary; plus a public read-only demo.
- **Operators:** Stromnetz Berlin + SachsenNetze (both low voltage). §14a Modul 3 is out of scope.
- **Harness (ADR 001):**
  - custom loop and control; LangChain only for model and tool plumbing; no LangGraph
  - run-level operations are code, never model tools
  - checkpoints at turn boundaries
  - a single-replica worker with a Postgres lease
- **Core also includes (ADR 004):**
  - RAG over a narrow corpus: EnWG §14a, MsbG, BK6-22-300, BK8-22/010-A, operator texts
  - a decision layer (Jev via OpenRouter after a spike; LLM fallback by default)
- **Evaluation:**
  - E1–E8
  - independent gold: a different drafting model, blind subsets, a dev/test split
  - E4 with a no-fault arm and replayed fault runs
  - a CI eval gate
- **Stack:**
  - FastAPI + React (Vite, shadcn/ui), Clerk login
  - Supabase Postgres + Storage (ADR 003)
  - Langfuse tracing
  - providers: OpenRouter (default), Gemini, Anthropic, Meta Llama
- **DevOps (ADR 002):**
  - Docker, GitHub Actions (CI + eval gate + CD in a protected environment, SSH deploy), GHCR, Helm
  - kind in CI, k3s on Oracle Always Free, Vercel for the frontend
  - nightly backups to Oracle Object Storage plus one restore drill
- **Repos:** `origin` = <https://github.com/qamran/Messkonzept-Copilot> (personal, public, home); `turing` = the Turing submission mirror. `main` is pushed to both after every merge; both at the latest merge commit (named in HANDOFF.md). Turing's initial commit incl. their brief `AE.CAP_afa.md` was pushed to `origin` on 24.11.2026 with the user's OK.
- **Ticket workflow (ADR 005):** GitHub Issues + sub-issues on a public Projects board (`Backlog → Ready → In progress → Testing → Done`); `MKC-<n>` keys in titles, branches and commits; the Turing repo as a code-only mirror with no issues and no token, the README linking the board (ADR 005 option (c), decision 35); tickets, sub-issues and PRs assigned to `qamran` (decision 33); the development agent continues without asking and stops only for genuine decisions (decision 36); rules for both agents in `AGENTS.md`; one branch per ticket; the **development agent (Opus 5.5)** builds and moves tickets to Testing, the **review agent (Fable)** reviews, merges after green CI and closes; started in-session with "next ticket".
- **Not used:** hupe1980/mako, in any form.
- **Budgets:** LLM €20–30; user verification 10–12 h.
- **Feature list:** 82 features across Phases 0–8, plus a deferred list. **Phase 6 is the submittable release;** RAG and the decision layer follow in Phase 7.

## Open items

- [x] User approval of the design doc (24.11.2026)
- [x] Development plan written: ticket backlog MKC-1 to MKC-60, each with goal, scope, test and success criteria (24.11.2026)
- [x] User review of the ticket backlog (approved 24.11.2026)
- [x] Tickets created on the board (MKC-1, 24.11.2026)
- [ ] User setup tasks:
  - Supabase project (Postgres + private bucket)
  - Vercel account linked to the personal repo
  - provider API keys with spending caps
  - GitHub Secrets and the protected `production` environment
  - a domain with TLS (for the backend API; Clerk needs none, decision 39)
- [ ] Research: BDEW Codeliste der Lokationsbündelstrukturen (version, format, licence)
- [ ] Spike: the Jev call path via OpenRouter (start of Phase 7)

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
