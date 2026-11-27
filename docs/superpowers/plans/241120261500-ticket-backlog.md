# Messkonzept-Copilot: ticket backlog (implementation plan)

> **For agentic workers:**
>
> - The **development agent (Claude Opus 5.5)** pulls one ticket at a time from the public Projects board (ADR 005). It turns the ticket into issues and sub-issues with a detailed test-first plan (superpowers:writing-plans, saved as `docs/superpowers/plans/<ddMMyyyyHHmm>-mkc-<n>-<slug>.md`), and implements it with superpowers:test-driven-development.
> - The **review agent (Fable)** checks the PR against the ticket's **success criteria** before merging.
> - Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Messkonzept-Copilot as designed. It extracts grid operators' Messkonzept PDFs into approved, LBS-keyed records through a custom agent harness, and gives household site advice with citations. It is deployed with CI/CD and measured by evaluations E1–E8.

**Architecture:**

- **Backend:** FastAPI API + a single-replica harness worker (one image) on k3s, with state in Supabase Postgres/Storage.
- **Frontend:** React on Vercel.
- **Harness:** a code-driven durable queue with a model-driven tool loop per item, turn-level checkpoints, approvals, limits and traces.
- **LangChain** is used only for model and tool plumbing.

**Tech stack:**

- **Backend:** Python 3.12, uv, FastAPI, Pydantic v2, SQLAlchemy + Alembic, pdfplumber, PyMuPDF, LangChain chat models, langchain-typesafe, pytest
- **Frontend:** React + Vite + TypeScript + shadcn/ui, Clerk
- **Data:** Supabase (Postgres, pgvector, Storage)
- **Observability:** Langfuse
- **DevOps:** Docker, GitHub Actions, GHCR, Helm, kind, k3s (Oracle Always Free ARM), Vercel

**Spec:** `docs/superpowers/specs/241120261330-messkonzept-copilot-design.md` (approved 24.11.2026), with ADRs 001–005 in `docs/adr/`.

## Global Constraints

These apply to every ticket.

- **Commits:** atomic, under 200 lines where possible. Format: `MKC-<n>: <summary>` plus the trailer `Refs: qamran/Messkonzept-Copilot#<issue>`.
- **Branches:** one per ticket, `mkc-<n>-<slug>` from `main`. PRs only; no squash merges; no force-push to `main`.
- **Pushes:** after a merge, `main` is pushed to both `origin` (qamran/Messkonzept-Copilot) and `turing` (the Turing submission repo).
- **Tests first:** every code change starts with a failing test (TDD). CI must be green before merge.
- **Never committed:** operator PDFs, BDEW/edi@energy documents, real customer data, secrets. Tests use synthetic PDFs generated in the test, or live fetches marked `@pytest.mark.live`.
- **hupe1980/mako** is not used in any form (code, data model, ideas).
- **Models:** all calls go through `ModelClient` (or `DecisionClient`). OpenRouter is the default, with zero-data-retention routing. Gemini free tier only for public or synthetic input.
- **The model never gets side-effect tools.** Run-level operations (`fetch_document`, `segment_document`, `enqueue_approval`, `commit_record`) are harness code.
- **Docs stay current:** a ticket that changes a decision updates the design doc's decision log, the matching ADR (or a new one, file prefix `ddMMyyyyHHmm-`) and `docs/241120261430-project-status.md` in the same PR.
- **Budgets:** LLM €20–30 in total; the user's verification time 10–12 h in total. Every evaluation ticket records its spend in the status doc.
- **No Streamlit, no LangGraph** in the build (LangGraph only in optional MKC-55).

## Review Focus

Failure modes the spec implies that no feature list names explicitly. Each has a test in the ticket that owns it.

1. **The operator republishes the PDF at the same URL** (new edition, different hash). The run must record the new hash, never mix records from two editions, and flag the change. Test in **MKC-21**.
2. **Out-of-scope or unexpected advisor input** (English text, a balcony PV plug-in, a commercial site, an empty description). Expected: a clear "not covered, clarify with the operator", never a forced match. Test in **MKC-36**.
3. **The same draft approved twice** (two browser tabs, double click, a retry after a timeout). Expected: exactly one commit. Test in **MKC-30**.
4. **Supabase paused or unreachable** during a run. Expected: the worker backs off, the run shows `waiting_for_database`, no state is lost, and it resumes when the database is back. Test in **MKC-17**.
5. **The model asks for a tool that doesn't exist, or one from the run-level set, with plausible arguments.** Expected: a structured error to the model, counted in the trace, nothing executed. Test in **MKC-14**.

## Parallel lanes and waves

Added 27.11.2026 by MKC-168 (decision 61, plan `docs/superpowers/plans/271120261901-parallel-lanes.md`). Tickets run in parallel lanes; each lane owns its package. Inside a lane, tickets run in order. A ticket that can be built in a lane is built now, whatever its phase (the user's choice). The dependencies below still hold: a lane whose next ticket waits on another lane pauses.

| Lane | Tickets, in order | Owns (new code) | Waits on another lane |
|---|---|---|---|
| A. Extraction | MKC-21 → MKC-22 → MKC-23 → MKC-25 → MKC-26 → MKC-28 → MKC-29 → MKC-30 | `mkc/extraction/`, the item tools in `mkc/harness/registry.py`, `backend/data/operators.yaml`, the review queue and commit (MKC-29, MKC-30) | none |
| A2. SachsenNetze and gold | MKC-27 → MKC-24 | `mkc/extraction/sachsen*.py`, the gold tooling | MKC-27 on A (MKC-21); MKC-24 on A (MKC-23) |
| B. Advisor | MKC-36 → MKC-37 → MKC-38 | `mkc/advisor/`, advisor API routes, advisor UI pages | MKC-37 waits on A (MKC-30) |
| C. Decision layer | MKC-46 → MKC-47 → MKC-48 | `mkc/decision/` (`DecisionClient`) | MKC-47 waits on B (MKC-36) and A (MKC-26); MKC-48 on MKC-31 (eval runner, no lane yet) |
| D. RAG | MKC-49 → MKC-50 → MKC-51 | `mkc/rag/`, corpus loader, retriever | MKC-51 waits on B (MKC-38) |

**Wave 1 (from 27.11.2026):** MKC-21 (lane A), MKC-36 (lane B), MKC-46 (lane C), MKC-49 (lane D); MKC-46 and MKC-49 are Phase 7 tickets built early.

**Later waves:** MKC-27 (lane A2) joins once MKC-21 is merged. The waits above come from each ticket's "Depends on" line. Tickets outside these lanes (for example the evaluation tickets MKC-31 to MKC-35) get a lane from the coordinator when their dependencies are done; the coordinator never builds lane code itself.

## Ticket format

Every ticket, issue and sub-issue on the board uses this template (also as the GitHub issue template, created in MKC-1):

```text
Key:        MKC-<n>
Phase:      <0–8 | deferred>
Goal:       one sentence
Scope:      design-doc feature numbers and what is in / out
Depends on: MKC-<m>, ...
Interfaces: consumes / produces (exact names)
Test:       how it is proven (test names, commands, checks)
Success criteria (definition of done):
  - [ ] concrete, checkable result 1
  - [ ] concrete, checkable result 2
  - [ ] docs updated where a decision changed
  - [ ] CI green; review agent verdict "pass"
```

The criteria "CI green; review agent verdict pass" and "every commit references the issue" apply to every ticket and are not repeated below.

---

## Phase 0: Foundation and pipeline

### MKC-1: Ticket workflow and repo setup

- **Goal:** the public board, templates and branch rules exist, so all later work follows ADR 005.
- **Scope:** features 0 and 1, without the Turing mirror part (MKC-2). Repo description and topics for the showcase.
- **Depends on:** none. The user must first grant `gh auth refresh -s project`.
- **Test:**
  - a dummy issue created from the template appears on the board in `Backlog`
  - a direct push to `main` is rejected
  - a PR without passing checks cannot be merged
- **Success criteria:**
  - [ ] Public Projects board "Messkonzept-Copilot" linked to the repo, with a Status field `Backlog, Ready, In progress, Testing, Done`
  - [ ] Labels: `phase-0` … `phase-8`, `deferred`, `type:feature`, `type:infra`, `type:eval`, `type:docs`, `user-task`
  - [ ] Issue template with the ticket format above; PR template with key, `Closes #`, the success-criteria checklist and test evidence
  - [ ] Branch protection on `main`: PR required, the required checks set (placeholders until MKC-6), no force-push, no deletion
  - [ ] Repo description, topics and website field set
  - [ ] All tickets in this backlog created on the board, with keys `MKC-<n>` in their titles

### MKC-2: Turing repo as code-only mirror (no issue mirror)

*Changed 24.11.2026 by user decision: ADR 005 option (c) instead of an issue-mirror Action (decision 35).*

- **Goal:** the Turing submission repo carries the same code as the home repo, and reviewers find the tickets through links, without an issue mirror or token.
- **Scope:** feature 0 (mirror part). Out: issue-mirror Action, `TURING_ISSUES_TOKEN`.
- **Depends on:** MKC-1.
- **Interfaces:**
  - **Produces:** `README.md` (replaces the one-line Turing bot README; the full README follows in MKC-44), `scripts/check_readme.py`.
- **Test:** `scripts/check_readme.py` asserts README.md links to the board URL and the issues URL; after merge, both remotes show the same `main` commit.
- **Success criteria:**
  - [ ] ADR 005 updated: decision is option (c), code-only mirror; consequences without token
  - [ ] Design doc section 14 + decision 35; this entry updated; HANDOFF.md and status doc updated
  - [ ] README.md with intro + links to the board, the issue list, design doc, ADRs, HANDOFF.md
  - [ ] Check script for the README links, added test-first
  - [ ] After merge: `origin/main` == `turing/main`

### MKC-3: Agent instructions (AGENTS.md, CLAUDE.md)

- **Goal:** both agents get the project rules from the repo, not from memory.
- **Scope:** feature 2.
- **Depends on:** MKC-1.
- **Test:** markdown lint passes; a check script asserts that CLAUDE.md references AGENTS.md and that AGENTS.md contains the required sections.
- **Success criteria:**
  - [ ] AGENTS.md sections:
    - project purpose
    - roles (development agent Opus 5.5, review agent Fable)
    - the ticket flow
    - commit format and size rule
    - TDD
    - docs-current rule
    - data rules (no PDFs, no mako, synthetic data)
    - model rules (ModelClient only, zero-data retention)
    - safety rules (no side-effect tools for the model)
    - the review agent's checklist
  - [ ] CLAUDE.md is one line pointing to AGENTS.md
  - [ ] Review-agent checklist covers: success criteria met, tests prove them, global constraints, docs updated, no secrets

### MKC-4: Backend skeleton

- **Goal:** a typed FastAPI service with API and worker entrypoints that later tickets extend.
- **Scope:** feature 3.
- **Depends on:** MKC-3.
- **Interfaces:**
  - **Produces:** the package `mkc` (`backend/src/mkc/`), `mkc.api.app:create_app() -> FastAPI`, `mkc.worker.main:run() -> None`, and `mkc.config.Settings` (pydantic-settings, env-driven).
  - **Endpoints:** `GET /health -> {"status": "ok"}` and `GET /api/version -> {"version": str, "commit": str}`.
- **Test:** `tests/api/test_health.py::test_health_ok`, `test_version_reports_commit` (commit read from the `MKC_COMMIT` env, default `"dev"`).
- **Success criteria:**
  - [ ] `uv sync` and `uv run pytest` work from `backend/`
  - [ ] ruff and mypy (strict on `src/`) pass
  - [ ] Both endpoints tested; the worker entrypoint starts and exits cleanly on SIGTERM (test with a timeout)

### MKC-5: Database layer

- **Goal:** migrations and a session layer that work the same locally, in CI and on Supabase.
- **Scope:** feature 5 (connection to Supabase verified; tables are added by later tickets).
- **Depends on:** MKC-4.
- **Interfaces:**
  - **Produces:** `mkc.db.session.get_session()` (context manager), `mkc.db.base.Base`, an Alembic environment in `backend/migrations/`.
  - **Settings:** `DATABASE_URL`.
- **Test:**
  - `tests/db/test_migrations.py::test_upgrade_downgrade_roundtrip` against Docker Postgres (with pgvector image)
  - `test_session_rolls_back_on_error`
- **Success criteria:**
  - [ ] `docker compose up db` provides Postgres with pgvector for local work and tests
  - [ ] `alembic upgrade head` / `downgrade base` round-trip passes in CI
  - [ ] A one-off check against the Supabase project succeeds (documented in the status doc, no secret in the repo)

### MKC-6: Secret hygiene and CI pipeline

- **Goal:** every PR is linted, typed, tested and scanned, with no secrets reachable from fork PRs.
- **Scope:** features 6 and 7.
- **Depends on:** MKC-4, MKC-5.
- **Test:**
  - CI run on a PR is green
  - a test job runs gitleaks against a temporary file holding a fake key pattern and expects failure
  - the workflow files contain no `pull_request_target` (checked by a script)
- **Success criteria:**
  - [ ] `.pre-commit-config.yaml` with gitleaks, ruff and the end-of-file fixer; `.env.example` with every variable name and no values
  - [ ] `.gitignore` covers PDFs, caches, renders, `.env*` (except `.env.example`)
  - [ ] `ci.yml` jobs: backend (ruff, mypy, pytest with a Postgres service), frontend (lint, typecheck, test; activated in MKC-7), gitleaks, dependency scan
  - [ ] These jobs are set as required checks in branch protection

### MKC-7: Frontend skeleton with Clerk

- **Goal:** a React app with login and an admin role, deployable to Vercel previews.
- **Scope:** feature 4, including the check of Clerk against preview domains.
- **Depends on:** MKC-6.
- **Interfaces:**
  - **Produces:** `frontend/` (Vite + React + TS + shadcn/ui), `src/lib/api.ts` with `apiFetch(path, init)` attaching the Clerk token, and a `RequireAdmin` route guard.
  - **Env:** `VITE_API_URL`, `VITE_CLERK_PUBLISHABLE_KEY`.
- **Test:**
  - vitest: `RequireAdmin` redirects a signed-out user and blocks a non-admin
  - `apiFetch` sets the `Authorization` header
- **Success criteria:**
  - [ ] Signed-in admin, signed-in non-admin and signed-out states all work locally
  - [ ] The Clerk instance choice for previews (production vs development instance) is decided and recorded in ADR 002
  - [ ] Backend verifies Clerk JWTs: `mkc.api.auth.require_user` and `require_admin` dependencies, tested with signed test tokens

### MKC-8: Containers and local Compose

- **Goal:** one backend image (API + worker) running locally and built multi-arch in CI.
- **Scope:** feature 8.
- **Depends on:** MKC-4, MKC-7.
- **Test:**
  - CI builds `linux/amd64,linux/arm64` and pushes to GHCR on `main`
  - a Compose smoke test (`docker compose up` → `/health` 200, the worker container running)
- **Success criteria:**
  - [ ] `backend/Dockerfile`: multi-stage, non-root user, `MKC_COMMIT` build argument
  - [ ] `compose.yaml` services: db, api, worker, frontend
  - [ ] Image tagged with the commit SHA and `main` in GHCR

### MKC-9: Helm chart and kind smoke test

- **Goal:** a chart that deploys the API and worker, proven on a throwaway cluster in CI.
- **Scope:** feature 9.
- **Depends on:** MKC-8.
- **Test:** `helm lint`; CI job creates a kind cluster, installs the chart with test values, and checks `/health` and that the worker pod is ready.
- **Success criteria:**
  - [ ] `deploy/helm/mkc/` contains:
    - an API Deployment (replicas configurable) and a worker Deployment (replicas: 1)
    - a Service and an Ingress (TLS via cert-manager values)
    - Secrets from values
    - probes and resource limits
  - [ ] The worker has `terminationGracePeriodSeconds` long enough to finish a turn (value documented)
  - [ ] The kind job is a required check

### MKC-10: Continuous deployment (k3s + Vercel)

- **Goal:** a merge to `main` deploys the backend to k3s, then the frontend to Vercel, with smoke test and rollback.
- **Scope:** features 10 and 11.
- **Depends on:** MKC-9; user tasks: domain + TLS, VM deploy user with SSH key, GitHub `production` environment with secrets.
- **Test:**
  - after a merge, `GET https://<api-domain>/api/version` returns the merged commit
  - a forced failing smoke test triggers `helm rollback` (tested once and documented)
  - a preview deployment can sign in and call the API (CORS)
- **Success criteria:**
  - [ ] `cd.yml` runs only on push to `main`, inside the protected `production` environment
  - [ ] Deploy over SSH to a restricted user; the k3s API is not exposed (verified from outside)
  - [ ] The backend deploys first, then Vercel production; the frontend shows a warning on an API version mismatch (vitest)
  - [ ] CORS allow-list: the production domain + the Vercel preview pattern (tested)
  - [ ] Runbook section "deploy and rollback" written

### MKC-11: Backups and restore drill

- **Goal:** nightly database backups off-site, and one proven restore.
- **Scope:** feature 12.
- **Depends on:** MKC-10; user task: an Oracle Object Storage bucket and credentials.
- **Test:**
  - CronJob triggered manually → a dump object appears in the bucket
  - restore drill into a throwaway Postgres → row counts match
- **Success criteria:**
  - [ ] Helm CronJob: `pg_dump | gzip` → Oracle Object Storage, with 14-day retention (lifecycle rule)
  - [ ] Failed backup visible in logs; a status endpoint `GET /api/admin/backup-status` is used by the Runs page later
  - [ ] Runbook "restore drill" with the steps, timing and row counts from the actual drill

### MKC-12: Codeliste research and LBS reference data

- **Goal:** know the current BDEW Codeliste version and terms, and load the LBS codes as cited facts.
- **Scope:** feature 13.
- **Depends on:** MKC-5.
- **Interfaces:**
  - **Produces:** the table `lbs_structure(code, bezeichnung, objects jsonb, source, version)`, the loader `mkc.reference.lbs.load_lbs(path) -> list[LbsStructure]`, and the data file `backend/data/lbs_structures.yaml`.
- **Test:**
  - `test_lbs_codes_are_13_digits_with_valid_check_digit`
  - `test_loader_rejects_duplicate_codes`
  - `test_every_code_in_berlin_table_exists` (Berlin's codes listed as facts in the test)
- **Success criteria:**
  - [ ] Research note `docs/<ddMMyyyyHHmm>-codeliste-research.md`: version, source URL, format, licence terms, and what may be committed
  - [ ] The YAML holds only codes, Bezeichnung and object composition with a citation, never the BDEW document
  - [ ] The check-digit algorithm is documented and tested (if the Codeliste defines one; otherwise a format check only, noted)

---

## Phase 1: Harness core

### MKC-13: Provider layer (ModelClient)

- **Goal:** one interface for all model calls across four providers, with cost, traces and record/replay.
- **Scope:** feature 14.
- **Depends on:** MKC-4.
- **Interfaces:**
  - **Produces:** `mkc.models.client.ModelClient`:
    - `chat(role: Role, messages) -> ModelReply`
    - `chat_with_tools(role, messages, tools: list[ToolSpec]) -> ModelReply`
    - `vision(role, messages, images) -> ModelReply`
  - `Role` = `Literal["extract_vision", "facts", "explain", "judge", "gold_draft"]`.
  - `ModelReply` fields: `text`, `tool_calls: list[ToolCall]`, `usage: Usage(input_tokens, output_tokens, cost_eur)`, `model_id`, `latency_ms`.
  - Modes: `live | record | replay` (env `MKC_MODEL_MODE`); replay store keyed by `sha256(role, model_id, messages, tools)`.
- **Test:**
  - unit tests with a fake LangChain chat model:
    - cost computed from a price table
    - replay returns the recorded reply
    - replay miss raises `ReplayMiss`
    - zero-data-retention routing parameters present for OpenRouter
  - `@pytest.mark.live` contract tests per provider (tool call + structured output round-trip)
- **Success criteria:**
  - [ ] Role → provider/model mapping in config, not code
  - [ ] LangChain packages pinned; agent APIs (`create_agent`) not imported anywhere (a grep test enforces it)
  - [ ] Live contract tests pass for OpenRouter, Gemini, Anthropic and the Meta API (run once, result noted in the status doc; Meta API replaces the closed Meta Llama API, decision 52)

### MKC-14: Tool registry and per-context allow-lists

- **Goal:** the model can only call allow-listed tools with validated arguments; everything else becomes a structured error.
- **Scope:** feature 15.
- **Depends on:** MKC-13.
- **Interfaces:**
  - **Produces:** `mkc.harness.tools.Tool(name, args_model: type[BaseModel], fn, side_effect: bool, deterministic: bool)` and `ToolRegistry.for_context(ctx: Literal["item", "run"]) -> list[Tool]`.
  - `ToolRegistry.execute(call: ToolCall, ctx) -> ToolResult` where `ToolResult(ok: bool, data | error: ToolError(code, message))`.
- **Test:**
  - `test_unknown_tool_returns_structured_error`
  - `test_run_level_tool_requested_in_item_context_is_refused_and_not_executed` (Review Focus 5)
  - `test_invalid_args_return_validation_error`
  - `test_item_context_exposes_no_side_effect_tools`
- **Success criteria:**
  - [ ] The item context exposes exactly the six tools from design section 8.1 (asserted by test)
  - [ ] Refusals are counted in the trace (assert via the trace interface from MKC-19, or a stub until then)

### MKC-15: Item loop, work queue and states

- **Goal:** code runs the queue; inside each item the model drives tools until a draft is saved or limits are hit.
- **Scope:** features 16 and 17; states from design section 8.2.
- **Depends on:** MKC-14, MKC-5.
- **Interfaces:**
  - **Produces:** tables `run`, `item`, `turn`.
  - `mkc.harness.loop.run_item(item_id) -> ItemOutcome`.
  - `mkc.harness.queue.next_item(run_id) -> Item | None`.
  - State enums `RunState`, `ItemState` exactly as in design 8.2.
- **Test:**
  - with a scripted fake model: `test_item_reaches_draft_saved`
  - `test_run_moves_to_awaiting_approval_when_items_done_and_drafts_pending`
  - `test_invalid_state_transition_raises`
- **Success criteria:**
  - [ ] All state transitions in a single transition function, tested against the design table
  - [ ] Extraction never blocks on approvals (test: the queue continues while drafts are pending)

### MKC-16: Turn checkpoints, resume, tool cache, idempotency

- **Goal:** an interrupted run resumes at its last complete turn without repeating completed work or side effects.
- **Scope:** features 18 and 19; design 8.3.
- **Depends on:** MKC-15.
- **Interfaces:**
  - **Produces:** `mkc.harness.checkpoint.save_turn(...)` and `load_resume_context(item_id) -> ResumeContext`.
  - Tool cache keyed by `(tool, sha256(args), document_hash)`; idempotency keys on `save_draft` and `commit_record`.
  - **As built (decision 56):** `save_turn(session, turn, *, blobs, inline_max_bytes)`, `load_resume_context(session, item_id, *, blobs)`; the cache key adds the code version (`ToolCache(sessions, code_version)`); `record_key(env)` is the key for both writes.
- **Test:**
  - `test_crash_after_turn_k_resumes_at_k_plus_1`
  - `test_inflight_turn_is_discarded`
  - `test_deterministic_tool_hits_cache_on_resume`
  - `test_save_draft_twice_creates_one_draft`
  - `test_checkpoint_never_splits_tool_call_and_result`
- **Success criteria:**
  - [ ] Each turn is saved in one transaction; large outputs stored as Storage references
  - [ ] The resume context is the item task + compact summary + last turn's results (asserted on the message list)

### MKC-17: Run executor (worker with lease)

- **Goal:** exactly one worker processes a run, survives restarts and deploys, and waits out database outages.
- **Scope:** feature 20; design 8.4.
- **Depends on:** MKC-16.
- **Interfaces:**
  - **Produces:** `mkc.worker.executor.claim_run() -> Run | None` (`FOR UPDATE SKIP LOCKED`, lease + heartbeat) and `graceful_shutdown()`.
  - New `RunState` value `waiting_for_database`.
- **Test:**
  - `test_two_workers_only_one_claims`
  - `test_expired_lease_is_reclaimed`
  - `test_sigterm_finishes_turn_then_releases_lease`
  - `test_database_unavailable_sets_waiting_and_resumes` (Review Focus 4: drop the DB connection in the test, then restore)
- **Success criteria:**
  - [ ] Lease and heartbeat timings in config, documented in the runbook
  - [ ] No state lost in any of the four tests (asserted on turn counts)
- **Note (decision 56):** the worker calls `process_run` with `code_version=Settings.commit`, `inline_max_bytes=Settings.turn_inline_max_bytes` and `default_registry(sessions=...)`. Until then the tool cache, the inline limit setting and the real `save_draft` are off in production. A database error inside `save_draft` is caught by the registry and reaches the model as `tool_failed`; decide whether it should propagate like other database errors.
- **As built (decision 57):** `claim_run` lives in `mkc.worker.lease` (re-exported by `mkc.worker.executor`) and takes `(session, *, owner, lease_seconds)`; `graceful_shutdown` is a method of `Executor`. The worker wires `process_run` as the note above says. A `save_draft` database error stays `tool_failed`: in an outage the turn's own commit fails too, so that turn is never stored and is asked again after the outage.

### MKC-18: Limits and retries

- **Goal:** runs stop cleanly at step, time, cost and retry limits; transient errors are retried sensibly.
- **Scope:** features 21 and 22.
- **Depends on:** MKC-15.
- **Interfaces:**
  - **Produces:** `mkc.harness.limits.Limits(max_steps_item, max_steps_run, max_wall_s, max_cost_eur, max_retries_tool)` and the `StopReason` enum.
- **Test:**
  - one test per limit asserting its own `StopReason`
  - `test_429_backs_off_exponentially` (fake clock)
  - `test_malformed_output_gets_one_reprompt_then_item_fails`
- **Success criteria:**
  - [ ] Every stop shows its reason in the run record and the trace
  - [ ] Default limits set in config and justified in the plan for MKC-15/18
- **Note (MKC-16 pre-PR review):** `process_run` resumes a `running` item before queued ones, with no attempt cap. An item that crashes on every restart blocks its run and pays a model call each time (a crashed call writes no turn row, so the step cap doesn't stop it). Add a resume-attempt counter on `item` and fail the item with its own reason after N attempts.
- **Note (MKC-17, decision 57):** setup errors (`ModelConfigError`, `ReplayMiss`) make the executor release the lease and pause for `MKC_WORKER_DB_BACKOFF_MAX_SECONDS`, then claim the run again; turn them into a run stop with its own `StopReason`. A wall-clock deadline per turn (MKC-13 finding 3: the provider timeout is per phase) belongs to the run limits; without it a turn longer than the 300 s grace period is killed on deploy and resumed like a crash.

- **As built (decision 58):** `Limits` has more fields than the five named here (`max_retries_model`, `max_reprompts`, `max_resumes_item`, `backoff_base_s`, `backoff_max_s`, `turn_timeout_s`); `run_item`/`process_run` take `limits`, `tracers` (`StopEvent` hooks) and `sleep` instead of `max_steps`. Setup errors and exhausted retries stop the run; the item in flight keeps its place. The resume note above is built as `item.attempts_without_progress`. For MKC-19: send `StopEvent`s to Langfuse and `run_log`; a failed model call's cost is recorded nowhere (`CallTrace.usage` is None and no turn is written); decide whether the tracer should estimate it.

### MKC-19: Tracing (Langfuse + run log)

- **Goal:** every model call and tool call is inspectable, with tokens, cost, latency and errors.
- **Scope:** feature 23.
- **Depends on:** MKC-13, MKC-15.
- **Interfaces:**
  - **Produces:** `mkc.observability.trace.Tracer`, with `span_model(...)` and `span_tool(...)`, writing to Langfuse and to the `run_log` table.
- **Test:**
  - with a fake Langfuse client: spans have the required fields
  - run-log rows match the span counts
  - tracing failure never fails the run (`test_langfuse_down_run_continues`)
- **Success criteria:**
  - [ ] Trace IDs link a run to its Langfuse trace (stored on `run`)
  - [ ] One real run visible in Langfuse (screenshot or link in the status doc)
- **As built (decision 59):** besides `span_model` and `span_tool`, `Tracer` has `span_stop` (`StopEvent`), `outage`, `start_run` (sets `run.trace_id`) and `flush`; Langfuse sits behind a `Sink` (`LangfuseSink`). `ModelClient` methods take a keyword `scope=` (`TraceScope`), `ToolEnv` gained `step` and `ToolTrace` the ids. `mkc.worker.main.build_executor` wires one tracer; `python -m mkc.observability.demo` makes the real run. Finding 18#1 (a run settling on its last limit turn) fixed here.

### MKC-20: Baseline mode, failure injection and CLI

- **Goal:** the same harness can run as the simple loop, faults can be injected on purpose, and runs are controllable from a CLI.
- **Scope:** features 24, 25 and 26.
- **Depends on:** MKC-16, MKC-17, MKC-18.
- **Interfaces:**
  - **Produces:** the setting `MKC_HARNESS_MODE=full|baseline`.
  - `mkc.harness.faults.FaultPlan(timeout_at, rate_limit_at, malformed_at, kill_at_turn, kill_during_approval)`.
  - CLI `mkc run start|resume|status|inspect`.
- **Test:**
  - `test_baseline_crash_restarts_from_zero`
  - `test_baseline_holds_approvals_in_memory_only`
  - one test per fault type
  - CLI tests with Typer's runner
- **Success criteria:**
  - [ ] Baseline differs from full **only** by the documented switches (asserted by a config test)
  - [ ] Fault plans can be loaded from YAML for E4
- **As built (decision 60):** baseline is not a second loop: `run_item`/`process_run` take `switches` and a `RunMemory`, and `mkc.harness.runner.execute_run` picks them from `run.mode` (migration 0011). `FaultPlan` fields are 1-based counts; `timeout_at` is a tool timeout (the E4 row); `kill_during_approval` fires after the n-th item ends `draft_saved` until MKC-23 brings approvals. The CLI takes a synthetic items file until MKC-21 and adds `resume` for `stopped` runs (MKC-18 finding 2). PR #161 findings 1 to 3 are fixed here.

---

## Phase 2: Extraction, Berlin, code path

### MKC-21: Fetch and segment (Berlin)

- **Goal:** the run fetches an allow-listed catalogue, hashes and caches it, and splits Berlin into one item per concept.
- **Scope:** features 27 and 28.
- **Depends on:** MKC-15; the Storage bucket (user task).
- **Interfaces:**
  - **Produces:** `operator` and `source_document` tables, `backend/data/operators.yaml` (Berlin, SachsenNetze URLs), `fetch_document(operator_id) -> SourceDocument`, `segment_document(doc) -> list[ConceptRegion(page, bbox, number_hint)]`.
- **Test:**
  - `test_disallowed_url_refused`
  - `test_new_hash_at_same_url_creates_new_edition_and_flags_it` (Review Focus 1)
  - `test_berlin_segmentation_one_region_per_concept_page` (synthetic PDF)
  - live: Berlin yields the expected concept count (the number is fixed in the test after the first verified run)
- **Success criteria:**
  - [ ] PDFs cached only in Storage and gitignored locally
  - [ ] Records from two editions never mixed (test)
- **Note (decision 56):** add a Supabase Storage `BlobStore` and make it the default for turn results; `blob:sha256:` refs written to the `blob` table must stay readable.
- **As built (decisions 62 to 64):** `fetch_document(operator_id, *, sessions, store, get, operators)` and `segment_document(doc, *, store)` as pinned by the test agent; `ConceptRegion.bbox` is `(x0, top, x1, bottom)`, origin top left. The Berlin heading is `<n> <title>`, not `Messkonzept <n>`; the live count is 26. Run-level operations through `default_registry(documents=DocumentOps(...))`; `mkc run start --operator` replaces the synthetic items file for real runs. Storage is the default for large turn results when its five settings are set (`blob` table as fallback). Production needs the `MKC_STORAGE_*` values in `mkc-secrets`.

### MKC-22: Text and table extraction

- **Goal:** text fields and table rows come out correctly by code, including the case where naive text extraction fails.
- **Scope:** features 29 and 30.
- **Depends on:** MKC-21.
- **Interfaces:**
  - **Produces:** item tools `extract_text(region) -> TextFields(title, applications, footnotes, stated_lbs)` and `extract_tables(doc, kind: Literal["meter_tech", "lbs"]) -> list[Row]`.
- **Test:**
  - synthetic PDF with a ruled table whose rows shift under pdftotext: `test_pdfplumber_rows_correct`
  - `test_stated_lbs_parsed`
  - live: the Berlin LBS table matches the codes on concept pages 3, 4.4 and 11.1 (spike facts)
- **Success criteria:**
  - [ ] A naive pdftotext baseline function is kept for the E1 comparison
  - [ ] Both tools are deterministic and cached
- **Note (MKC-16 pre-PR review):** Postgres JSONB rejects `\u0000`, and PDF text can hold NUL characters. Strip them from tool output before it reaches `turn`, `tool_cache` or `blob` JSON, or the item stays `running` and crashes on every resume.

### MKC-23: Render, draft assembly, save_draft

- **Goal:** diagram regions are rendered and cached, and drafts are assembled, saved and queued for approval exactly once.
- **Scope:** features 31 and 32.
- **Depends on:** MKC-22, MKC-16.
- **Interfaces:**
  - **Produces:** `render_region(page, bbox, dpi) -> ImageRef` (cache key: doc hash, page, bbox, dpi; DPI cap in config).
  - `save_draft(draft: MesskonzeptDraft) -> DraftId` (writes only this item's draft; the harness then runs `enqueue_approval` on the result, decision 53).
  - Pydantic `MesskonzeptDraft`, exactly the fields of design section 7.
- **Test:**
  - `test_bbox_outside_page_rejected`
  - `test_dpi_above_cap_rejected`
  - `test_render_cache_hit`
  - `test_saved_draft_is_enqueued_for_approval_once` (by the harness, not by `save_draft`)
- **Success criteria:**
  - [ ] `MesskonzeptDraft` JSON schema exported for the vision prompt (MKC-26)
- **Note (decision 56):** the draft key (document hash, concept key) spans runs, so a new run of the same document overwrites a draft that may still await approval. Decide here what a save does once the draft is enqueued or approved.
- **Note (PR #167 finding 7, decision 60):** a baseline item can be `draft_saved` with no `draft` row (its draft was in memory); approvals must not assume a row.

### MKC-24: Gold tooling

- **Goal:** gold data is independent: a fixed split, drafted by a different model, with blind labelling and import/export.
- **Scope:** feature 33; design 11.1.
- **Depends on:** MKC-23, MKC-13.
- **Interfaces:**
  - **Produces:** `gold_item(kind, key, split, payload, drafted_by, verified_by, blind)`, CLI `mkc gold split|draft|export|import`, and a blind-labelling mode in the review UI (wired up in MKC-29).
- **Test:**
  - `test_split_is_deterministic_and_balanced_per_operator`
  - `test_gold_draft_uses_gold_draft_role_model_not_extraction_model`
  - `test_blind_mode_hides_draft_payload`
- **Success criteria:**
  - [ ] Split file committed (keys only, no PDF content)
  - [ ] **User task:** the first Berlin gold batch verified; hours logged in the status doc

### MKC-25: Go/no-go vision check

- **Goal:** decide on evidence whether vision reads Berlin diagrams well enough to continue with both operators.
- **Scope:** feature 34.
- **Depends on:** MKC-23 (uses a throwaway vision call through ModelClient).
- **Test:** 5 Berlin concepts read by vision, compared against user-verified topology.
- **Success criteria:**
  - [ ] Result table (concept, meters correct, upstream correct, components correct) in the status doc
  - [ ] Decision recorded: **go**, or **Berlin only**; the design doc and status doc updated if Berlin only

---

## Phase 3: Vision, SachsenNetze, validation and approvals

### MKC-26: Diagram reading with agentic re-render

- **Goal:** the vision model turns a rendered diagram into the topology schema, re-rendering at a higher DPI when validation fails.
- **Scope:** features 35 and 36.
- **Depends on:** MKC-23, MKC-25 (go).
- **Interfaces:**
  - **Produces:** item tool `read_diagram(image: ImageRef) -> Topology(meters, components)`, and a versioned prompt in `backend/prompts/read_diagram.v1.md`.
- **Test:**
  - fake model: `test_schema_violation_triggers_one_corrective_reprompt`
  - `test_validation_failure_leads_model_to_rerender_higher_dpi` (scripted tool sequence)
- **Success criteria:**
  - [ ] PDF content wrapped as untrusted data in the prompt (asserted on the message)
  - [ ] Few-shot examples come only from approved records of the *other* operator

### MKC-27: SachsenNetze segmentation

- **Goal:** two concepts per landscape page become two items.
- **Scope:** feature 37.
- **Depends on:** MKC-21.
- **Test:**
  - synthetic two-up landscape page → two regions
  - live: SachsenNetze yields 11 items
- **Success criteria:**
  - [ ] The split method chosen (detected layout vs half page) is documented in the ticket plan, with the reason

### MKC-28: Validation and LBS inference

- **Goal:** drafts are cross-checked, and operators without codes get inferred LBS candidates with a rationale.
- **Scope:** features 38 and 39.
- **Depends on:** MKC-26, MKC-12.
- **Interfaces:**
  - **Produces:** item tool `validate_draft(draft) -> ValidationReport(errors, warnings)` and `infer_lbs(draft) -> list[LbsCandidate(code, condition, rationale)]` (provenance `inferred`).
- **Test:**
  - `test_diagram_label_missing_from_text_is_error`
  - `test_stated_lbs_not_in_table_is_error`
  - `test_topology_incompatible_with_lbs_is_warning`
  - `test_inferred_lbs_never_marked_stated`
- **Success criteria:**
  - [ ] Every rule in design 8 step 4 implemented and tested
  - [ ] The inference prompt is versioned; the rationale is stored per candidate

### MKC-29: Review queue (API + UI)

- **Goal:** the user approves, edits or rejects drafts next to the source region; blind labelling uses the same screen.
- **Scope:** feature 40, plus the blind mode from MKC-24.
- **Depends on:** MKC-28, MKC-7.
- **Interfaces:**
  - **Produces:** `GET /api/review/queue`, `POST /api/review/{draft_id}/decision {action: approve|edit|reject, reason?, edited?}` (admin only, idempotency key required).
  - React route `/review`.
- **Test:**
  - API: `test_non_admin_forbidden`
  - `test_edit_validates_against_schema`
  - vitest: inferred LBS highlighted; reject requires a reason
- **Success criteria:**
  - [ ] The rendered source region is shown beside each draft
  - [ ] Blind mode hides the draft and saves the user's labels as gold

### MKC-30: Commit on approval, run report, export/import

- **Goal:** approvals become catalogue records exactly once, and every run produces a report.
- **Scope:** features 41, 42 and 43.
- **Depends on:** MKC-29, MKC-17.
- **Interfaces:**
  - **Produces:** `messkonzept` (approved catalogue) table; worker handler `commit_record(decision_id)` (idempotent on `(document_hash, concept_number)`); `GET /api/runs/{id}/report`; CLI `mkc catalogue export|import`.
- **Test:**
  - `test_double_approval_commits_once` (two concurrent decisions; Review Focus 3)
  - `test_commit_after_crash_resumes_from_stored_decision`
  - `test_report_counts_match_items`
  - export → import round-trip
- **Success criteria:**
  - [ ] The run reaches `done` only when every item is committed, rejected or failed
  - [ ] Berlin fully extracted and approved once, end to end (counts in the status doc)
- **Note (decision 56):** the commit key is `mkc.harness.drafts.record_key` (document hash, concept key). `messkonzept` must have a unique constraint on it, and a test must show that a double commit leaves one record.

---

## Phase 4: Evaluation

### MKC-31: Eval runner, E1 and E2

- **Goal:** one command produces versioned E1/E2 reports on the test split.
- **Scope:** features 44, 45 and 46.
- **Depends on:** MKC-30, MKC-24.
- **Interfaces:**
  - **Produces:** CLI `mkc eval run --suite e1|e2|... --split test`; reports written to `eval/reports/<ddMMyyyyHHmm>-<suite>.json` and `.md`.
- **Test:**
  - metric unit tests (field precision/recall, exact match, top-k) with hand-made fixtures
  - `test_e2_masks_berlin_printed_codes`
- **Success criteria:**
  - [ ] E1 also reports the naive pdftotext baseline from MKC-22
  - [ ] E9 (agent trajectory, decision 55): task completion, tool-choice accuracy, valid-argument rate, refusals, steps and cost per item, read from the `turn` rows
  - [ ] Reports store pass/fail per case; `mkc eval diff` lists the cases that passed in the previous report and fail now (decision 55)
  - [ ] `eval/iterations.md` started: each change made because of an eval result, with metrics before and after and the cases that changed (decision 55)
  - [ ] Reports include model ids, prompt versions, spend in EUR and set sizes
  - [ ] Results summarised in the status doc
- **Note (decision 56):** run the items with `code_version` = the git `HEAD` commit, never `dev`, so the tool cache never serves a result from before a fix. With uncommitted changes the cache must be off (`code_version=None`): `HEAD` does not name them.

### MKC-32: E4, harness vs baseline

- **Goal:** measure what checkpoints cost and what they save.
- **Scope:** feature 47.
- **Depends on:** MKC-20, MKC-31.
- **Test:**
  - suite runs on **replay** for fault mechanics
  - one live no-fault and one live fault run
- **Success criteria:**
  - [ ] No-fault arm: overhead in time, cost and steps, reported for full vs baseline
  - [ ] Fault arm: completion rate, cost, repeated side effects (= 0 for full), recovery time, for each fault type
  - [ ] Report + README-ready chart data committed
- **Note (decision 60):** a re-prompt, a faulted tool result or a resume context changes the next request, so its replay key differs from a no-fault recording. Record each fault arm once (`MKC_MODEL_MODE=record`) before replaying it; a `ReplayMiss` stops the run with `setup_error`. Fault plans: `backend/data/e4_faults.yaml`; run them with `mkc run start --inline --mode full|baseline --faults ... --plan ...`. An injected tool timeout, 429 or malformed reply has no `run_log` row (it never reaches the registry or the provider); count it from the fault plan and the turn rows. Run baseline arms with `--inline`: a baseline crash loop in the worker has no cap across attempts. Repeated side effects in baseline are the extra entries in `RunMemory.approvals` and the extra `save_draft` rows in `run_log`. Open points from the PR #167 review (findings 3 to 6): fence before a baseline stop writes its report; CLI exit code 0 also for a run that ended `stopped`; `start --inline` creates and claims the run in two transactions, `--faults` without `--inline` is ignored, Ctrl-C leaves the lease to expire; baseline limits restart per attempt.

### MKC-33: E5, safeguard suite

- **Goal:** prove the safeguards hold against crafted attacks and misuse.
- **Scope:** feature 48.
- **Depends on:** MKC-30.
- **Test:** pass/fail cases:
  - synthetic injection PDFs (text and image)
  - a disallowed URL
  - invalid arguments
  - a non-allow-listed tool
  - an over-limit run
- **Success criteria:**
  - [ ] Every case passes or is documented as a known limitation with a follow-up ticket
  - [ ] Injection PDFs generated in tests, never committed as real documents

### MKC-34: E6, model comparison

- **Goal:** choose a model per role by accuracy, cost and latency, within budget.
- **Scope:** feature 49.
- **Depends on:** MKC-31.
- **Test:** an E1/E2 subset (about 5 concepts per model) across OpenRouter models (incl. open-weight Llama 4), Gemini, Anthropic, the Meta API and Jev Router.
- **Success criteria:**
  - [ ] Chosen model per role written to config and justified in the design doc's decision log
  - [ ] Spend within the E6 budget line (€3–4)

### MKC-35: CI eval gate

- **Goal:** PRs that touch prompts, models, extraction, rules or retrieval cannot lower quality unnoticed.
- **Scope:** feature 50.
- **Depends on:** MKC-31, MKC-13 (replay).
- **Test:**
  - a PR with a deliberately degraded prompt fails the gate
  - an unrelated PR runs on replay at €0
- **Success criteria:**
  - [ ] The gate runs on a path filter; uses replay unless prompts or models changed; has a cost cap
  - [ ] Baseline and tolerance stored in the repo; the gate is a required check
  - [ ] The gate also fails on any case of its subset that passed in the baseline and fails now, unless the PR names it as an accepted change (decision 55)

---

## Phase 5: Site advisor

### MKC-36: Site facts and follow-up questions

- **Goal:** free text becomes confirmed SiteFacts; only result-changing gaps are asked about.
- **Scope:** features 51 and 52.
- **Depends on:** MKC-13, MKC-7.
- **Interfaces:**
  - **Produces:** `POST /api/advisor/facts {text, operator_id} -> SiteFacts`, the `SiteFacts` model (design 7, `modul14a ∈ {1, 2}`), and `required_questions(facts) -> list[Question]`.
  - **Built (decisions 65 and 66):** also `POST /api/advisor/questions SiteFacts -> list[Question]` for the UI; out of scope is a 200 `SiteFacts` with `out_of_scope` notes and no facts.
- **Test:**
  - `test_extracts_pv_battery_heatpump_modul2`
  - `test_only_result_changing_unknowns_are_asked`
  - Review Focus 2: `test_english_input_handled`, `test_plugin_pv_out_of_scope`, `test_commercial_site_out_of_scope`, `test_empty_input_rejected`
- **Success criteria:**
  - [ ] Facts card with confirm/edit in the UI (vitest)
  - [ ] Modul 3 is answered as out of scope (test)

### MKC-37: Rule table and deterministic matching

- **Goal:** confirmed facts map to LBS and to the operator's approved concepts, reproducibly.
- **Scope:** features 53 and 54.
- **Depends on:** MKC-30, MKC-12, MKC-36.
- **Interfaces:**
  - **Produces:** `backend/data/rules.yaml` (AI-drafted, user-verified; provenance per row) and `match(facts, operator_id) -> MatchResult(candidates: list[RankedConcept], status: match|ambiguous|none)`.
- **Test:**
  - table-driven tests over the dev scenarios
  - `test_no_match_returns_none_status`
  - `test_two_equal_candidates_returns_ambiguous`
  - `test_same_input_same_output`
- **Success criteria:**
  - [ ] **User task:** rule table verified; hours logged
  - [ ] The matcher calls no LLM (asserted)

### MKC-38: Explainer with checked citations

- **Goal:** recommendations explain themselves and cite only approved records and pages.
- **Scope:** feature 55.
- **Depends on:** MKC-37.
- **Interfaces:**
  - **Produces:** `POST /api/advisor/recommend {facts} -> Recommendation` (design 7) and `check_citations(rec) -> None | CitationError`.
- **Test:**
  - `test_citation_to_unapproved_record_rejected`
  - `test_ambiguous_result_lists_questions_for_operator`
  - `test_explanation_mentions_inferred_lbs_as_inferred`
- **Success criteria:**
  - [ ] The recommendation card in the UI shows concept, LBS (stated/inferred), explanation, citations and open questions

### MKC-39: E3, advisor evaluation

- **Goal:** measure the advisor on the test scenarios for both operators.
- **Scope:** feature 56.
- **Depends on:** MKC-38, MKC-31.
- **Test:** 25 scenarios × 2 operators (test split reported); an LLM judge with a rubric for explanation quality, spot-checked by the user.
- **Success criteria:**
  - [ ] **User task:** E3 expected answers + blind subset verified; hours logged
  - [ ] Report with top-1 concept, LBS accuracy, citation validity, question precision and judge scores

---

## Phase 6: Submittable release

### MKC-40: Runs page and trace view

- **Goal:** operators can start, resume and inspect runs in the UI.
- **Scope:** features 57 and 58.
- **Depends on:** MKC-30, MKC-19, MKC-11.
- **Test:** vitest for list, status badges, the resume button, the trace timeline; API tests for `GET /api/runs` and `POST /api/runs/{id}/resume`.
- **Success criteria:**
  - [ ] Shows state, stop reason, cost, steps, the backup status, and database and storage usage
  - [ ] Each trace links to Langfuse

### MKC-41: Catalogue and comparison view

- **Goal:** approved concepts per operator, side by side by LBS.
- **Scope:** feature 59.
- **Depends on:** MKC-30.
- **Test:** `test_comparison_groups_by_lbs`; vitest for the stated/inferred markers.
- **Success criteria:**
  - [ ] "Berlin 4.4 ≈ SachsenNetze 3-5"-style rows rendered from data, never hard-coded

### MKC-42: Eval report page

- **Goal:** the latest evaluation results are visible in the app.
- **Scope:** feature 60.
- **Depends on:** MKC-31 to MKC-35, MKC-39.
- **Test:** vitest renders a report fixture.
- **Success criteria:**
  - [ ] Shows E1–E6 and E9 with set sizes, split, model ids, spend and date
  - [ ] Shows the regressions against the previous run and links the improvement log (decision 55)

### MKC-43: Public read-only demo

- **Goal:** visitors try the product without logging in, at zero LLM cost.
- **Scope:** feature 61.
- **Depends on:** MKC-41, MKC-38.
- **Test:**
  - `test_public_routes_make_no_model_calls` (ModelClient spy)
  - `test_public_routes_rate_limited`
  - `test_public_routes_are_read_only`
- **Success criteria:**
  - [ ] Catalogue, comparison and precomputed advisor examples, plus a "how it works" panel
  - [ ] Linked from the README

### MKC-44: README, security notes, runbook, demo script, presentation

- **Goal:** the repo explains itself for reviewers and employers.
- **Scope:** features 62 and 63.
- **Depends on:** MKC-40 to MKC-43.
- **Test:** markdown lint and a link check in CI; README purpose paragraph reviewed against the brief's criterion.
- **Success criteria:**
  - [ ] README: purpose paragraph (goal, problem, how it works), architecture diagram, how to run, results, limitations, prior-art line, data and privacy notes, the showcase link near the top
  - [ ] Security and privacy notes covering the six review topics
  - [ ] Runbook complete (deploy, rollback, restore drill, lease timings)
  - [ ] Demo script and presentation material following the brief's six points

### MKC-45: Showcase upload (user task)

- **Goal:** the project is on the Turing College showcase.
- **Scope:** feature 64.
- **Depends on:** MKC-44.
- **Success criteria:**
  - [ ] Uploaded by the user; the link added near the top of the README in both repos

---

## Phase 7: RAG and decision layer

### MKC-46: Decision-layer spike

- **Goal:** prove or disprove the Jev call path via OpenRouter.
- **Scope:** feature 65.
- **Depends on:** MKC-13.
- **Test:** a live call with three Noul questions and one Choice question through `langchain-typesafe` against OpenRouter (`~typesafe/jev-latest`); the response is parsed into typed answers.
- **Success criteria:**
  - [ ] Result recorded in ADR 004 and the status doc: working path, or the documented alternative
  - [ ] The LLM fallback stays the default until this passes

### MKC-47: DecisionClient and wiring

- **Goal:** guard and gating decisions come from the decision layer, with a fallback switch.
- **Scope:** features 66 and 67.
- **Depends on:** MKC-46, MKC-36, MKC-26.
- **Interfaces:**
  - **Produces:** `mkc.decision.client.DecisionClient`, with `noul(q, state) -> float`, `choice(q, criteria, state) -> ChoiceAnswer` and `score(q, rubric, state) -> ScoreAnswer`.
  - Backend chosen by `MKC_DECISION_BACKEND=jev|llm`.
- **Test:**
  - `test_fallback_switch_routes_to_llm`
  - `test_thresholds_compared_as_bands`
  - wiring tests for the scope guard, follow-up gating, injection guard, page triage and review priority
- **Success criteria:**
  - [ ] Flagged injection content is shown to a human, never silently dropped (test)
  - [ ] `langchain-typesafe` pinned

### MKC-48: E8, decision-layer evaluation

- **Goal:** compare decision-model and LLM decisions on labelled sets.
- **Scope:** feature 68.
- **Depends on:** MKC-47, MKC-31.
- **Success criteria:**
  - [ ] **User task:** labelled sets verified (scope, fact-stated, injection, page triage); hours logged
  - [ ] Accuracy, calibration, latency and cost per question and backend; thresholds tuned on dev, pinned in config

### MKC-49: Corpus loader, chunking and embeddings

- **Goal:** the narrow legal corpus is loaded, chunked per paragraph, embedded and indexed.
- **Scope:** features 69 and 70.
- **Depends on:** MKC-5.
- **Interfaces:**
  - **Produces:** tables `corpus_document`, `chunk(embedding vector, tsv tsvector)`, CLI `mkc corpus load`, and `backend/data/corpus_sources.yaml` (EnWG §14a, MsbG, BK6-22-300 + Anlage 1, BK8-22/010-A, operator texts; licence class per source).
- **Test:**
  - `test_chunk_boundaries_follow_paragraphs` (synthetic law text)
  - `test_every_chunk_has_source_reference`
  - `test_non_official_sources_not_written_to_repo`
- **Success criteria:**
  - [ ] One multilingual embedding model chosen and recorded in ADR 004

### MKC-50: Hybrid retriever

- **Goal:** keyword and vector search combined, robust for paragraph references.
- **Scope:** feature 71.
- **Depends on:** MKC-49.
- **Interfaces:**
  - **Produces:** `retrieve(query, k) -> list[RetrievedChunk(chunk_id, score, source_ref, text)]`, using reciprocal rank fusion.
- **Test:**
  - `test_paragraph_reference_found_by_keyword` ("§ 14a")
  - `test_rrf_merges_rankings`
  - `test_retrieved_text_marked_untrusted`
- **Success criteria:**
  - [ ] Latency per query logged in the trace
- **As built (decisions 79 to 81):** `retrieve(query, k=5, *, session, embedder, tracers=(), scope=None)` in `mkc.rag.retriever`; the embedder needs `embed_query` (the query instruction lives there). The keyword side ORs the query's terms; a third ranking, the reference side, keeps a paragraph the query names (`§ 14a Abs. 1`) in the result. Latency: one `RetrievalTrace` per call; `Tracer.span_retrieval` writes it to `run_log` (kind `retrieval`) and Langfuse (`retriever`) when the call has a run scope, otherwise only a log line. `EmbeddingClient` has trace hooks (`EmbedTrace`). For MKC-51: build prompts from `RetrievedChunk.as_prompt_data()` only, and decide how "ask why" retrievals (no run) are traced. The MKC-49 review findings 1 to 5 and `MKC_CORPUS_SOURCES_FILE` are in this ticket too.

### MKC-51: Legal reasons and "ask why"

- **Goal:** recommendations quote the legal reasons, and users can ask grounded follow-up questions.
- **Scope:** features 72 and 73.
- **Depends on:** MKC-50, MKC-38.
- **Interfaces:**
  - **Produces:** `POST /api/advisor/why {recommendation_id, question} -> GroundedAnswer(text, citations)`.
- **Test:**
  - `test_answer_cites_only_retrieved_or_approved_sources`
  - `test_no_relevant_passage_returns_not_covered`
  - `test_injection_passage_does_not_change_answer_policy`
- **Success criteria:**
  - [ ] UI shows quoted passages with source links

### MKC-52: E7, RAG evaluation

- **Goal:** measure retrieval and grounding quality.
- **Scope:** feature 74.
- **Depends on:** MKC-51, MKC-31.
- **Success criteria:**
  - [ ] **User task:** gold passages for about 20 "why" questions verified; hours logged
  - [ ] precision@k and recall@k for hybrid vs vector vs keyword; RAGAs faithfulness, answer relevancy, context precision

### MKC-53: Re-run E3/E5 and update the release

- **Goal:** the submitted state reflects Phase 7 honestly.
- **Scope:** feature 75.
- **Depends on:** MKC-47, MKC-51, MKC-52, MKC-48.
- **Success criteria:**
  - [ ] E3 and E5 re-run; differences to the Phase 6 results explained
  - [ ] Eval page shows E1–E8; README, showcase and status doc updated in both repos

---

## Phase 8: Optional extras

### MKC-54: Read-only MCP server for the catalogue

- **Scope:** feature 76.
- **Success criteria:**
  - [ ] Tools: `list_operators`, `get_concept`, `compare_by_lbs`; read-only
  - [ ] Security notes (confused deputy, rate limits) in the README
  - [ ] Tested with an MCP client

### MKC-55: LangGraph comparison arm for E4

- **Scope:** feature 77.
- **Success criteria:**
  - [ ] The extraction item loop ported to LangGraph with its checkpointer
  - [ ] E4 run as a third arm
  - [ ] Findings added to ADR 001

### MKC-56: Third operator

- **Scope:** feature 78.
- **Success criteria:**
  - [ ] A third catalogue (e.g. VBEW-based) loaded at runtime, extracted, approved and evaluated
  - [ ] Licence handling documented

## Deferred (cut in the independent review; kept for later)

- **MKC-57: Broader RAG corpus** (feature 79). Success: EEG passages, BDEW guides and edi@energy documents fetched at runtime, never committed; E7 re-run.
- **MKC-58: Embedding-model comparison** (feature 80). Success: local multilingual model vs Gemini embeddings compared in E7; choice recorded in ADR 004.
- **MKC-59: Reranker** (feature 81). Success: the reranker added behind a switch; the E7 delta reported.
- **MKC-60: Automated monthly restore test** (feature 82). Success: a scheduled CI job restores the latest dump and checks row counts; failure alerts.

---

## Coverage check (spec → tickets)

| Spec features | Tickets |
|---|---|
| 0–13 (Phase 0) | MKC-1 to MKC-12 |
| 14–26 (Phase 1) | MKC-13 to MKC-20 |
| 27–34 (Phase 2) | MKC-21 to MKC-25 |
| 35–43 (Phase 3) | MKC-26 to MKC-30 |
| 44–50 (Phase 4) | MKC-31 to MKC-35 |
| 51–56 (Phase 5) | MKC-36 to MKC-39 |
| 57–64 (Phase 6) | MKC-40 to MKC-45 |
| 65–75 (Phase 7) | MKC-46 to MKC-53 |
| 76–78 (Phase 8) | MKC-54 to MKC-56 |
| 79–82 (Deferred) | MKC-57 to MKC-60 |
