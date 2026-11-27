# Lane D: RAG

**Last updated:** 27.11.2026, 21:56

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-49` → `MKC-50` → `MKC-51` (MKC-51 waits on lane B's MKC-38)
- **Branch and worktree:** `mkc-49-corpus-loader`
- **Owns:** `backend/src/mkc/rag/`, the corpus loader, the retriever, `backend/tests/rag/`, `backend/data/corpus_sources.yaml`
- **Decision numbers:** 71–73

## In progress

- `MKC-49` (`#49`): built; the six sub-issues are in Testing (they close with the PR's merge); PR #198 opened 27.11.2026 21:55 (GitHub `createdAt` 2026-11-27T20:55:20Z) at `5b39b61`; `#49` and the six sub-issues are in Testing. The test agent's red acceptance tests are in `backend/tests/rag/`.
- **Red commits:** `97c18ea` to `f515d26` "MKC-49: red test for the corpus tables' downgrade" (the test agent's last commit on this branch; diff the tests against it).
- **Sub-issues** (all assigned to `qamran`, on the board, linked to `#49`):
  - `MKC-49.1` (`#179`) corpus sources file: built (`4ce0e06`), Testing
  - `MKC-49.2` (`#181`) chunking per paragraph: built (`49462e7`), Testing
  - `MKC-49.3` (`#182`) embedding model through the provider layer: built (`97b760c`, `0871d20`), Testing
  - `MKC-49.4` (`#184`) corpus tables and migration 0012: built (`8f8117d`), Testing
  - `MKC-49.5` (`#185`) corpus loader with the licence guard: built (`46f818c`), Testing
  - `MKC-49.6` (`#186`) `mkc corpus load` and the HTTP fetcher: built (`5c5f50d`, `3e1c8aa`), Testing

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

1. Done 21:47: the test agent's mutation pass (98 tried, 95 killed, 3 survived); the 3 survivors have tests since `4db8f62`.
2. Done 21:55: PR #198 opened; `#49` and its sub-issues in Testing. Next, the coordinator starts the review once `gh pr checks` is green, updates the branch from `main` and re-chains migration `0012` if lane A merges first.
3. Open for the coordinator:
   - decision 71 confirmed by the user on 27.11.2026, with the research note `docs/271120262150-embedding-model-research.md`; the production key's guardrail was not checked
   - 4 of 6 sources are PDFs and refused until MKC-21's PDF library is in; the BK8-22/010-A file is an encrypted PDF (`/Encrypt` in its header) served from an `.html` URL; the `sections` chunker has only run on synthetic text
   - one operator text only (Stromnetz Berlin); no SachsenNetze URL was found in the repo
   - `EmbeddingClient` beside `ModelClient` is allowed by the user (the coordinator updates AGENTS.md); it has no tracers, and is live-only while the default mode is `replay`: MKC-50's query embeddings need a decision on tracing and on tests and evals
   - edits not at a file's end: the import lines of `providers.py`, the price line in `models.yaml`; the ORM block imports at the bottom with `noqa: E402` and registers `vector` in the PostgreSQL dialect's `ischema_names`
   - the backend image does not copy `backend/data/` (as for the LBS file), so `mkc corpus load` in the container needs `--sources`

## Recent log

- **27.11.2026 21:56** Development agent: `bash scripts/pre_pr.sh` exit 0 at `5b39b61` (`746 passed, 1 skipped, 13 deselected, 4 warnings in 95.73s`); pushed; PR #198 opened (createdAt `2026-11-27T20:55:20Z`), assigned to `qamran`; `#49`, `#179`, `#181`, `#182`, `#184`, `#185`, `#186` set to Testing on the board.
- **27.11.2026 21:51** Development agent: research note `docs/271120262150-embedding-model-research.md`, linked from ADR 004, decision 71 and the status doc; decision 71 marked confirmed by the user on 27.11.2026; decision 72 (chunk size) added.
- **27.11.2026 21:50** Development agent: the 3 survivors and the leftover-folder finding. New tests: a lettered Absatz `(2a)` gets `§ 14a Abs. 2a`; the section cap is 4000 characters; a long law Absatz stays whole (decision 72); `REPO_ROOT` is the repo root; the CLI cache test cleans up in `finally`. `uv run pytest tests/rag -q`: `84 passed, 1 deselected, 4 warnings in 9.66s`. Each survivor re-applied by hand and restored: `(\d+)` → `1 failed, 12 passed`; `MAX_CHUNK_CHARS = 40` → `1 failed, 13 passed`; `parents[5]` → `1 failed, 69 passed` (all with `-x`).
- **27.11.2026 21:47** Test agent: mutation pass on `d4de5fd`. One mutant at a time, each restored before the next; none committed. Each ran `uv run pytest tests/rag tests/models -q -x` (baseline `235 passed, 13 deselected, 4 warnings in 21.83s`). Scope: `mkc/rag/` (sources, chunking, embeddings, loader, fetch, cli), the embedding code in `mkc/models/client.py` and `providers.py`, the MKC-49 block of `mkc/db/models.py`, and migration `0012_corpus.py`. Result: **98 tried, 95 killed, 3 survived** (all 98 applied; 0 not applied). Survivors:
  1. `backend/src/mkc/rag/chunking.py:31` `_ABSATZ` `(\d+[a-z]?)` → `(\d+)`. A lettered Absatz such as `(2a)` no longer opens its own chunk: it is merged into the Absatz before it and gets that Absatz's `source_ref`. No test has a lettered Absatz. Real laws have them, so a unit test with `(1a)` would kill it.
  2. `backend/src/mkc/rag/chunking.py:24` `MAX_CHUNK_CHARS = 4000` → `40`. No test splits a long block. Law blocks have no inner blank lines, so the cap never applies to them. This matches the development agent's 21:03 log entry: the largest real MsbG chunk was 7836 characters, which is over the 4000 cap.
  3. `backend/src/mkc/rag/loader.py:24` `REPO_ROOT` `parents[4]` → `parents[5]` (the folder above the repo). The guard still refuses every cache inside the repo but is too broad. No test checks `REPO_ROOT == <repo root>`.
  Finding (not a mutant): `tests/rag/test_cli_unit.py:57` `test_a_cache_inside_the_repo_is_refused` points `--cache-dir` at `backend/.mkc49-cli-cache-test` in the real repo and has no `finally` cleanup. Under the guard-removed mutants it wrote the 2 synthetic texts there, and the test agent deleted the folder (the worktree is clean again). A `try/finally: shutil.rmtree(...)` would stop a broken guard from leaving files in the repo.
- **27.11.2026 21:20** Development agent: sub-issues `#179`–`#186` reopened and set to Testing (sub-issues close with the PR's merge, as `#169`–`#173` did with PR `#174`). ADR 004 table: every zero-data-retention embedding model listed (exact id match of OpenRouter's two lists), unverified dimensions dropped. Check on the saved MsbG page: 220 chunk refs, all unique; the 79 paragraphs in chunk order match the page's `jnenbez` list. `refs/original` of `filter-branch` deleted.
- **27.11.2026 21:13** Development agent: `bash scripts/pre_pr.sh` exit 0 at `1d54b78` (`742 passed, 1 skipped, 13 deselected, 4 warnings in 136.96s`; commits over 200 lines: `d526f60` 232, `97b760c` 265, `ecd4252` 241). The test agent's red tests are unchanged since `f515d26` (`git diff --stat f515d26 HEAD` on them is empty).
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
