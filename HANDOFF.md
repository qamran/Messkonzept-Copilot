# HANDOFF

**Last updated:** 24.11.2026, 16:15

This file is how agents resume work after a session restart.
- **Updated:** in every commit, and after every important ticket change: status change, sub-issue created or closed, PR opened or merged, review verdict. A change made outside a branch (e.g. on the board) is recorded in the next commit.
- **This file vs the status doc:** this file is the running log and next steps for agents. `docs/241120261430-project-status.md` is the overview of decisions and documents.

## Read this first

1. `AGENTS.md`, once MKC-3 is merged. Until then, ADR 005: `docs/adr/241120261456-adr-005-ticket-workflow.md`.
2. This file, top to bottom.
3. The ticket you are about to work on: `gh issue view <n> -R qamran/Messkonzept-Copilot`.
4. Background when needed:
   - design doc: `docs/superpowers/specs/241120261330-messkonzept-copilot-design.md`
   - backlog: `docs/superpowers/plans/241120261500-ticket-backlog.md`
   - ADRs: `docs/adr/`

**Roles:**
- **Development agent** (Claude Opus 5.5): pulls a ticket, sets it to `In progress`, assigns the ticket, sub-issues and PR to `qamran`, works test-first in atomic commits (`MKC-<n>: …` + `Refs:`), pushes a branch, opens a PR, and sets the ticket to `Testing`.
- **Review agent** (Fable): checks the PR against the success criteria, posts its verdict, and merges on PASS.
- **After each merge:** the development agent pulls `main` and pushes it to the `turing` remote.

## Current state

- **Design approved;** ADRs 001–005 accepted; backlog MKC-1 to MKC-60 on the public board (issue number = key).
- **Remotes:**
  - `origin` = qamran/Messkonzept-Copilot (home, public)
  - `turing` = TuringCollegeSubmissions/qshahz-AE.CAP.AFA.1.1 (code-only mirror, no issues; ADR 005 option (c), decision 35)
  - Both at `7b11612` (merge of PR #70).
- **`main` is protected:** PRs only, enforced for admins. No required CI checks until MKC-6.
- **Done:**
  - MKC-1: board, labels, tickets, templates, branch protection (PR #65)
  - MKC-2: code-only Turing mirror, README with links, `scripts/check_readme.py` (PR #70)
  - MKC-3.1: assignment rule in the workflow docs (PR #67)
  - MKC-3.2: HANDOFF.md and its maintenance rule (PR #69, after one FAIL and a fix)
- **No application code yet.**

## In progress

- **MKC-3** (#3), agent instructions. Status `In progress`. MKC-3.1 and MKC-3.2 done.
- **MKC-3.3** (#71), AGENTS.md and CLAUDE.md. Status `In progress`, assigned to `qamran`, sub-issue of #3. Branch `mkc-3-agents-md`.
  - [x] HANDOFF.md caught up after PR #70; design doc "Remotes" line fixed
  - [ ] `scripts/check_agents.py` test-first (red)
  - [ ] AGENTS.md with the required sections and the review checklist
  - [ ] CLAUDE.md, one line pointing to AGENTS.md (check green); markdown lint
  - [ ] HANDOFF "Read this first" points to AGENTS.md; status doc
  - [ ] PR; #3 and #71 to `Testing`; review agent; merge; push `main` to `turing`

## Next steps

1. Finish MKC-3.3 on `mkc-3-agents-md` (checklist above); MKC-3 closes with it.
2. MKC-4 (backend skeleton); then MKC-5, MKC-6 (CI + required checks).

## Blocked / waiting on user

- Optional: turn on the board's "Auto-add to project" workflow (board settings, UI only). Until then, the development agent adds new issues to the board itself.
- Later setup tasks (listed in design doc section 13): Supabase project, Vercel account, provider API keys with caps, GitHub `production` environment, a domain with TLS.

## Recent log

Newest first. Times are local (CET), taken from git and GitHub.
- **24.11.2026 16:15** MKC-3: branch `mkc-3-agents-md`; HANDOFF.md caught up after PR #70; design doc "Remotes" line updated.
- **24.11.2026 16:15** MKC-3.3 (#71) created as sub-issue of #3, assigned to `qamran`, on the board as `In progress`.
- **24.11.2026 15:57** `main` pushed to `turing`; `origin/main` == `turing/main` == `7b11612`. #2 criteria ticked, board `Done`.
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
