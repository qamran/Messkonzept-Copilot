# Lane A: Extraction

**Last updated:** 27.11.2026, 20:49

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-21` → `MKC-22` → `MKC-23` → `MKC-25` → `MKC-26` → `MKC-28` → `MKC-29` → `MKC-30`
- **Branch and worktree:** `mkc-21-fetch-segment`
- **Owns:** `mkc/extraction/`, the item tools in `mkc/harness/registry.py`, `backend/data/operators.yaml`
- **Decision numbers:** 62–64

## In progress

- `MKC-21` (`#21`): the test agent's red acceptance tests are in `backend/tests/extraction/`, in red commits `b18f652` to `c9202aa` (`git diff c9202aa` shows any later change to them). The development agent is building it.
- Sub-issues (all assigned to `qamran`, on the board, linked to #21):
  - `MKC-21.1` (#187): `operator` and `source_document` tables, `operators.yaml`, the YAML in the image
  - `MKC-21.2` (#188): `fetch_document` with the allow-list and editions
  - `MKC-21.3` (#189): Berlin segmentation
  - `MKC-21.4` (#190): Supabase Storage `BlobStore`
  - `MKC-21.5` (#191): run operations, `mkc run start --operator`, live run, docs
- Real Berlin layout (studied 27.11.2026 on the September 2026 edition): a concept page opens with `<number> <title>` (`1 Volleinspeisung`, `4.1 Überschusseinspeisung …`) on the first line of the main column, not `Messkonzept <n>`. A sidebar at x ≈ 461 pt repeats `Messkonzepte`, `Seite/Umfang`, `n/33`. Pages 4, 5 and 7 are tables whose rows start with concept numbers. The synthetic PDF in `conftest.py` changes to this layout (reason in the PR).

### Pinned interfaces (the development agent follows these)

- `mkc/extraction/__init__.py`: the package.
- `mkc/extraction/operators.py`:
  - `OperatorConfig(id, name, voltage_level, url, allowed_hosts: tuple[str, ...])`, built by keyword.
  - `load_operators() -> dict[str, OperatorConfig]`: reads the content of `backend/data/operators.yaml`. The Dockerfile copies only `src`, `alembic.ini` and `migrations`, so the worker image also needs the YAML (as `lbs_structures.yaml` will).
- `backend/data/operators.yaml`: a top-level `operators:` list; each entry has `id`, `name`, `voltage_level`, `url` (https), `allowed_hosts`. Ids: `stromnetz-berlin` (as in `test_registry.py`) and `sachsennetze`.
- `mkc/extraction/fetch.py`:
  - `FetchResponse(url, content)`: `url` is the final URL after redirects.
  - `http_get(url) -> FetchResponse`: the real getter (used only by the live test).
  - `is_allowed_url(url, allowed_hosts) -> bool`: https only, exact host match (case-insensitive), no userinfo.
  - `DisallowedUrl` (exception): raised before any request or write.
  - `fetch_document(operator_id, *, sessions, store, get=http_get, operators=None) -> SourceDocument`. `sessions` is a `sessionmaker`; `store` is a `mkc.harness.blobs.BlobStore`; `operators=None` means `load_operators()`.
  - `SourceDocument` (detached value): `operator_id`, `url`, `sha256` (hex), `fetched_at`, `page_count`, `edition`, `new_edition`.
- `mkc/extraction/segment.py`:
  - `ConceptRegion(page, bbox, number_hint)`: `page` is 1-based; `bbox` is `(x0, y0, x1, y1)` in PDF points inside the page; `number_hint` is `str | None`. Regions compare by value.
  - `segment_document(doc, *, store) -> list[ConceptRegion]`: reads the PDF from `store` by `blob:sha256:<doc.sha256>` and picks the segmenter by `doc.operator_id`.
- `mkc/extraction/storage.py`: `LOCAL_CACHE_DIR`, a folder inside the repo where a local run may cache PDFs; every file in it must be gitignored (`backend/.cache/...` already is).
- Migration `0012` (`down_revision = "0011"`):
  - Table `operator`: at least `id`, `name`, `voltage_level`, `url`, `edition`.
  - Table `source_document`: at least `id`, `operator_id` (FK to `operator`), `url`, `sha256`, `fetched_at`, `page_count`, `edition`, and a unique constraint on `(operator_id, edition)`.
  - No `bytea` column in either table. The PDF never goes into the Postgres `blob` table.
- `fetch_document` upserts the `operator` row from its config and sets `operator.edition` to the latest edition.

### Assumptions (the test agent's, for the coordinator to confirm)

1. The first fetch is edition 1 with `new_edition = False`. A re-fetch of the same bytes adds no row and keeps `new_edition = False`. A new hash adds edition n+1 with `new_edition = True`.
2. Not tested yet: what happens when the hash goes back to an older edition's hash. The tables do not require `(operator_id, sha256)` to be unique, so the development agent may choose either behaviour and should record it as a decision (62–64).
3. A Berlin concept page starts with the heading `Messkonzept <n>` (for example `1`, `2a`). The cover, contents and appendix pages are not concepts. A body line that cites another concept is not a heading. The real layout is unknown until the live run. If it differs, the development agent changes the synthetic PDF in `conftest.py` and gives the reason in the PR body.
4. "Records from two editions never mixed" is tested as follows: each edition keeps its own bytes in Storage, segments to its own concepts, and has its own `sha256`. Drafts are already keyed by `(document_hash, concept_key)` (MKC-16.5).

### Not covered by red tests (the development agent's items)

- The real Supabase Storage `BlobStore` (decision 56 says MKC-21 adds it). It has no acceptance test here. The development agent writes its tests first, with no network access.
- Wiring `fetch_document` and `segment_document` into `RUN_OPERATIONS` in `mkc/harness/registry.py`. `segment_document` there takes `document_hash`, so the development agent decides how a hash maps to a `source_document` row. `test_placeholders_return_not_implemented` must then drop those two tools, with the reason given in the PR.
- The live test's `EXPECTED_BERLIN_CONCEPTS` is `None` until the first verified live run, which needs the coordinator's go.
- Adding the PDF library (pdfplumber or PyMuPDF, design section 4) to `pyproject.toml`, and saying so in the PR. The synthetic PDF parses with both.

## Next steps

1. Development agent: build `mkc/extraction/` and migration `0012` against the red tests, test-first and in atomic commits.
2. Test agent: run the mutation pass on the development agent's code.

## Recent log

- **27.11.2026 20:49** Development agent: the synthetic Berlin PDF now has the real layout (`<n> <title>` heading, sidebar, appendix table rows); red unit tests for the heading rule (`test_segment_rules.py`); `pytest tests/extraction`: 16 failed, 40 passed, 1 deselected.

- **27.11.2026 20:48** Development agent: `fetch_document`, `http_get` (https-only redirects, at most 5), `is_allowed_url`, the edition rules and `LOCAL_CACHE_DIR` (`backend/.cache/blobs`); `test_fetch_rules.py test_fetch.py test_storage_only.py`: 27 passed.

- **27.11.2026 20:46** Development agent: red unit tests for the edition rules (A, B, A gives edition 3), non-PDF responses, unknown operators and `http_get` redirects (`test_fetch_rules.py`: 9 failed).

- **27.11.2026 20:46** Development agent: dependencies `pdfplumber` (MIT; brings `pdfminer.six`, `pypdfium2`, `pillow`) and `httpx` (was only transitive) added with `uv add`.

- **27.11.2026 20:45** Development agent: `operators.yaml` (Berlin September 2026 edition; SachsenNetze `Standard-Messkonzepte.pdf` from its download centre), `load_operators`, `MKC_OPERATORS_FILE`, the YAML in the image, `.cache` kept out of the image; `test_operators_file.py test_operators_yaml.py test_config.py`: 35 passed.

- **27.11.2026 20:42** Development agent: migration `0012` (`operator`, `source_document`) and the models; `tests/extraction/test_source_tables.py tests/db`: 30 passed.

- **27.11.2026 20:42** Development agent: sub-issues #187 to #191 created and linked; red unit tests for where `load_operators` finds the YAML and for the image shipping it (`test_operators_file.py`: 6 failed).

- **27.11.2026 20:33** Test agent: commit `c9202aa`. The Storage-only test now also checks that `LOCAL_CACHE_DIR` is unchanged, and the `OPERATORS_YAML` path pin is dropped. Full suite (`uv run pytest -q`): `28 failed, 662 passed, 1 skipped, 13 deselected in 178.42s`; the 28 failures are the extraction tests.

- **27.11.2026 20:28** Test agent: red acceptance tests in `backend/tests/extraction/`. `uv run pytest tests/extraction -q`: `28 failed, 1 deselected` (22 × `No module named 'mkc.extraction'`, 2 × missing `operators.yaml`, 4 × missing tables). `ruff check` and `ruff format --check` pass.
