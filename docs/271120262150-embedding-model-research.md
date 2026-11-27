# Embedding model research (MKC-49)

**Date:** 27.11.2026. **Decision:** 71 (confirmed by the user on 27.11.2026, with this note). **ADR:** 004, amendment of 27.11.2026.

**Result:** `qwen/qwen3-embedding-8b` through OpenRouter, cut to 1024 dimensions.

## Requirements

- **German legal text.** The corpus is EnWG § 14a, the MsbG, two BNetzA decisions and operator catalogues, all German.
- **Multilingual.** Questions can come in other languages, and the model must handle German well, not only English.
- **pgvector.** An index (HNSW or IVFFlat) on a `vector` column takes at most 2,000 dimensions. MKC-50 may want one.
- **Zero data retention.** Every call goes through OpenRouter with `zdr: true` and `data_collection: deny`, like the chat calls (AGENTS.md model rules).
- **Our provider layer.** No direct SDK calls outside `mkc/models/providers.py`.
- **Cost.** The LLM budget is €20–30 in total. The corpus is small, so price matters less than the rest.
- **Context length.** One chunk is one law Absatz. The longest real one (MsbG) is 7,836 characters, about 2,000 tokens. A 512-token model cannot embed it whole.

## How the candidates were checked

1. **OpenRouter's embedding models:** `GET https://openrouter.ai/api/v1/embeddings/models` on 27.11.2026 listed 40 models with price and context length.
2. **Zero-data-retention endpoints:** `GET https://openrouter.ai/api/v1/endpoints/zdr` on 27.11.2026. The two lists were matched by exact model id. 28 embedding models have such an endpoint.
3. **The workspace guardrail:** one tiny call per model (the word "Messstelle") with the zero-data-retention routing. The OpenRouter workspace of the local key refuses some models with "0 endpoints … available matching your guardrail restrictions". Refused calls cost nothing.
4. **Quality:** the model cards and the MTEB leaderboard. No German legal benchmark was found, and no comparison was run here (feature 80 is deferred).

## Probes and results (27.11.2026, local OpenRouter key)

| Time | Call | Result | Cost (as OpenRouter reported it) |
|---|---|---|---|
| 20:46 | `baai/bge-m3`, 2 sentences | refused by the guardrail | none |
| 20:46 | `qwen/qwen3-embedding-8b`, 1 word | OK, 4,096 dimensions | $0.00000004 |
| 20:46 | `mistralai/mistral-embed-2312`, 1 word | OK, 1,024 dimensions | $0.0000005 |
| 20:46 | `google/gemini-embedding-001`, `intfloat/multilingual-e5-large` | refused by the guardrail | none |
| 20:47 | Qwen3, 3 German sentences, on Nebius and on DeepInfra, without and with `dimensions=1024` | 4,096 or 1,024 dimensions as asked; every vector has length 1.000 | $0.00000077 per call |
| 20:47 | Qwen3, the same sentence on Nebius and on DeepInfra, 1,024 dimensions | cosine between the two vectors: **0.9942** | $0.00000027 per call |

What the probes show:

- **The dimension works on both endpoints.** Both providers honour `dimensions=1024` and return normalised vectors.
- **The endpoints agree.** The corpus and a later query may land on different providers; their vectors are nearly identical.
- **The meaning holds at 1,024 dimensions.** Two sentences about § 14a steering scored 0.474 (Nebius) and 0.481 (DeepInfra); a sentence about a PV meter scored 0.329 and 0.334 against the first.

The end-to-end run later that evening loaded EnWG § 14a (4 chunks) and the MsbG (220 chunks): 51,934 tokens, €0.000475.

## Why Qwen3-Embedding-8B

- **The route allows it.** The guardrail lets it through, with two zero-data-retention endpoints (Nebius, DeepInfra).
- **Multilingual and strong.** The model card names 100+ languages and rank 1 on the MTEB multilingual leaderboard (5 June 2025, score 70.58).
- **Long context.** 32k tokens per the model card (OpenRouter lists 40,960 on its model page). A whole Absatz fits.
- **Fits pgvector.** It cuts its vectors to any size from 32 to 4,096 (Matryoshka learning). 1,024 stays under the index limit.
- **Cheap.** $0.01 per million input tokens on both endpoints.
- **Open weights.** Apache 2.0, so a local copy could reproduce the vectors later.
- **Queries and documents.** Documents are embedded as stored. Queries get a one-sentence instruction, as the model card advises; MKC-50 adds it.

## Rejected models

| Model | Price per million tokens | Reason |
|---|---|---|
| `baai/bge-m3` | $0.01 | Refused by the guardrail; otherwise a close second (multilingual, 8k context, 1,024 dimensions) |
| `mistralai/mistral-embed-2312` | $0.10 | Allowed, but ten times the price, one zero-data-retention endpoint and no stated multilingual retrieval lead |
| `google/gemini-embedding-001` | $0.15 | Refused by the guardrail; 15 times the price |
| `openai/text-embedding-3-large` | $0.13 | 13 times the price; Azure endpoint only; not probed |
| `intfloat/multilingual-e5-large` | $0.01 | 512-token context; refused by the guardrail |
| `qwen/qwen3-embedding-4b` | $0.02 | The smaller sibling at twice the price; not evaluated |
| `google/gemini-embedding-2`, `openai/text-embedding-3-small`, `amazon/titan-embed-text-v2`, `perplexity/pplx-embed-*` | $0.004–0.20 | Not evaluated (no comparison in this ticket) |
| English 512-token models (`baai/bge-*-en-v1.5`, `intfloat/e5-*-v2`, `thenlper/gte-*`, `sentence-transformers/*`) | $0.005–0.01 | English only, per their OpenRouter descriptions |
| A local model | none | Needs a model download and a GPU, or slow CPU runs in the worker image; the provider route keeps every model call in one layer |

## Known gaps

- **No German legal-quality measurement yet.** The only quality source is the model card's multilingual rank of June 2025. Feature 80 (an embedding comparison) is deferred, so E7 measures retrieval quality later.
- **The production key's guardrail was not checked.** The probes used the local key. If production runs in another OpenRouter workspace, its guardrail must allow the model.
- **The guardrail decided part of the shortlist.** `baai/bge-m3` might have scored as well; it was not reachable on our route.

## Sources

- [Qwen3-Embedding-8B model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B) (languages, MTEB rank and date, context, dimensions, instructions, licence)
- [MTEB leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [OpenRouter embedding models](https://openrouter.ai/api/v1/embeddings/models) and [zero-data-retention endpoints](https://openrouter.ai/api/v1/endpoints/zdr), read on 27.11.2026
- [pgvector README](https://github.com/pgvector/pgvector) (index limit of 2,000 dimensions for `vector`)
- The probe and run log: `handoff/lane-d.md`, entries of 27.11.2026 from 20:49 on
