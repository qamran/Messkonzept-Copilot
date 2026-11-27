# Architecture Decision Record (ADR) 004: Narrow RAG corpus and a decision layer with LLM fallback

- **Status:** accepted
- **Date:** 24.11.2026
- **Design reference:** design doc sections 6, 9, 11 and 20 (Phase 7)
- **Amended:** 27.11.2026, the spike result (MKC-46, decisions 68 and 69; section at the end)

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

## Spike result (MKC-46, 27.11.2026): the call path works

The development agent of lane C ran the spike (decisions 68 and 69).

- **Working path:** `langchain-typesafe==0.1.0`'s `TypeSafeClassifier` with `base_url="https://openrouter.ai/api"` and our OpenRouter key. It posts to `https://openrouter.ai/api/v1/systemone`.
  - OpenRouter's API spec (`https://openrouter.ai/openapi.yaml`, read 27.11.2026) documents this path as "System One": "Compatible with the TypeSafe SDKs".
  - The native OpenRouter route for decision models is `POST /api/alpha/decisions` (same request shape, marked alpha). It is not used: the library cannot post there without overriding its endpoint.
- **Live evidence:** `uv run --env-file .env pytest -m live tests/decision/test_jev_live.py -v`: "1 passed in 10.26s" (27.11.2026, 20:47:56). Three Noul questions and one Choice question in one request, parsed into our typed answers.
  - The same request through `build_decision_model` and `DecisionClient` with a logging hook (20:48:21): HTTP 200, `has_pv` 0.99, `has_heat_pump` 0.99, `has_wallbox` 0.02, `scope` = `household` (confidence 1), `usage.cost` 0.000017934 (USD).
- **Model id:** `~typesafe/jev-latest` resolved to `typesafe/jev-1.14-20261014`. Thresholds are pinned per model id, so MKC-48 records the resolved id (`Decisions.model_id`) and may pin `typesafe/jev-1.14`.
- **Zero data retention:** the stock library sends no routing preferences. `build_decision_model` adds `provider: {"zdr": true, "data_collection": "deny"}` (the chat models' `OPENROUTER_ROUTING`) to every body by overriding the library's `_payload`.
  - OpenRouter honours `provider` on this path: a probe with `provider.only: ["nonexistent-provider"]` failed with 404, `failed_routing_step: "Filter by Allowed Providers"`.
  - OpenRouter's ZDR endpoint list (`/api/v1/endpoints/zdr`) names the `typesafe/zdr` endpoints of Jev 1.14 and 1.13. The probes do not show the `zdr` filter itself rejecting an endpoint.
- **The switch:** `MKC_DECISION_BACKEND` defaults to `llm`. The ticket allows switching to `jev` once the spike passes; it stays `llm` until MKC-47 builds the fallback and the wiring and MKC-48 compares both.
- **Notes for MKC-47:**
  - The API may answer a question with `{"type": "refusal"}`. `ClassifierResponse` 0.1.0 does not know it, so the whole reply fails validation (a `TypeSafeAPIResponseValidationError`). MKC-47 decides how a refusal is handled.
  - A Noul answer may carry a `confidence`; `NoulAnswer` 0.1.0 drops it.
  - `classify_error` already maps the library's HTTP errors by `status_code` (checked 27.11.2026: 429 and 502 are transient, 401 is an auth error) and its timeout (a `TimeoutError`). It misses `TypeSafeAPIConnectionError` and the `Retry-After` of a 429 (the library keeps the headers on the error, not on a response). MKC-47 closes both.
- **Spend:** three calls printed a cost (`usage.cost`, USD): 0.000011886, 0.000011886 and 0.000017934. Two 404 probes and the pytest run printed none. The full log is in `handoff/lane-c.md` and the status doc.
