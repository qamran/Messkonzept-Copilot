# Multi-agent workflow plan: parallel lanes with dev, test and review agents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for the setup ticket. Steps use checkbox (`- [ ]`) syntax.

**Goal:**

- Build later tickets in parallel: several development agents, each with its own test agent, and one review agent per PR.
- Each lane works on code no other lane touches.
- Every PR keeps the quality bar of AGENTS.md.

**Why now:**

- **The tickets allow it.** Four `Ready`-able tickets depend on nothing open: MKC-21, MKC-36, MKC-46 and MKC-49.
- **The user decided on phases (27.11.2026):** "if it can be developed with parallel agents then develop it regardless of phase." So Phase 7 tickets (MKC-46, MKC-49) run now, beside Phase 2 and 3 work.

**Lessons from MKC-20 that this plan builds in:**

- **The checks did not match CI.** The pre-PR check ran `ruff format --check src tests`; CI runs `ruff format --check .`.
- **The review started too early.** It began before CI was green, so the first verdict was FAIL on red CI.
- **Numbers were not copied from output.** Several figures in HANDOFF were added up or estimated instead of taken from tool output.
- **Some tests could not fail.** The advisor and the reviewer had to find them.

## 1. Lanes: work that does not intersect

A lane is a chain of tickets that owns its own package and its own tests. Lanes run at the same time; tickets inside a lane run in order.

| Lane | Tickets, in order | Owns (new code) | Waits on another lane |
|---|---|---|---|
| **A. Extraction** | MKC-21 → MKC-22 → MKC-23 → MKC-25 → MKC-26 → MKC-28 | `mkc/extraction/`, the item tools in `mkc/harness/registry.py`, `backend/data/operators.yaml` | — |
| **A2. SachsenNetze** | MKC-27 (after MKC-21) | `mkc/extraction/sachsen*.py` | A (MKC-21) |
| **B. Advisor** | MKC-36 → (MKC-37 after MKC-30) → MKC-38 | `mkc/advisor/`, advisor API routes, advisor UI pages | MKC-37 waits on A (MKC-30) |
| **C. Decision layer** | MKC-46 → (MKC-47 after MKC-36, MKC-26) → MKC-48 | `mkc/decision/` (`DecisionClient`) | MKC-47 waits on A and B |
| **D. RAG** | MKC-49 → MKC-50 → (MKC-51 after MKC-38) | `mkc/rag/`, corpus loader, retriever | MKC-51 waits on B |

**Wave 1, now:** MKC-21 (A), MKC-36 (B), MKC-46 (C), MKC-49 (D). Four dev agents, four test agents.

**Later waves:** MKC-27 joins once MKC-21 is merged. Lanes that wait on another lane pause, and their agents stop rather than build against code that does not exist yet.

Each lane stays at most one ticket ahead of its slowest dependency, so a review FAIL never blocks more than one lane.

## 2. Shared files: one rule each

Lanes never touch each other's packages. A few files are shared by design. Each gets a rule, so two PRs never fight over the same lines.

| Shared file | Rule |
|---|---|
| `HANDOFF.md` | **Per-lane logs.** Each lane writes only `handoff/lane-<x>.md` (its "In progress", "Next" and log). The coordinator alone edits `HANDOFF.md`, which keeps the board summary, the links to the lane files and the merges and deploys. `check_handoff.py` checks the lane files too. |
| Migrations | Each PR adds its revision with `down_revision` set to `main`'s head when the branch was cut. A new test, `test_single_migration_head`, fails when `main` has two heads. Branch protection already requires the branch to be up to date, so the second PR to merge gets its revision re-chained by the coordinator when it updates that PR from `main` (a merge, never a rebase; AGENTS.md), then CI runs again. |
| Decision log (design section 18) | **Number blocks per wave.** Wave 1: decision 61 (this workflow, coordinator), 62–64 lane A, 65–67 lane B, 68–70 lane C, 71–73 lane D. Unused numbers are skipped and marked "not used" at the wave's end. |
| Status doc, runbook, design sections, backlog | Each lane edits only its own ticket's section, and adds new sections at the end of its own area. The coordinator resolves any text conflict at merge time. |
| `config.py`, `.env.example` | Append-only, one block per lane with a comment naming the ticket. Conflicts are line-adjacent only and the coordinator resolves them. |
| `pyproject.toml`, `uv.lock` | A lane that adds a dependency says so in its PR. After an update from `main`, the coordinator runs `uv lock` once; the lock is never hand-merged. |
| `registry.py` (item tools) | Owned by lane A only. Other lanes register nothing there. |
| The board | Each agent moves only its own ticket and its sub-issues. |

## 3. Agents and their jobs

| Agent | Model | Per | Job | Never does |
|---|---|---|---|---|
| **Coordinator** (the main session) | Opus 5.5 | 1 | picks the wave, sets the lanes up, creates worktrees, owns the shared files, runs the merge queue, pushes `turing`, approves the deploy gates, writes `HANDOFF.md`, reports to the user | write lane code |
| **Test agent** | Opus 5.5 (or Sonnet for small tickets) | 1 per lane | reads the ticket and the design; **before the dev agent starts**, writes the acceptance tests for every success criterion (red, committed on the lane branch); at the end, runs a mutation pass on the dev agent's code and reports surviving mutants | write or fix production code |
| **Dev agent** | Opus 5.5 | 1 per lane | plans the ticket, makes the sub-issues, writes its own unit tests first, makes the acceptance tests green, keeps `handoff/lane-<x>.md`, runs the pre-PR gate, opens the PR | change the test agent's tests without saying why in the PR; touch another lane's package |
| **Review agent** | Fable | 1 per PR | the AGENTS.md checklist, item by item; merges on PASS | start before CI is green; write code |

Why a separate test agent:

- **Independent tests.** Its tests are written from the ticket, not from the code, so they catch what the dev agent's own tests miss. In MKC-20 the advisor and the reviewer found weak tests late.
- **Mutation pass.** Its mutation pass is the evidence that the tests can fail; until now that evidence came only from the reviewer.

## 4. Mechanics

- **Worktrees:**
  - each dev agent runs with `isolation: "worktree"` on its own branch `mkc-<n>-<slug>`
  - its test agent works in the same worktree, before and after the dev agent
  - no two agents ever write the same worktree at the same time
- **Database:**
  - all lanes share the one Compose Postgres
  - each test session already makes its own throwaway database (`tests/conftest.py`), so lanes do not collide
  - the coordinator starts Docker once per wave and shuts it down (and WSL) when the wave ends
- **Smoke tests with fixed ports:**
  - the Compose smoke test (`mkc-smoke`) and the kind test (`mkc-smoke` cluster) use fixed names and ports
  - only the coordinator runs them, one at a time, before a merge
  - CI runs them anyway
- **The pre-PR gate (new, `scripts/pre_pr.sh`):**
  - runs exactly CI's commands: `uv sync --locked`, `ruff check .`, `ruff format --check .`, `mypy`, `pytest`, every `scripts/check_*.py`, markdownlint
  - writes the output to the PR body as it is
  - checks the `Refs:` trailers and lists the commits over 200 lines
  - a PR is opened only when it exits 0
- **Merge queue:**
  - one merge at a time, by the coordinator's order
  - review starts only when `gh pr checks` is green
  - after each merge, every other open PR is updated from `main` (required by branch protection) and CI runs again; a migration re-chain happens here
- **Deploys:**
  - each merge deploys (the `cd` workflow); the coordinator approves the gates after each PASS merge (decision 51)
  - with several merges in a row, the coordinator approves them in order and checks production after each
- **Status reporting:** the coordinator reports to the user once per merged PR (verdict, deploy, findings) and when a lane is blocked; lanes never ask the user directly.
- **Budget:**
  - **LLM spend:** live model calls (contract or demo runs) need the coordinator's go and are logged per lane; the total budget stays €20–30.
  - **Tokens:** a wave of four lanes runs about nine agents at once (four dev, four test and one reviewer per PR as PRs arrive). Expect several times the token use of one ticket at a time.
  - **The user's verification time** (10–12 h total) is spent per merged PR, not per lane.

## 5. What can go wrong, and the guard

| Risk | Guard |
|---|---|
| Two lanes need the same new helper | the first lane to need it puts it in its own package; the second asks the coordinator, who makes a tiny shared ticket |
| A lane's design question is really the user's | the dev agent stops and reports to the coordinator, who asks the user (decision 36 still holds) |
| The merge queue goes stale while CI reruns | merge order follows readiness (green CI and PASS first); a FAIL goes back to its lane without blocking others |
| The coordinator's context fills up | lane details live in the lane files and the PRs, not in the coordinator's context; it keeps only the summary |
| The dev agent edits the test agent's tests to make them pass | `git diff` of the test agent's red commit vs the PR head; any change needs a reason in the PR body, and the reviewer checks it |

## 6. Setup ticket (one PR, before wave 1)

A new issue, "Parallel lanes: workflow, gate and checks", built by the coordinator alone:

- [x] Decision 61 in the design doc (this workflow, the user's phase decision), ADR 005 amendment (lanes, agents, merge queue), `AGENTS.md` roles (coordinator, test agent) and the lane rules, `check_agents.py` updated
- [x] `handoff/` folder with a template, `HANDOFF.md` reduced to the coordinator's summary, `check_handoff.py` checks the lane files (red first)
- [x] `scripts/pre_pr.sh` (CI's exact commands, trailer and size report), with a test that it fails on a mis-formatted file (red first)
- [x] `test_single_migration_head` (red with a second head made in a test database)
- [x] Decision-number blocks for wave 1 written in the status doc
- [x] The backlog marks the lanes and wave 1

As built (MKC-168, #169–#173): the gate's own tests are pytest tests in `backend/tests` (the `backend` job runs them), and `commit_report.py` does the trailer and size report; the decision blocks are in the status doc, checked by `check_lanes.py`; the old HANDOFF log moved to `handoff/271120261920-handoff-log-archive.md`.

Then wave 1 starts: MKC-21, MKC-36, MKC-46 and MKC-49, each `Ready` → `In progress`, each with its test agent first.
