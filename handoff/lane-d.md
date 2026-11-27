# Lane D: RAG

**Last updated:** 27.11.2026, 21:09

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-49` → `MKC-50` → `MKC-51` (MKC-51 waits on lane B's MKC-38)
- **Branch and worktree:** `mkc-49-corpus-loader`
- **Owns:** `backend/src/mkc/rag/`, the corpus loader, the retriever, `backend/tests/rag/`, `backend/data/corpus_sources.yaml`
- **Decision numbers:** 71–73

## In progress

- `MKC-49` (`#49`): built, all six sub-issues closed; the branch is pushed and waits for the test agent's mutation pass before the PR. The test agent's red acceptance tests are in `backend/tests/rag/`.
- **Red commits:** `97c18ea` to `f515d26` "MKC-49: red test for the corpus tables' downgrade" (the test agent's last commit on this branch; diff the tests against it).
- **Sub-issues** (all assigned to `qamran`, on the board, linked to `#49`):
  - `MKC-49.1` (`#179`) corpus sources file: done (`4ce0e06`), closed
  - `MKC-49.2` (`#181`) chunking per paragraph: done (`49462e7`), closed
  - `MKC-49.3` (`#182`) embedding model through the provider layer: done (`97b760c`, `0871d20`), closed
  - `MKC-49.4` (`#184`) corpus tables and migration 0012: done (`8f8117d`), closed
  - `MKC-49.5` (`#185`) corpus loader with the licence guard: done (`46f818c`), closed
  - `MKC-49.6` (`#186`) `mkc corpus load` and the HTTP fetcher: done (`5c5f50d`, `3e1c8aa`), closed

### Pinned interfaces (MKC-49)

The tests import these; module paths and names are fixed, internals are free.

- `mkc.rag.sources`
  - `DEFAULT_SOURCES_PATH` = `backend/data/corpus_sources.yaml`
  - `LicenceClass` enum: `OFFICIAL = "official"` (laws, BNetzA decisions: amtliche Werke), `RESTRICTED = "restricted"` (operator texts)
  - `SourceType` enum: `LAW = "law"`, `BNETZA_DECISION = "bnetza_decision"`, `OPERATOR_TEXT = "operator_text"`
  - `CorpusSource` with `id`, `title`, `source_type: SourceType`, `url`, `version`, `licence: LicenceClass`
  - `load_sources(path) -> list[CorpusSource]`; raises `CorpusSourceError(ValueError)` on a bad file
  - YAML: top-level `sources:` list; each entry has `id, title, source_type, url (https), version, licence` and never the text. Required ids: `enwg-14a`, `msbg`, `bk6-22-300`, `bk6-22-300-anlage-1`, `bk8-22-010-a`, plus at least one `operator_text`.
- `mkc.rag.chunking`
  - `Chunk` with `source_id`, `ordinal` (0, 1, 2, … in text order), `source_ref` (names the §, e.g. `§ 14a` or `§ 14a Abs. 1`; MKC-50's `RetrievedChunk.source_ref` reads it), `text`
  - `chunk_text(text, *, source_id) -> list[Chunk]`
  - Chunks do not overlap: each Absatz is in exactly one chunk.
- `mkc.rag.embeddings`
  - `EMBEDDING`: the one config value, with `.model: str` and `.dim: int`. ADR 004 must name `EMBEDDING.model` (the ticket's success criterion).
  - An `Embedder` protocol: `embed(texts: Sequence[str]) -> list[list[float]]` (the fake also has `model` and `dim`).
- `mkc.rag.loader`
  - `load_corpus(session, sources, *, embedder, fetcher, cache_dir=None, repo_root=<this repo>)`; works inside the caller's transaction
  - `fetcher: Callable[[CorpusSource], str]` returns the source's plain text
  - `CorpusLicenceError`: raised when `cache_dir` (resolved) is inside `repo_root` and any source is `restricted`, **before anything is written**
  - Re-loading replaces a source's chunks (keyed by `source_id`); no duplicates
  - The stored `chunk.text` is passed verbatim to `embed`; a model-specific prefix (e.g. a `passage:` prefix) lives inside the embedder
  - Any code that writes a source's text to disk (the loader's cache or the real fetcher from `make_fetcher`) applies the same guard. No test proves the cache is used; it may stay unused if no cache is needed.
- `mkc.rag.cli`
  - `corpus_app` (Typer) with `load --sources PATH`; exit 0 on success, 2 on a bad sources file
  - `make_embedder(settings)` and `make_fetcher(settings)`: module-level factories the tests monkeypatch
- Tables (columns the tests read); downgrade to base drops both, upgrade to head twice is a no-op
  - `corpus_document(id, source_id, title, source_type, url, version, licence)`
  - `chunk(id, document_id → corpus_document, ordinal, source_ref, text, embedding vector(EMBEDDING.dim), tsv tsvector)` with a GIN index on `tsv`; `tsv` uses the `german` configuration

### Shared-file rules for the development agent

- New ORM classes go at the end of `mkc/db/models.py` in a block commented `MKC-49`.
- The `corpus` sub-app is mounted at the end of `mkc/cli.py` with a comment (`app.add_typer(corpus_app, name="corpus")`).
- The migration is `0012` with `down_revision = "0011"`. Lane A also writes `0012`; the coordinator re-chains the second to merge. The tests name no revision.
- A new dependency (e.g. `pgvector`, an embedding library) is named in the PR; the coordinator runs `uv lock` after updates from `main`.
- The real embedder must respect the model rule: every model call goes through `ModelClient` (AGENTS.md). A local model that makes no provider call is the development agent's call; record it in ADR 004 and decision 71.

### Test agent's assumptions (open for the coordinator)

1. Chunk granularity (one chunk per § or per Absatz) is left open; the tests only require that no chunk crosses a §, no Absatz is lost and each chunk keeps the source's lines.
2. Licence classes are two: `official` and `restricted`. A cache of a restricted text inside the repo is refused for the whole load; nothing says whether an official text may be cached inside the repo, so the tests do not check it.
3. Who owns an on-disk cache of fetched texts, the loader (`cache_dir`) or the fetcher, and whether one is needed at all, is open; the guard applies either way.
4. The tests cover §-structured law text only; how BNetzA decisions and operator texts are split into sections is the development agent's design.

## Next steps

1. The test agent runs its mutation pass on `mkc/rag/` (and the embedding code at the end of `mkc/models/client.py` and `providers.py`) and reports the surviving mutants.
2. Then the development agent opens the PR (on the coordinator's word), discloses the commits over 200 lines and the new code in `mkc/models/` and `mkc/db/models.py`, and moves `#49` to Testing.
3. Open for the coordinator: decision 71 (the embedding model) needs the user's confirmation; PDF sources wait on the PDF library of MKC-21; the backend image does not copy `backend/data/` (as for the LBS file), so `mkc corpus load` in the container needs `--sources`.

## Recent log

- **27.11.2026 21:09** Development agent: `bash scripts/pre_pr.sh` exit 1: every step green (`742 passed, 1 skipped, 13 deselected, 4 warnings in 128.45s`) except the commit check: two trailers read `Refs: qamra/` (my typo in `6dcb8ef`, `2b3774a`). Fixed with `git filter-branch --msg-filter` on the unpushed range `f515d26..HEAD`; from the loader's red tests on, the SHAs changed (`6dcb8ef`→`1d4df45`, `2b94d13`→`46f818c`, `2b3774a`→`ecd4252`, `972af4f`→`5c5f50d`, `4666aef`→`3e1c8aa`, `76633d3`→`fcc30be`); `#185` got a correcting comment. `#186` closed.
- **27.11.2026 21:06** Development agent: status doc section "Lane D: RAG corpus (MKC-49)". Live end-to-end run 21:04:30–21:05:46 into a throwaway database (created and dropped by the script): `mkc corpus load --source enwg-14a --source msbg` exit 0, `enwg-14a: 4 chunks`, `msbg: 220 chunks`, `embeddings: 51934 tokens, 0.000475 EUR`; every vector 1024 dims; `plainto_tsquery('german', 'steuerbare Verbrauchseinrichtung')` finds `§ 14a Abs. 1` to `Abs. 4` first. Live spend of this lane so far (python sum of the logged costs): EUR `0.000479`, plus the first live-test run whose cost was not printed.
- **27.11.2026 21:04** Development agent: `mkc corpus load` (`mkc.rag.cli`: `--sources`, `--source`, `--cache-dir`; mounted at the end of `mkc/cli.py`) and the runbook section "RAG corpus (MKC-49)".
- **27.11.2026 21:03** Development agent: `mkc.rag.fetch` (https only, same-host redirects, 20 MB cap; gesetze-im-internet.de HTML to one line per heading and Absatz; PDFs refused until MKC-21's PDF library); `uv run pytest tests/rag/test_fetch_unit.py -q`: `13 passed`. Offline check on the real pages fetched at 20:39 (file times) into the session scratch folder (not the repo): EnWG § 14a gives 4 chunks, the MsbG 220 chunks (largest 7836 characters).
- **27.11.2026 21:00** Development agent: `#185` closed; red unit tests for the HTTP fetcher and `mkc corpus load` (`uv run pytest tests/rag/test_fetch_unit.py tests/rag/test_cli_unit.py -q`: `11 failed, 1 passed, 4 errors in 1.23s`).
- **27.11.2026 20:59** Development agent: `mkc.rag.loader` (`load_corpus`, `check_cache_dir`, `CorpusLicenceError`, `CorpusLoadError`; optional read-through cache keyed by URL and version); `uv run pytest tests/rag -q`: `61 passed, 1 deselected, 4 warnings, 2 errors in 16.64s` (the 2 errors are the CLI tests, next).
- **27.11.2026 20:58** Development agent: `#184` closed; red unit tests for `load_corpus` (`uv run pytest tests/rag/test_loader_unit.py -q`: `7 failed in 1.67s`).
- **27.11.2026 20:57** Development agent: migration `0012_corpus.py` (`down_revision = "0011"`; lane A also writes a `0012`, the coordinator re-chains the second) and the ORM block `MKC-49` at the end of `mkc/db/models.py` (own `Vector` type, no new dependency). `uv run pytest tests/rag/test_corpus_orm_unit.py tests/rag/test_corpus_tables.py tests/db -q -W error::sqlalchemy.exc.SAWarning`: `30 passed in 16.81s`.
- **27.11.2026 20:55** Development agent: `#182` closed; red ORM tests for the corpus tables (`uv run pytest tests/rag/test_corpus_orm_unit.py -q`: `2 errors in 1.02s`, `relation "chunk" does not exist`).
- **27.11.2026 20:54** Development agent: ADR 004 amendment and decision 71 (embedding model `qwen/qwen3-embedding-8b`, 1024 dims, $0.01 per million tokens; to be confirmed by the user); `uv run pytest tests/rag/test_embedding_model.py -q`: `2 passed in 0.03s`.
- **27.11.2026 20:54** Development agent: `EmbeddingClient` (end of `mkc/models/client.py`), `build_embed_call` (end of `mkc/models/providers.py`), the price in `models.yaml`, `mkc.rag.embeddings` (`EMBEDDING` = `qwen/qwen3-embedding-8b`, 1024 dims). `uv run pytest tests/rag/test_embeddings_unit.py tests/rag/test_embedding_model.py tests/models -q`: `170 passed, 12 deselected, 4 warnings in 14.66s`. Live test `tests/rag/test_embeddings_live.py` run twice: 20:52 `1 passed` (cost not printed), 20:53 `tokens 72, cost 0.00000066 EUR`, `1 passed`.
- **27.11.2026 20:49** Development agent: `#181` closed. Live probes of OpenRouter embeddings (ZDR routing; costs in USD as OpenRouter reported them): 20:46 `baai/bge-m3` refused by the workspace guardrail (`0 endpoints out of 2 requested are available matching your guardrail restrictions`, no charge); 20:46 `qwen/qwen3-embedding-8b` OK, 4096 dims, cost `4e-08`; `mistralai/mistral-embed-2312` OK, 1024 dims, cost `5e-07`; `google/gemini-embedding-001` and `intfloat/multilingual-e5-large` refused by the guardrail; 20:47 Qwen3 with `dimensions=1024` on Nebius and DeepInfra: 4 calls, 1024 dims, normalised, cost `7.7e-07` each; 20:47 cross-provider check, 2 calls, cost `2.7e-07` each, cosine Nebius vs DeepInfra `0.9942`. Red unit tests for the embedding layer (`uv run pytest tests/rag/test_embeddings_unit.py -q`: `13 failed in 21.85s`).
- **27.11.2026 20:46** Development agent: `mkc.rag.chunking` (`law` layout: one chunk per Absatz, ref `§ 14a Abs. 1`; `sections` layout for decisions and operator texts); `uv run pytest tests/rag/test_chunking_unit.py tests/rag/test_chunking.py -q`: `12 passed in 0.04s`.
- **27.11.2026 20:44** Development agent: `#179` closed; red unit tests for chunking (`uv run pytest tests/rag/test_chunking_unit.py -q`: `10 failed in 0.26s`).
- **27.11.2026 20:43** Development agent: `mkc.rag.sources` and `backend/data/corpus_sources.yaml` (6 sources; every URL fetched once on 27.11.2026, HTTP 200; no text stored); `uv run pytest tests/rag/test_sources_unit.py tests/rag/test_corpus_sources.py -q`: `18 passed in 0.57s`.
- **27.11.2026 20:42** Development agent: sub-issues `#179`, `#181`, `#182`, `#184`, `#185`, `#186` created, assigned, on the board and linked to `#49`; red unit tests for `load_sources` (`uv run pytest tests/rag/test_sources_unit.py -q`: `14 failed in 0.45s`).
- **27.11.2026 20:30** Test agent: added `test_corpus_tables_downgrade_and_upgrade_again`; `uv run pytest tests/rag -q`: `10 failed, 7 errors in 4.77s`. The 5 red commits `97c18ea`..`969ebf0` (20:28) were pushed to `origin/mkc-49-corpus-loader`.
- **27.11.2026 20:27** Test agent: red acceptance tests for MKC-49 written in `backend/tests/rag/`; `uv run pytest tests/rag -q`: `9 failed, 7 errors in 4.31s` (no `mkc.rag`, no tables, no `corpus_sources.yaml`).
