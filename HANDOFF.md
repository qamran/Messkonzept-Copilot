# HANDOFF

**Last updated:** 24.11.2026, 15:45

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
  - `turing` = TuringCollegeSubmissions/qshahz-AE.CAP.AFA.1.1 (mirror)
  - Both at `7609490` (merge of PR #67).
- **`main` is protected:** PRs only, enforced for admins. No required CI checks until MKC-6.
- **Done:**
  - MKC-1: board, labels, tickets, templates, branch protection (PR #65)
  - MKC-3.1: assignment rule in the workflow docs (PR #67)
- **No application code yet.**

## In progress

- **MKC-3** (#3), agent instructions. Status `In progress`, assigned to `qamran`.
  - MKC-3.1 (#66): done.
  - **MKC-3.2 (#68): this file and its maintenance rule.** Branch `mkc-3-handoff`.
    - [x] `scripts/check_handoff.py` (failed before this file existed)
    - [x] `HANDOFF.md`
    - [x] rule in ADR 005, design doc section 14 and decision 34 (incl. restart at about 80 % context)
    - [ ] PR + review
  - Still to do in MKC-3: AGENTS.md (roles, ticket flow, commit rules, TDD, docs-current incl. HANDOFF.md, data, model and safety rules, review checklist) and a one-line CLAUDE.md.

## Next steps

1. Finish MKC-3.2 → PR → review agent → merge → push `main` to `turing`.
2. Finish MKC-3 (AGENTS.md, CLAUDE.md) as further sub-issues on new branches.
3. MKC-2 (issue mirror), once the user provides `TURING_ISSUES_TOKEN`.
4. MKC-4 (backend skeleton) once MKC-3 is done; then MKC-5, MKC-6 (CI + required checks).

## Blocked / waiting on user

- `TURING_ISSUES_TOKEN`: a fine-grained token with issues read/write on the Turing repo, stored as a repo secret. Blocks MKC-2.
- Optional: turn on the board's "Auto-add to project" workflow (board settings, UI only). Until then, the development agent adds new issues to the board itself.
- Later setup tasks (listed in design doc section 13): Supabase project, Vercel account, provider API keys with caps, GitHub `production` environment, a domain with TLS.

## Recent log

Newest first.
- **24.11.2026 15:45** HANDOFF rule added to ADR 005 + design doc (decision 34).
- **24.11.2026 15:40** MKC-3.2 started (#68, board `In progress`); `check_handoff.py` + `HANDOFF.md` written on `mkc-3-handoff`.
- **24.11.2026 15:35** PR #67 (MKC-3.1) review PASS, merged `7609490`, pushed to `turing`; #66 closed.
- **24.11.2026 15:25** MKC-3 started; assignment rule added to ADR 005 + design doc (decision 33); PR #67.
- **24.11.2026 15:15** PR #65 (MKC-1) review PASS, merged `8f9b7d0`, pushed to `turing`. MKC-2 and MKC-3 set to `Ready`.
- **24.11.2026 15:05** MKC-1: board, labels, 60 tickets, sub-issues #61–#64, templates, repo metadata, branch protection; PR #65.
- **24.11.2026 15:00** Ticket backlog approved and committed; both remotes synced.
- **24.11.2026** Design doc approved after an independent review; ADRs 001–005 written.

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
