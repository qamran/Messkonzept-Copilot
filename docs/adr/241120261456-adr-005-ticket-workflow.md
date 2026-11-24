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

Issue numbers in the two repos diverge.

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
- **Turing mirror:** a GitHub Action in the home repo copies each issue to the Turing repo (same key, with a link back) and syncs open/closed state. Code is pushed to both remotes.
- **Trigger:** in-session to start ("next ticket"). A loop or schedule may come later.
- **Roles:**
  - **Development agent (Claude Opus 5.5):** pulls a ticket, breaks it into issues and sub-issues, works it in atomic commits (under 200 lines where possible) that each reference their issue, pushes to a separate branch, and moves the ticket to `Testing`.
  - **Review agent (Fable):** reviews the PR, merges it, and closes the ticket. It never writes the code it reviews.
- **Flow per ticket:**
  1. The **development agent** takes the highest-priority `Ready` ticket and sets it to `In progress`.
  2. It breaks the ticket into issues and sub-issues, each with a goal, a test and a success measure.
  3. It branches `mkc-<n>-<slug>` from `main`, works test-first, and makes atomic commits (under 200 lines where possible), each referencing its sub-issue.
  4. It pushes the branch, opens a PR (body: `Closes #<issue>` and the key), and sets the ticket to `Testing`.
  5. The **review agent** (Fable) reviews the PR against the ticket's success measures and the repo standards, and posts its verdict as a PR comment.
  6. **Pass + green CI:** the review agent merges (squash is not used, so the atomic commits are kept), the ticket closes, its status goes to `Done`, and `main` is pushed to both remotes.
  7. **Fail:** the ticket goes back to `In progress`, with the findings listed, and the development agent picks it up again.
- **Branch protection on `main`:** PRs only; required CI checks (lint, types, tests, eval gate, Helm/kind); no force-push. A bot cannot formally approve its own PR, so the gate is green CI plus the review agent's verdict comment.

## Consequences

- A small amount of automation to build in Phase 0: the board setup, labels, issue and PR templates, the mirror Action, and the branch protection.
- The review verdicts and the ticket history are public evidence for the "agentic coding" review topic.
- The mirror Action needs a fine-grained token, with write access to the Turing repo's issues only, stored as a secret.
- If the Turing organisation disallows issues or Actions tokens, fall back to option (c) and document it.
