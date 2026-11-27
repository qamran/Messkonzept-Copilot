# AGENTS.md

Project rules for every agent working in this repo. These rules come from the repo, not from any agent's memory. If a rule here conflicts with an older note somewhere else, this file and the ADRs win; fix the other place.

Read in this order at the start of a session:

1. This file.
2. `HANDOFF.md`: what is done, in progress, next and blocked, plus a newest-first log.
3. The ticket you are about to work on: `gh issue view <n> -R qamran/Messkonzept-Copilot`.
4. Background when needed: the design doc (`docs/superpowers/specs/241120261330-messkonzept-copilot-design.md`), the backlog (`docs/superpowers/plans/241120261500-ticket-backlog.md`), the ADRs (`docs/adr/`) and the status doc (`docs/241120261430-project-status.md`).

## Project purpose

Messkonzept-Copilot reads German grid operators' Messkonzept PDFs and turns them into structured records keyed by the BDEW Lokationsbündelstruktur (LBS). A human approves every record before it enters the catalogue. A site advisor then recommends the matching Messkonzept for a household site, with the LBS code, page citations and, from Phase 7, the legal reasons. It is a Turing College AI Engineering capstone (Case 5): a hand-built, reusable agent harness shown on this one workflow and measured against a simple loop.

## Roles

- **Development agent (Claude Opus 5.5):** pulls a ticket, breaks it into sub-issues, works test-first in atomic commits, pushes a branch, opens the PR and moves the ticket to `Testing`. After each merge it pulls `main`, pushes it to the `turing` remote, and approves the `cd` run's two `production` gates itself (decision 51).
- **Review agent (Fable):** reviews the PR item by item against the ticket's success criteria and this file, posts its verdict as a PR comment, and merges on PASS. It never writes or fixes the code it reviews.
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
4. Push, open a PR from `.github/pull_request_template.md` (`Closes #<issue>`, the key, the criteria with evidence, the test output), and set the ticket to `Testing`.
5. The review agent posts PASS or FAIL. **PASS + green CI:** it merges with a merge commit (never squash, never rebase), the ticket closes and goes to `Done`, and the development agent pushes `main` to `turing` and checks that `origin/main` and `turing/main` are the same commit. It then approves the `cd` run's `production` gates (`backend`, then `frontend`) with `gh api -X POST repos/qamran/Messkonzept-Copilot/actions/runs/<run>/pending_deployments` (only after a PASS merge with green CI), checks the smoke results and logs both approvals in HANDOFF.md. The user can still reject a deploy in GitHub (decision 51). **FAIL:** the ticket goes back to `In progress` and the development agent fixes the findings.

**HANDOFF.md** is the restart file. Update it in every commit and after every important ticket change: status change, sub-issue created or closed, PR opened or merged, review verdict. A change made outside a branch (on the board, a merge, a push to `turing`) goes into the next commit. Log times are local time (CET) taken from git and GitHub, never estimated. When a session's context passes about 80 %, make sure HANDOFF.md is current, tell the user and recommend a restart.

`main` is protected: PRs only, no force-push, no deletion.

## Commits

- Format: `MKC-<n>: <summary>` on the first line, a short body, then the trailer `Refs: qamran/Messkonzept-Copilot#<issue>` (the sub-issue being worked on).
- Atomic: one logical change per commit, under 200 lines where possible.
- Never skip hooks or bypass signing.

## Tests first

- Every code change starts with a failing test (TDD): write the test or check, run it and see it fail for the right reason, then write the code that makes it pass. Commit the red test before the code where that keeps commits atomic.
- Docs-only rules get a check script in `scripts/` (for example `check_handoff.py`, `check_readme.py`, `check_agents.py`), written the same way.
- CI must be green before merge (from MKC-6; until then, run the check scripts and tests yourself and paste the output into the PR).

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

The review agent checks each item and writes its evidence in the verdict comment:

- [ ] **Success criteria:** every success criterion of the ticket and its sub-issues is met, item by item.
- [ ] **Tests prove it:** the tests or check scripts prove each criterion; the test was red before the change and is green now; CI is green.
- [ ] **Global constraints:** the rules in this file hold (commit format and size, data, model and safety rules, assignment to `qamran`, merge commit only).
- [ ] **Docs updated:** design doc decision log, ADR, status doc and HANDOFF.md are current, and HANDOFF.md log times match git and GitHub.
- [ ] **No secrets:** no keys, tokens, `.env` content, real customer data or committed PDFs anywhere in the diff.

Verdict: PASS (merge with a merge commit) or FAIL (findings listed; do not merge).
