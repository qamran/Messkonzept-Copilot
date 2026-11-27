# Capstone evaluation criteria: tracking

**Last updated:** 27.11.2026, 10:12

This doc tracks the capstone's grading criteria and where the project shows each one. Update it when Turing College changes the criteria or when a ticket adds evidence. The full brief is in `AE.CAP_afa.md`.

## Current criteria (official, since 27.11.2026)

Source: Turing College website, copied on 27.11.2026 (`AE.CAP_afa.md`, section "Evaluation criteria"). The reviewer scores each criterion separately; the shares are rounded (they add up to 99 %).

| # | Area | What the reviewer checks | Weight |
|---|---|---|---|
| 1 | Application and functionality | Completeness and functionality of the project | 20 % |
| 2 | Application and functionality | User interface and interaction quality (if applicable) | 13 % |
| 3 | Application and functionality | Clear explanation of purpose, implementation and impact; a concise README paragraph on the goal, the problem solved and how the project works | 7 % |
| 4 | AI engineering techniques | Effective use and understanding of frameworks and tools (e.g. LangChain, Claude Code, OpenRouter) | 13 % |
| 5 | AI engineering techniques | Best practices applied in AI engineering and application design | 13 % |
| 6 | AI engineering techniques | **Effective use of evals for optimising and ensuring the reliability of core AI functionalities** (new) | 13 % |
| 7 | Security and quality | Awareness of security, privacy and quality considerations in AI application development | 13 % |
| 8 | Showcase submission (optional) | Upload to showcase.turingcollege.com before the review; link it near the top of the README | 7 % |

## What changed on 27.11.2026

| # | Criterion | Before (brief of 23.11.2026) | Now |
|---|---|---|---|
| 1 | Completeness and functionality | 23 % | 20 % |
| 2 | User interface | 15 % | 13 % |
| 3 | README explanation | 8 % | 7 % |
| 4 | Frameworks and tools | 15 % | 13 % |
| 5 | Best practices | 15 % | 13 % |
| 6 | **Evals (new)** | — | **13 %** |
| 7 | Security, privacy and quality | 15 % | 13 % |
| 8 | Showcase (optional) | 8 % | 7 % |

Two more changes in the brief:

- **AI evaluations are now required.** The review topics were "recommendations"; now only the relevant topics need implementing, *except AI evaluations, which every capstone must include*.
- **The AI evaluations topic asks for more:** show eval results for the core AI functionality, and how you used them to improve the project, besides choosing representative test tasks, defining success criteria and checking that changes do not reduce quality on tasks that passed before.

Turing's announcement adds what this looks like in practice:

- evals for the core AI functionality (e.g. answer quality for RAG, tool choice and task completion for an agent)
- a small set of representative test cases, a definition of "good", and runs of them
- evidence that the results were used to improve the project, and that changes did not break cases that passed before
- eval results brought to the review, with the choices explained
- course refreshers: Sprint 1 Part 4 (prompt evaluation, LLM-as-a-judge), Sprint 2 Part 4 (RAGAs, DeepEval), Sprint 2 Part 5 (tool-calling evals)

## Where the project shows each criterion

| # | Criterion | Evidence in this project | Status |
|---|---|---|---|
| 1 | Completeness and functionality | extraction workflow with human approval (Phases 1–4); site advisor (Phase 5); RAG and the decision layer (Phase 7) | in progress (MKC-16) |
| 2 | User interface | review queue, runs and trace, catalogue comparison, advisor, eval report page (design section 12) | planned |
| 3 | README explanation | README paragraph (MKC-2), final version at release | started |
| 4 | Frameworks and tools | LangChain for model and tool plumbing, OpenRouter with zero data retention, own harness (ADR 001); Claude Code workflow (ADR 005) | started (MKC-13 to MKC-15) |
| 5 | Best practices | TDD, tool allow-lists, checkpoints and resume, limits, traces, ADRs and a decision log | started |
| 6 | Evals | E1–E9 (design 11.4), per-case regression and CI gate (11.5), improvement log `eval/iterations.md` (11.6); decision 55 | planned (MKC-31, MKC-35, MKC-42) |
| 7 | Security, privacy and quality | no side-effect tools for the model, untrusted data wrapped, Clerk auth, secret hygiene and gitleaks, protected deploys, backups (design section 10) | started |
| 8 | Showcase | upload before the review, link near the top of the README | not started |
