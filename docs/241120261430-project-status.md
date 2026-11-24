# Project status: Messkonzept-Copilot

**Last updated:** 24.11.2026, 15:46

This is the living status document. It is updated whenever a decision is made or work is completed. Older brainstorming material lives in `brainstorming internal/` (gitignored and frozen).

## Where we are

- **Phase:** implementation, Phase 0 (foundation). The design doc was **approved by the user on 24.11.2026** (after an independent review, verdict "approve with changes", all required changes applied). No application code yet.
- **Restart file:** `HANDOFF.md` (repo root) is the agents' running log and next steps, updated with every commit and important ticket change (decision 34). This status doc stays the overview of decisions and documents.
- **Board:** https://github.com/users/qamran/projects/1 (public). Tickets MKC-1 to MKC-60 exist as issues #1 to #60 (issue number = key).
- **Done:** MKC-1 (ticket workflow and repo setup), merged in PR #65 after a review-agent PASS. Both remotes at the merge commit.
- **Also done:** MKC-3.1 (#66), assignment rule in the workflow docs, merged in PR #67.
- **Current ticket:** MKC-3 (agent instructions). MKC-3.2 (#68, HANDOFF.md) is in PR #69; AGENTS.md and CLAUDE.md follow.
- **Ready next:** MKC-2 (#2), redefined by user decision: code-only Turing mirror + README links, no issue mirror, no token.

## Key documents

| Document | Path |
|---|---|
| Design doc | `docs/superpowers/specs/241120261330-messkonzept-copilot-design.md` |
| Architecture Decision Record (ADR) 001: custom harness on LangChain plumbing | `docs/adr/241120261430-adr-001-harness.md` |
| ADR 002: Vercel frontend, k3s backend (+ worker, CD hardening) | `docs/adr/241120261430-adr-002-hosting.md` |
| ADR 003: Supabase instead of SQLite (+ restore drill) | `docs/adr/241120261430-adr-003-database.md` |
| ADR 004: narrow RAG corpus and decision layer with LLM fallback | `docs/adr/241120261441-adr-004-rag-and-decision-layer.md` |
| ADR 005: ticket workflow (GitHub Issues + public Projects board) | `docs/adr/241120261456-adr-005-ticket-workflow.md` |
| HANDOFF.md (agents' restart file) | `HANDOFF.md` |
| Ticket backlog (implementation plan, MKC-1 to MKC-60) | `docs/superpowers/plans/241120261500-ticket-backlog.md` |
| Official brief | `AE.CAP_afa.md` |

## Decisions so far (summary; the full log of 34 decisions is in design doc section 18)

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
- **Repos:** `origin` = https://github.com/qamran/Messkonzept-Copilot (personal, public, home); `turing` = the Turing submission mirror. `main` is pushed to both after every merge; both at `7609490` (merge of PR #67). Turing's initial commit incl. their brief `AE.CAP_afa.md` was pushed to `origin` on 24.11.2026 with the user's OK.
- **Ticket workflow (ADR 005):** GitHub Issues + sub-issues on a public Projects board (`Backlog → Ready → In progress → Testing → Done`); `MKC-<n>` keys in titles, branches and commits; the Turing repo as a code-only mirror (user decision 24.11.2026; formalised in MKC-2); tickets, sub-issues and PRs assigned to `qamran` (decision 33); one branch per ticket; the **development agent (Opus 5.5)** builds and moves tickets to Testing, the **review agent (Fable)** reviews, merges after green CI and closes; started in-session with "next ticket".
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
  - a domain with TLS (also needed for Clerk production)
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
- the Clerk preview check
- the primary user
- Modul 3 out of scope

User choices:
- 10–12 h of verification
- a narrow RAG corpus
- one restore drill
- cut features moved to the deferred list
