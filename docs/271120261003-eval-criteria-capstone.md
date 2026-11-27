# Capstone evaluation criteria: tracking

**Last updated:** 27.11.2026, 10:03

This doc tracks the capstone's grading criteria and where the project shows each one. Update it when Turing College changes the criteria or when a ticket adds evidence.

## Official criteria (from the brief)

Source: `AE.CAP_afa.md`, section "Evaluation criteria". The reviewer scores each criterion separately; the shares are rounded (they add up to 99 %).

| # | Area | Criterion | Share |
|---|---|---|---|
| 1 | Application and functionality | Completeness and functionality of the project | 23 % |
| 2 | Application and functionality | User interface and interaction quality (if applicable) | 15 % |
| 3 | Application and functionality | Clear explanation of purpose, implementation and impact; a concise README paragraph on the goal, the problem solved and how the project works | 8 % |
| 4 | AI engineering techniques | Effective use and understanding of frameworks and tools (e.g. LangChain, Claude Code, OpenRouter) | 15 % |
| 5 | AI engineering techniques | Best practices applied in AI engineering and application design | 15 % |
| 6 | Security and quality | Awareness of security, privacy and quality considerations in AI application development | 15 % |
| 7 | Showcase submission (optional) | Upload to showcase.turingcollege.com before the review; link it in the README | 8 % |

## With the new evals criterion (estimate)

On 27.11.2026 Turing College added a criterion, effective immediately: **"Effective use of evals for optimising and ensuring the reliability of core AI functionalities"**, about 13 % of the score.

- The announcement gives only "~13 %". It does not say how the other shares change.
- The shares below assume the seven old shares were scaled down evenly. **They are an estimate, not the official table.** Replace them when Turing publishes the new weights.

| # | Criterion | Old share | Estimated new share |
|---|---|---|---|
| 1 | Completeness and functionality | 23 % | ~20 % |
| 2 | User interface and interaction quality | 15 % | ~13 % |
| 3 | Explanation of purpose, implementation and impact (README) | 8 % | ~7 % |
| 4 | Frameworks and tools | 15 % | ~13 % |
| 5 | Best practices in AI engineering and design | 15 % | ~13 % |
| 6 | Security, privacy and quality | 15 % | ~13 % |
| 7 | Showcase submission (optional) | 8 % | ~7 % |
| 8 | **Effective use of evals (new)** | — | **~13 %** |

What the announcement asks for under criterion 8:

- evals for the core AI functionality (e.g. answer quality for RAG, tool choice and task completion for an agent)
- a small set of representative test cases, a definition of "good", and runs of them
- evidence that the results were used to improve the project, and that changes did not break cases that passed before
- eval results brought to the review, with the choices explained

## Where the project shows each criterion

| # | Criterion | Evidence in this project | Status |
|---|---|---|---|
| 1 | Completeness and functionality | extraction workflow with human approval (Phases 1–4); site advisor (Phase 5); RAG and the decision layer (Phase 7) | in progress (MKC-16) |
| 2 | User interface | review queue, runs and trace, catalogue comparison, advisor, eval report page (design section 12) | planned |
| 3 | README explanation | README paragraph (MKC-2), final version at release | started |
| 4 | Frameworks and tools | LangChain for model and tool plumbing, OpenRouter with zero data retention, own harness (ADR 001); Claude Code workflow (ADR 005) | started (MKC-13 to MKC-15) |
| 5 | Best practices | TDD, tool allow-lists, checkpoints and resume, limits, traces, ADRs and a decision log | started |
| 6 | Security, privacy and quality | no side-effect tools for the model, untrusted data wrapped, Clerk auth, secret hygiene and gitleaks, protected deploys, backups (design section 10) | started |
| 7 | Showcase | upload before the review | not started |
| 8 | Evals | E1–E9 (design 11.4), per-case regression and CI gate (11.5), improvement log `eval/iterations.md` (11.6); decision 55 | planned (MKC-31, MKC-35, MKC-42) |
