# HANDOFF

**Last updated:** 24.11.2026, 16:27

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

- **Design approved;** ADRs 001–005 accepted; backlog MKC-1 to MKC-60 on the public board (issue number = key). The board's auto-add workflow is on: new issues land on the board by themselves.
- **Remotes:**
  - `origin` = qamran/Messkonzept-Copilot (home, public)
  - `turing` = TuringCollegeSubmissions/qshahz-AE.CAP.AFA.1.1 (code-only mirror, no issues; ADR 005 option (c), decision 35)
  - Both at `6650cbd` (merge of PR #72).
- **`main` is protected:** PRs only, enforced for admins. No required CI checks until MKC-6.
- **Agent rules:** `AGENTS.md` (CLAUDE.md imports it). The development agent continues without asking and stops only for genuine decisions (decision 36).
- **Done:**
  - MKC-1: board, labels, tickets, templates, branch protection (PR #65)
  - MKC-2: code-only Turing mirror, README with links, `scripts/check_readme.py` (PR #70)
  - MKC-3: assignment rule (PR #67), HANDOFF.md (PR #69), AGENTS.md + CLAUDE.md + `scripts/check_agents.py` (PR #72, after one FAIL and a fix)
- **No application code yet.**

## In progress

- **MKC-4** (#4), backend skeleton. Status `In progress`, assigned to `qamran`. Branch `mkc-4-backend-skeleton`. Plan: `docs/superpowers/plans/241120261627-mkc-4-backend-skeleton.md`.
- **MKC-4.1** (#73), FastAPI app, settings, health and version endpoints. `In progress`.
  - [ ] uv project in `backend/` (Python 3.12, ruff, mypy strict on `src/`)
  - [ ] tests for `/health` and `/api/version` (red)
  - [ ] `mkc.config.Settings` + `mkc.api.app:create_app()` (green); ruff + mypy pass
- **MKC-4.2** (#74), worker entrypoint with clean SIGTERM shutdown. `In progress`.
  - [ ] worker tests (red)
  - [ ] `mkc.worker.main:run()` + `mkc-worker` script (green); ruff + mypy pass
- [ ] Status doc; PR; review agent; merge; push `main` to `turing`

## Next steps

1. Finish MKC-4 on `mkc-4-backend-skeleton` (checklist above).
2. MKC-5 (database layer), then MKC-6 (secret hygiene and CI, required checks; also repo-wide markdown lint).

## Blocked / waiting on user

- Later setup tasks (listed in design doc section 13): Supabase project, Vercel account, provider API keys with caps, GitHub `production` environment, a domain with TLS. MKC-5 needs the Supabase project for its live part; its one-off Supabase check waits for that; migrations and tests use Docker Postgres.

## Recent log

Newest first. Times are local (CET), taken from git and GitHub.
- **24.11.2026 16:27** MKC-4: branch `mkc-4-backend-skeleton`; HANDOFF.md caught up after PR #72; plan written.
- **24.11.2026 16:26** MKC-4 (#4) to `In progress`, assigned to `qamran`; sub-issues MKC-4.1 (#73) and MKC-4.2 (#74) created, assigned, `In progress`. Board auto-add found to be on.
- **24.11.2026 16:25** `main` pushed to `turing`; `origin/main` == `turing/main` == `6650cbd`. #3 and #71 criteria ticked, both closed and `Done`. MKC-3 complete.
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
