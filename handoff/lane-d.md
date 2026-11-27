# Lane D: RAG

**Last updated:** 27.11.2026, 20:27

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-49` → `MKC-50` → `MKC-51` (MKC-51 waits on lane B's MKC-38)
- **Branch and worktree:** `mkc-49-corpus-loader`
- **Owns:** `backend/src/mkc/rag/`, the corpus loader, the retriever, `backend/tests/rag/`, `backend/data/corpus_sources.yaml`
- **Decision numbers:** 71–73

## In progress

- `MKC-49` (`#49`): the test agent's red acceptance tests are in `backend/tests/rag/` (no sub-issues yet). The development agent has not started.

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
- `mkc.rag.embeddings`
  - `EMBEDDING`: the one config value, with `.model: str` and `.dim: int`. ADR 004 must name `EMBEDDING.model` (the ticket's success criterion).
  - An `Embedder` protocol: `embed(texts: Sequence[str]) -> list[list[float]]` (the fake also has `model` and `dim`).
- `mkc.rag.loader`
  - `load_corpus(session, sources, *, embedder, fetcher, cache_dir=None, repo_root=<this repo>)`; works inside the caller's transaction
  - `fetcher: Callable[[CorpusSource], str]` returns the source's plain text
  - `CorpusLicenceError`: raised when `cache_dir` (resolved) is inside `repo_root` and any source is `restricted`, **before anything is written**
  - Re-loading replaces a source's chunks (keyed by `source_id`); no duplicates
- `mkc.rag.cli`
  - `corpus_app` (Typer) with `load --sources PATH`; exit 0 on success, 2 on a bad sources file
  - `make_embedder(settings)` and `make_fetcher(settings)`: module-level factories the tests monkeypatch
- Tables (columns the tests read)
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
3. The tests cover §-structured law text only; how BNetzA decisions and operator texts are split into sections is the development agent's design.

## Next steps

1. The development agent builds `mkc/rag/`, the migration, `corpus_sources.yaml` and the ADR 004 entry until `uv run pytest tests/rag` is green.
2. The test agent then runs its mutation pass on `mkc/rag/` and reports the surviving mutants.

## Recent log

- **27.11.2026 20:27** Test agent: red acceptance tests for MKC-49 written in `backend/tests/rag/`; `uv run pytest tests/rag -q`: `9 failed, 7 errors in 4.31s` (no `mkc.rag`, no tables, no `corpus_sources.yaml`).
