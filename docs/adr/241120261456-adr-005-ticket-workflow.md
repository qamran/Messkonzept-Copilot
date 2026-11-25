# Architecture Decision Record (ADR) 005: Ticket workflow on GitHub Issues and a public Projects board

- **Status:** accepted
- **Date:** 24.11.2026
- **Design reference:** design doc section 14

## Context

The user wants tickets defined in a public place:

- an agent pulls a ticket, breaks it into issues and sub-issues, and works it in atomic commits (under 200 lines where possible), each referencing its issue
- the agent pushes to a separate branch and moves the ticket to *Testing*
- a Fable reviewer agent reviews, merges and closes the ticket

The project has two remotes:

- `origin`: the personal public repo, which is home
- `turing`: the Turing College submission mirror

Issue numbers in the two repos would diverge if both held issues.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **GitHub Issues (with sub-issues) + a public GitHub Projects board** | Public on the user's profile; issues, branches, commits and PRs link natively; free; scriptable with `gh` | Issues are per repo; the Turing repo needs a mirror |
| Linear | Polished; GitHub integration | Not publicly browsable; no showcase value; one more system |
| Jira | Familiar in industry | Heavy for a solo project; public access needs setup; weaker GitHub link |

**Turing repo issues:**

- (a) auto-copy by a GitHub Action
- (b) the agent creates issues in both repos by hand
- (c) code only, with a link to the home issues

**Trigger:**

- an in-session command
- a loop or schedule
- a GitHub Action running Claude on a label

## Decision

- **Tickets:** GitHub Issues in `qamran/Messkonzept-Copilot` with native **sub-issues**, on a **public GitHub Projects board**. Status field: `Backlog → Ready → In progress → Testing → Done`.
- **Stable keys:** every ticket gets a key `MKC-<n>`, used in the issue title, the branch name (`mkc-<n>-<slug>`) and every commit message.
  - Commit format: `MKC-<n>: <summary>` with a trailer `Refs: qamran/Messkonzept-Copilot#<issue>`.
  - This stays unambiguous across both repos.
- **Turing mirror: option (c), code only.** The Turing repo receives the same commits as the home repo (`main` is pushed to both remotes) but no issues. The README in the repo root links to the public board, the issue list, the design doc, the ADRs and HANDOFF.md, so reviewers of either repo find the tickets. *(Changed 24.11.2026 by user decision in MKC-2; first decision was option (a), an issue-mirror Action.)*
- **Trigger:** in-session to start ("next ticket"). A loop or schedule may come later. Once started, the development agent goes on to the next ticket or step without asking the user for permission; it stops only for a genuine decision (scope or design choices, user-only setup tasks). *(Added 24.11.2026 at the user's request.)*
- **Agent instructions:** `AGENTS.md` (repo root) holds these rules for both agents, including the review agent's checklist; `CLAUDE.md` is one line importing it (MKC-3).
- **Roles:**
  - **Development agent (Claude Opus 5.5):** pulls a ticket, breaks it into issues and sub-issues, works it in atomic commits (under 200 lines where possible) that each reference their issue, pushes to a separate branch, and moves the ticket to `Testing`.
  - **Review agent (Fable):** reviews the PR, merges it, and closes the ticket. It never writes the code it reviews.
- **Flow per ticket:**
  1. The **development agent** takes the highest-priority `Ready` ticket, sets it to `In progress` and **assigns it to the user (`qamran`)**. The same applies to every sub-issue it creates and to the PR. *(Added 24.11.2026 at the user's request.)*
  2. It breaks the ticket into issues and sub-issues, each with a goal, a test and **success criteria**: a checklist of exactly what must be delivered and true before it counts as done (the ticket format in `docs/superpowers/plans/241120261500-ticket-backlog.md`).
  3. It branches `mkc-<n>-<slug>` from `main`, works test-first, and makes atomic commits (under 200 lines where possible), each referencing its sub-issue.
  4. It pushes the branch, opens a PR (body: `Closes #<issue>` and the key), and sets the ticket to `Testing`.
  5. The **review agent** (Fable) reviews the PR item by item against the ticket's success criteria and the repo standards, and posts its verdict as a PR comment.
  6. **Pass + green CI:** the review agent merges (squash is not used, so the atomic commits are kept), the ticket closes, its status goes to `Done`, and `main` is pushed to both remotes.
  7. **Fail:** the ticket goes back to `In progress`, with the findings listed, and the development agent picks it up again.
- **HANDOFF.md** (repo root) is the restart file for agents: what is done, in progress, next, blocked, and a newest-first log. It is updated in every commit and after every important ticket change (status change, sub-issue created or closed, PR opened or merged, review verdict); changes made outside a branch are recorded in the next commit. `scripts/check_handoff.py` checks its sections. When a session's context passes about 80 %, the development agent tells the user and recommends a restart, after making sure HANDOFF.md is current. *(Added 24.11.2026 at the user's request.)*
- **Branch protection on `main`:** PRs only; required CI checks (lint, types, tests, eval gate, Helm/kind); no force-push. A bot cannot formally approve its own PR, so the gate is green CI plus the review agent's verdict comment.
  - *Set 25.11.2026 in MKC-6 (decision 38):* the required checks are the `ci` jobs `backend`, `frontend`, `gitleaks`, `dependency-scan` and `docs`, pinned to the GitHub Actions app, with "branch must be up to date before merging". A PR branch that falls behind `main` must merge `main` in before it can be merged. The eval gate and Helm/kind checks are added with their tickets. `scripts/check_workflows.py` keeps the workflows free of `pull_request_target`, secrets and `paths` filters.
  - *Added 25.11.2026 in MKC-8 (decision 41):* the `ci` job `image` (Compose smoke test, image scan, multi-arch build) is a required check too. The job `publish` is not: it is skipped on PRs.

## Consequences

- A small amount of automation to build in Phase 0: the board setup, labels, issue and PR templates, and the branch protection. No mirror Action.
- The review verdicts and the ticket history are public evidence for the "agentic coding" review topic.
- No token or secret for the Turing repo is needed; the Turing repo has no issues of its own, and `scripts/check_readme.py` checks that the README links to the board and the issue list.
- Issue numbers and keys exist only in the home repo, so the `MKC-<n>` key in each commit is the link from Turing's history back to its ticket.
