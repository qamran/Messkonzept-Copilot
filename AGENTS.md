# AGENTS.md

Project rules for every agent working in this repo. These rules come from the repo, not from any agent's memory. If a rule here conflicts with an older note somewhere else, this file and the ADRs win; fix the other place.

Read in this order at the start of a session:

1. This file.
2. `HANDOFF.md`: what is done, in progress, next and blocked, plus a newest-first log. A lane agent then reads its lane file, `handoff/lane-<x>.md`.
3. The ticket you are about to work on: `gh issue view <n> -R qamran/Messkonzept-Copilot`.
4. Background when needed: the design doc (`docs/superpowers/specs/241120261330-messkonzept-copilot-design.md`), the backlog (`docs/superpowers/plans/241120261500-ticket-backlog.md`), the ADRs (`docs/adr/`) and the status doc (`docs/241120261430-project-status.md`).

## Project purpose

Messkonzept-Copilot reads German grid operators' Messkonzept PDFs and turns them into structured records keyed by the BDEW Lokationsbündelstruktur (LBS). A human approves every record before it enters the catalogue. A site advisor then recommends the matching Messkonzept for a household site, with the LBS code, page citations and, from Phase 7, the legal reasons. It is a Turing College AI Engineering capstone (Case 5): a hand-built, reusable agent harness shown on this one workflow and measured against a simple loop.

## Roles

- **Coordinator (Claude Opus 5.5, the main session):** picks the wave and the lanes, creates the worktrees, starts the agents of each lane, owns the shared files (see "Parallel lanes"), runs the merge queue, and writes `HANDOFF.md`. After each merge it pulls `main`, pushes it to the `turing` remote, and approves the `cd` run's two `production` gates itself (decisions 51 and 61). It reports to the user once per merged PR and when a lane is blocked. It never writes lane code. When no lanes run, the coordinator is also the development agent.
- **Test agent (Claude Opus 5.5, Sonnet for small tickets), one per lane:** before the development agent starts, reads the ticket and the design and writes red acceptance tests for every success criterion, committed on the lane branch. At the end it runs a mutation pass on the development agent's code and reports the surviving mutants. It never writes or fixes production code.
- **Development agent (Claude Opus 5.5), one per lane:** pulls its lane's ticket, breaks it into sub-issues, works test-first in atomic commits, makes the test agent's tests green, keeps `handoff/lane-<x>.md`, runs `scripts/pre_pr.sh`, pushes the branch, opens the PR and moves the ticket to `Testing`. It changes a test agent's test only with a reason in the PR body, and never touches another lane's package.
- **Review agent (Fable), one per PR:** starts only when `gh pr checks` is green. Reviews the PR item by item against the ticket's success criteria and this file, posts its verdict as a PR comment, and merges on PASS. It never writes or fixes the code it reviews.
- **User (`qamran`):** owns decisions on scope and design, and the setup tasks only a human can do (accounts, keys, secrets). The development agent does not ask the user for permission to start the next ticket or step; it stops only for a genuine decision (decision 36).

## Ticket flow

Full rules: ADR 005 (`docs/adr/241120261456-adr-005-ticket-workflow.md`) and design doc section 14.

- **Where:** GitHub Issues with native sub-issues in `qamran/Messkonzept-Copilot`, on the public board <https://github.com/users/qamran/projects/1>. Status: `Backlog → Ready → In progress → Testing → Done`.
- **Keys:** `MKC-<n>` (issue number = key) in the issue title, the branch name (`mkc-<n>-<slug>`) and every commit. Sub-issues are `MKC-<n>.<m>`.
- **The Turing repo is a code-only mirror:** it gets the same commits but has no issues (ADR 005 option (c)). Never create issues there.

Per ticket:

1. Take the highest-priority `Ready` ticket, set it to `In progress`, and **assign it to `qamran`**. Do the same for every sub-issue you create and for the PR.
2. Break it into sub-issues in the ticket format (goal, scope, depends on, interfaces, test, success criteria). Add each to the board and link it to its parent.
3. Branch `mkc-<n>-<slug>` from `main`. Work test-first in atomic commits.
4. Run `bash scripts/pre_pr.sh` (CI's exact `backend` and `docs` commands, then the commit check). Only when it exits 0: push, open a PR from `.github/pull_request_template.md` (`Closes #<issue>`, the key, the criteria with evidence, the gate's output as it is), and set the ticket to `Testing`.
5. The review agent starts once `gh pr checks` is green and posts PASS or FAIL. **PASS + green CI:** it merges with a merge commit (never squash, never rebase), the ticket closes and goes to `Done`, and the coordinator pushes `main` to `turing` and checks that `origin/main` and `turing/main` are the same commit. It then approves the `cd` run's `production` gates (`backend`, then `frontend`) with `gh api -X POST repos/qamran/Messkonzept-Copilot/actions/runs/<run>/pending_deployments` (only after a PASS merge with green CI), checks the smoke results and logs both approvals in HANDOFF.md. The user can still reject a deploy in GitHub (decision 51). **FAIL:** the ticket goes back to `In progress` and the development agent fixes the findings.

**Restart files.** `HANDOFF.md` is the coordinator's restart file; each lane has its own, `handoff/lane-<x>.md`, made from `handoff/TEMPLATE.md` and written only by that lane's agents. Update your file in every commit and after every important ticket change: status change, sub-issue created or closed, PR opened or merged, review verdict. A change made outside a branch (on the board, a merge, a push to `turing`) goes into the next commit. Log times are local time (CET) taken from git and GitHub, never estimated; numbers are copied from tool output, never added up or estimated. When a session's context passes about 80 %, make sure your restart file is current, tell the coordinator (or, for the coordinator, the user) and recommend a restart.

`main` is protected: PRs only, no force-push, no deletion.

## Parallel lanes

Full rules: decision 61, ADR 005 (amendment of 27.11.2026) and the plan `docs/superpowers/plans/271120261901-parallel-lanes.md`.

- **A lane** is a chain of tickets that owns its own package and tests. Lanes run at the same time; tickets inside a lane run in order. The lanes and waves are in the backlog; their state is in `HANDOFF.md` "Lanes".
- **Phases:** a ticket that can be built in a parallel lane is built now, whatever its phase (the user, 27.11.2026). Phase 7 code may reach production before the Phase 6 release; the release notes say which parts are Phase 7 and still unused.
- **Waiting:** a lane whose next ticket depends on another lane's open ticket pauses; its agents stop rather than build against code that does not exist yet. A lane stays at most one ticket ahead of its slowest dependency.
- **Agents per lane:** the test agent writes the red acceptance tests first, then the development agent builds, then the test agent runs its mutation pass. Each lane works in its own git worktree on `mkc-<n>-<slug>`; no two agents write the same worktree at the same time.
- **Shared files, one rule each:**
  - `HANDOFF.md`: the coordinator only. Lanes write `handoff/lane-<x>.md`.
  - Migrations: `down_revision` = `main`'s head when the branch was cut. `test_single_migration_head` fails when `main` has two heads; the coordinator re-chains the second PR's revision when it updates the branch from `main`.
  - Decision log (design section 18): each lane uses only its block of numbers (status doc); unused numbers are marked "not used" at the wave's end.
  - Status doc, runbook, design sections, backlog: each lane edits only its own ticket's section and adds new sections at the end of its own area; the coordinator resolves text conflicts.
  - `config.py`, `.env.example`: append-only, one block per lane with a comment naming the ticket.
  - `pyproject.toml`, `uv.lock`: a lane that adds a dependency says so in its PR; after a rebase the coordinator runs `uv lock`; the lock is never hand-merged.
  - `mkc/harness/registry.py` item tools: lane A only.
  - The board: each agent moves only its own ticket and sub-issues.
- **Merge queue:** one merge at a time, by readiness (green CI and PASS first), not by ticket number; the backlog's dependencies still hold. Review starts only when `gh pr checks` is green. After each merge the coordinator updates every other open PR from `main`, and CI runs again. A FAIL goes back to its lane without blocking the others.
- **Questions:** lanes never ask the user. A design question goes to the coordinator, who asks the user if it is a genuine decision (decision 36).
- **Smoke tests:** the Compose and kind smoke tests use fixed names and ports; only the coordinator runs them, one at a time.
- **Budget:** live model calls need the coordinator's go and are logged per lane.

## Commits

- Format: `MKC-<n>: <summary>` on the first line, a short body, then the trailer `Refs: qamran/Messkonzept-Copilot#<issue>` (the sub-issue being worked on).
- Atomic: one logical change per commit, under 200 lines where possible.
- Never skip hooks or bypass signing.

## Tests first

- Every code change starts with a failing test (TDD): write the test or check, run it and see it fail for the right reason, then write the code that makes it pass. Commit the red test before the code where that keeps commits atomic.
- Docs-only rules get a check script in `scripts/` (for example `check_handoff.py`, `check_readme.py`, `check_agents.py`), written the same way.
- CI must be green before merge (from MKC-6; until then, run the check scripts and tests yourself and paste the output into the PR).
- Before a PR, `bash scripts/pre_pr.sh` must exit 0: it runs CI's exact `backend` and `docs` commands (`scripts/check_pre_pr.py` keeps them in step with `ci.yml`), checks every commit's subject and `Refs:` line, and lists the commits over 200 lines to disclose. Claims in a PR or a restart file come from that output, never from a partial run.

## Docs stay current

- A ticket that changes a decision updates, in the same PR: the design doc's decision log (section 18), the matching ADR (or a new ADR in `docs/adr/`), `docs/241120261430-project-status.md` and `HANDOFF.md`.
- New Markdown docs, specs and plans are named `ddMMyyyyHHmm-<topic>.md`.
- Docs are written in plain English: short sentences, lists over long paragraphs.

## Data rules

- **No PDFs in the repo:** operator PDFs and BDEW or edi@energy documents are never committed. Operator PDFs are fetched at runtime from allow-listed URLs. Tests use synthetic PDFs generated in the test, or live fetches marked `@pytest.mark.live`.
- **Gold data** holds only extracted facts and page references.
- **Synthetic only:** all sites are synthetic and the company ("Stadtwerke Musterstadt Messtechnik GmbH") is fictional. No real customer or personal data.
- **No mako:** hupe1980/mako is not used in any form: no code, no data model, no ideas.
- **No secrets in the repo:** `.env` is gitignored; secrets live in GitHub Secrets and Kubernetes Secrets.

## Model rules

- Every model call goes through `ModelClient` (or `DecisionClient` for decisions). No direct provider SDK calls elsewhere.
- OpenRouter is the default route, with zero-data-retention routing. The Gemini free tier is used only for public or synthetic input.
- LangChain is used only for model and tool plumbing (chat models, tool schemas, structured output). The loop and all control logic are our own. No LangGraph in the build (only in optional MKC-55), no Streamlit.
- Budgets: LLM spend €20–30 in total; the user's verification time 10–12 h in total. Every evaluation ticket records its spend in the status doc.

## Safety rules

- **The model never gets side-effect tools.** A side-effect tool reaches outside its own item: the network, the catalogue, the approval queue, or state that a re-run cannot overwrite by key (decision 53). So `save_draft` (its own item's draft, idempotent) is an item tool, and harness code enqueues the approval. Run-level operations (`fetch_document`, `segment_document`, `enqueue_approval`, `commit_record`) are harness code, never model tools. Tools can't be added at runtime.
- PDF text, images and retrieved passages are untrusted data; prompts wrap them as data.
- No record enters the catalogue without human approval.
- No recommendation without a citation; an inferred LBS code is never shown as if the operator had stated it.
- Workflows triggered by fork PRs get no secrets; `pull_request_target` is not used; deploys run only from `main` in the protected `production` environment.

## Review agent checklist

The review agent starts only when `gh pr checks` is green. It checks each item and writes its evidence in the verdict comment:

- [ ] **Success criteria:** every success criterion of the ticket and its sub-issues is met, item by item.
- [ ] **Tests prove it:** the tests or check scripts prove each criterion; the test was red before the change and is green now; CI is green. In a lane, the test agent's red tests are unchanged at the PR head (`git diff` of its red commit), or each change has a reason in the PR body.
- [ ] **Global constraints:** the rules in this file hold (commit format and size, data, model and safety rules, assignment to `qamran`, merge commit only).
- [ ] **Docs updated:** design doc decision log, ADR, status doc and HANDOFF.md are current, and HANDOFF.md log times match git and GitHub.
- [ ] **No secrets:** no keys, tokens, `.env` content, real customer data or committed PDFs anywhere in the diff.

Verdict: PASS (merge with a merge commit) or FAIL (findings listed; do not merge).
