# Architecture Decision Record (ADR) 004: Narrow RAG corpus and a decision layer with LLM fallback

- **Status:** accepted
- **Date:** 24.11.2026
- **Design reference:** design doc sections 6, 9, 11 and 20 (Phase 7)

## Context

The site advisor recommends a Messkonzept with deterministic rules over approved catalogue records. Two additions were made to the core:
1. **RAG**, so explanations and "ask why" answers can quote the legal and regulatory reasons.
2. **A decision layer**, so yes/no, choice and score decisions (scope guard, follow-up gating, injection guard, page triage, review priority) come from a decision model returning probabilities rather than from parsed LLM text.

An independent review of the design found that both were added late without budgets, phases or evaluations to match. It also found that the decision model's call path through OpenRouter is not documented by the client library (`langchain-typesafe`, alpha).

## Options considered

**RAG corpus:**

| Option | Pros | Cons |
|---|---|---|
| Broad: laws, BNetzA decisions, BDEW guides, edi@energy documents, operator texts; embedding bake-off; reranker | Deepest retrieval evaluation | Large gold set (user time), licence handling for BDEW material, more moving parts |
| **Narrow: EnWG §14a, MsbG, BK6-22-300 (+ Anlage 1), BK8-22/010-A, operator texts; one embedding model; hybrid retrieval without a reranker** | Covers every reason the household advisor needs; official texts are free to use; small E7 gold set | Less retrieval depth; no embedding comparison |

**Decision layer:**

| Option | Pros | Cons |
|---|---|---|
| Jev via OpenRouter only | One key; probabilities and calibration | Unverified call path; alpha library |
| **Jev via OpenRouter after a spike, LLM structured output as the default fallback** | Works from the first day; the probability story is added once proven; E8 compares both | One extra switch to maintain |
| LLM structured output only | Simplest | Loses the decision-model comparison, which differentiates the project |

## Decision

- **RAG: the narrow corpus.**
  - EnWG §14a, MsbG, BNetzA BK6-22-300 (with Anlage 1), BNetzA BK8-22/010-A, and the operator catalogue texts.
  - BK8-22/010-A stays because the advisor's §14a Modul 1/2 cases depend on it.
  - One multilingual embedding model in pgvector (Supabase), plus German full-text search, merged by reciprocal rank fusion.
- **Decision layer:** a `DecisionClient` targeting Jev via OpenRouter (`~typesafe/jev-latest`).
  - The **first issue is a spike** that proves the call path.
  - Until then, and whenever the switch is set, decisions use **LLM structured output** (`method="json_schema"`).
  - Thresholds are tuned on the dev split and pinned per model id.
- **Phasing:** both come in Phase 7, **after** the submittable release (Phase 6). E3 and E5 are re-run afterwards.
- **Deferred, not dropped:** the broader corpus (EEG, BDEW guides, edi@energy documents), an embedding comparison, a reranker.

## Consequences

- E7 (retrieval and grounding) and E8 (decision layer) have their own gold sets: about 1.5 h and 1 h of the user's 10–12 h verification budget, and €1–2 each of the LLM budget.
- Retrieved passages are untrusted input; the injection guard screens them as well.
- If the Jev spike fails, E8 reports the LLM fallback against a smaller alternative, and the README states why.
- `langchain-typesafe` is pinned; any breakage is contained by the fallback switch.
