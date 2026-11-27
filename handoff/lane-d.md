# Lane D: RAG

**Last updated:** 27.11.2026, 23:19

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-49` (merged, PR #198) → `MKC-50` → `MKC-51` (MKC-51 waits on lane B's MKC-38)
- **Branch and worktree:** `mkc-50-hybrid-retriever` (cut from `main` `d7fad1e`)
- **Owns:** `backend/src/mkc/rag/`, the corpus loader, the retriever, `backend/tests/rag/`, `backend/data/corpus_sources.yaml`, `EmbeddingClient` at the end of `mkc/models/client.py`
- **Decision numbers:** 79–81 (wave 2; 71–73 of wave 1: 71 and 72 used, 73 free)

## In progress

- `MKC-50` (`#50`), Hybrid retriever: the test agent's red acceptance tests are in `backend/tests/rag/` (see the log for the commits). Next: the development agent builds against them.
- The coordinator assigned a sub-issue "MKC-49 review findings" (wave 1 review of PR #198, findings 1 to 5 and the open points) to MKC-50. The development agent creates it on the board with the other sub-issues.
- Migration: MKC-49's is `0013_corpus.py` (`down_revision = "0012"`; the coordinator re-chained it at the merge). A new migration in MKC-50, if any, uses `down_revision = "0013"`.

### Pinned interfaces (MKC-50)

The tests import these; module paths and names are fixed, internals are free.

- `mkc.rag.retriever`
  - `RRF_K = 60`; `rrf_merge(rankings: Sequence[Sequence[int]], *, rrf_k: int = RRF_K) -> list[tuple[int, float]]`: score = sum of `1 / (rrf_k + rank)` over the rankings, ranks from 1, a chunk missing from a ranking gets nothing from it; sorted by score, highest first; **ties go to the lower chunk id**.
  - `MAX_K` and `CANDIDATES` (ints): `10 <= MAX_K <= CANDIDATES`; each side (keyword, vector) looks at up to `CANDIDATES` chunks before fusion.
  - `RetrievedChunk(chunk_id: int, score: float, source_ref: str, text: str)`: a frozen dataclass; `text` is the stored chunk text unchanged; `score` is the RRF score.
  - The untrusted mark: `PASSAGE_OPEN = "<retrieved_passage>"`, `PASSAGE_CLOSE = "</retrieved_passage>"`, `RetrievedChunk.as_prompt_data() -> str` = open tag + JSON `{"chunk_id", "source_ref", "text"}` + close tag. The JSON has no `<` or `>` (escaped, as in `mkc/harness/prompts.py`) and keeps umlauts and `§` as they are (`ensure_ascii=False`). The open tag has no attributes. A prompt must use this, never `text` directly (MKC-51).
  - `retrieve(query: str, k: int = 5, *, session: Session, embedder, tracers: Sequence[Callable[[RetrievalTrace], None]] = (), scope: TraceScope | None = None) -> list[RetrievedChunk]`
    - at most `k` results, sorted by score (highest first), unique chunk ids; an empty corpus gives `[]`
    - keyword side: Postgres `german` full-text search on `chunk.tsv`; the query is plain text (`&`, `|`, `!`, `:`, `'`, `<->`, `*` never raise)
    - vector side: the query vector against `chunk.embedding`
    - `ValueError` for `k < 1`, `k > MAX_K` or a blank query, before the embedder is called
    - the query is embedded once with `embedder.embed_query(query)`, the raw query; `embed` is never called by the retriever
  - `RetrievalTrace` (dataclass): at least `latency_ms: int` (the whole call, embedding included), `k`, `query_chars`, `returned`, `keyword_hits`, `vector_hits`, `error: str | None` (`"<Class>: …"`), `scope: TraceScope | None`. **No query text** (no field named `query` or `text`, no string field holds the query). One trace per `retrieve` call, also when it fails (then `returned == 0` and the error is raised again). A hook that raises is logged and skipped; the next hook still gets the trace.
- `mkc.rag.embeddings.ProviderEmbedder.embed_query(query: str) -> list[float]`: sends one text that starts with `Instruct: `, contains `\nQuery:` and ends with the query (Qwen3-Embedding's query format, decision 71); adds tokens and cost like `embed`. `embed` still sends passages exactly as stored.
- `mkc.models.client` (lane D's block at the end)
  - `EmbedTrace` (dataclass): `model_id`, `mode`, `texts: int` (how many), `input_tokens`, `cost_eur`, `latency_ms: int`, `error: str | None` (starts with the error's class name), `scope: TraceScope | None`. No text of the input anywhere in it.
  - `EmbeddingClient(..., tracers: Sequence[Callable[[EmbedTrace], None]] = ())` and `EmbeddingClient.from_settings(..., tracers=...)`, kept as `_tracers` (a list). `embed(texts, *, scope=None)`: **one trace per `embed()` call** (not per batch), with the reply's tokens, cost and latency; on a provider error one trace with `error` set, then the error is raised. A hook that raises never breaks the call.
- MKC-49 review findings (tests, not interfaces):
  - fetcher: an `http://` URL is refused before any request; an https → http redirect on the same host is refused before the http request.
  - `law` layout: a line starting with `§ <n>` opens a paragraph only at the start of the text or after a blank line (the fetcher's layout); elsewhere it is body text of the current Absatz. Proven on plain text and through `law_text(html)`.
  - `law` layout: a blank line inside an Absatz does not split it, even past `MAX_CHUNK_CHARS` (decision 72).
  - loader: **any** cache folder inside the repo is refused (`CorpusLicenceError`, before any fetch), official-only sources included. The MKC-49 test `test_an_official_only_cache_inside_the_repo_is_allowed` is replaced by `test_an_official_only_cache_inside_the_repo_is_refused_too` (the test agent's change, reason in its docstring).
  - image: the runtime stage copies `data/corpus_sources.yaml` to `/app/data/corpus_sources.yaml` (one `COPY` line after the `operators.yaml` line; granted by the coordinator).

### Shared-file rules for the development agent

- `mkc/observability/`: append only (a new helper at the end of a module). The tests do not require a `run_log` bridge (see the assumptions).
- `backend/Dockerfile`: only the one `COPY data/corpus_sources.yaml ./data/corpus_sources.yaml` line after the `operators.yaml` line.
- A new dependency is named in the PR; the coordinator runs `uv lock`.
- Live calls: at most €0.50 for live query embeddings, logged here.
- Stale wording to fix (no tests): this file's MKC-49 lines naming migration 0012 (now 0013, history stays); the `DEFAULT_SOURCES_PATH` docstring ("the image carries `backend/data/`"); `EMBED_BATCH_SIZE` ("at most about 1,000 tokens"; decision 72 allows about 2,000); "the PDF library comes with MKC-21" in `fetch.py`, the runbook and the status doc (it is on `main`). Using `pdfplumber` for the PDF sources is optional.

### Test agent's assumptions (for the coordinator to confirm)

1. **Untrusted mark:** a `<retrieved_passage>` wrapper around escaped JSON, as `mkc/harness/prompts.py` does for tool results; the JSON holds `source_ref` too, because it is read from the document.
2. **Query instruction:** lives in the embedder (`embed_query`), as MKC-49 put any passage prefix in the embedder; `retrieve` passes the raw query.
3. **Trace at hook level:** `RetrievalTrace` and `EmbedTrace` are hooks like `CallTrace`. How they reach `run_log` and Langfuse is open: `TraceRecord.kind` is a closed `Literal`, `run_log.run_id` is not nullable, and `Tracer` only takes new code at a module's end. A retrieval with no run (MKC-51's "ask why") has no `run_log` row to join. Needs a coordinator decision.
4. **Score:** the RRF score itself (not normalised); ties to the lower chunk id.
5. **An official-only cache inside the repo is refused** (review finding 5): one simple rule, nothing needs a cache in the repo, and only `.cache/` is git-ignored.
6. **The image default path:** `DEFAULT_SOURCES_PATH` uses `parents[3]` of the installed package, which does not exist in the image. The tests pin only the shipped file; making `mkc corpus load` find it without `--sources` needs an `ENV` line or a setting (not granted). Needs a coordinator decision.

### Not covered by red tests

- The exact keyword ranking function (`ts_rank` or other) and the tsquery builder (`plainto_tsquery` or `websearch_to_tsquery`); the tests need only that "§ 14a" and "BK6-22-300" match.
- The distance operator (cosine, L2 or inner product): the test vectors are unit vectors, so all three agree.
- A live query embedding (`@pytest.mark.live`): optional for the development agent.
- An index for the vector side (HNSW or IVFFlat): no test; the corpus is small.
- The injection guard on retrieved text (MKC-46/51) and the prompt layer that uses `as_prompt_data()` (MKC-51).

## Next steps

1. The development agent: create the sub-issues (incl. "MKC-49 review findings"), build `mkc.rag.retriever`, `embed_query`, the `EmbeddingClient` hooks and the findings, make the red tests green, then `bash scripts/pre_pr.sh` and the PR.
2. The test agent: mutation pass on the development agent's code.
3. Open for the coordinator: assumptions 3 and 6 above.

## Recent log

- **27.11.2026 23:19** Test agent: tests for the MKC-49 review findings (PR #198). `uv run pytest tests/rag/test_fetch_unit.py tests/rag/test_chunking_unit.py tests/rag/test_loader_unit.py tests/rag/test_image_unit.py -q`: `5 failed, 36 passed in 1.50s`. Red (5): the three `§`-body-line tests (finding 2), `test_an_official_only_cache_inside_the_repo_is_refused_too` (finding 5; replaces the MKC-49 test that allowed it) and `test_the_image_ships_corpus_sources_yaml`. Green today, proven by mutants applied and restored by hand: the https tests (finding 1; scheme check removed: `2 failed, 13 passed`) and the blank-line test (finding 4; law blank lines kept: `4 failed, 13 passed` in `test_chunking_unit.py`, the new blank-line test among them).
- **27.11.2026 23:19** Test agent: red tests for the `EmbeddingClient` hooks (`EmbedTrace`, one per `embed()` call, also on error, never the texts) and `ProviderEmbedder.embed_query` (Qwen3's `Instruct: …\nQuery:…` format) in `tests/rag/test_embedding_trace_unit.py`; `uv run pytest tests/rag/test_embedding_trace_unit.py -q`: `6 failed, 1 passed in 5.35s` (`test_passages_are_still_embedded_as_stored` is green already: it guards the passage side).
- **27.11.2026 23:19** Test agent: red tests for `retrieve` on the test database (`tests/rag/test_retriever.py`: `test_paragraph_reference_found_by_keyword`, "BK6-22-300", ordering, `k` bounds, blank query, empty corpus, the RRF score, and `test_latency_per_query_logged_in_the_trace` with `RetrievalTrace`); hand-made unit vectors put both `§ 14a` chunks last on the vector side. `uv run pytest tests/rag/test_retriever.py -q`: `17 failed in 2.57s` (no `mkc.rag.retriever` yet). The commit is over 200 lines (one test module with its corpus fixture).
- **27.11.2026 23:19** Test agent: red tests for reciprocal rank fusion (`RRF_K = 60`, ties to the lower chunk id) and the untrusted mark (`RetrievedChunk.as_prompt_data()`) in `tests/rag/test_retriever_unit.py`; `uv run pytest tests/rag/test_retriever_unit.py -q`: `9 failed in 0.24s` (no `mkc.rag.retriever` yet).
- **27.11.2026 23:17** Test agent: lane file rewritten for MKC-50 (header, pinned interfaces, assumptions, what the red tests leave open); decision numbers 79–81.
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
