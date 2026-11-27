# Lane A: Extraction

**Last updated:** 27.11.2026, 21:19

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

1. Development agent: `bash scripts/pre_pr.sh`, push the branch, report to the coordinator (no PR yet).
2. Test agent: run the mutation pass on the development agent's code (`mkc/extraction/`, `mkc/harness/storage.py`, the `blobs` path in `loop.py`, `--operator` in `cli.py`).
3. Development agent: open the PR when the coordinator says so. Changes to the test agent's tests, with reasons: `conftest.py` (`berlin_pages` in the real layout, `Side` sidebar lines in `make_pdf`), the docstring of `test_segment.py`, `EXPECTED_BERLIN_CONCEPTS = 26` in `test_live_berlin.py`.
4. Admin, before the deploy: the five `MKC_STORAGE_*` values into `mkc-secrets` (runbook "Fetch and segment").
5. Decisions taken for the test agent's open assumptions: 1 confirmed; 2 (a return to an older hash) is a new edition (decision 62); 3 replaced by the real layout (decision 64); 4 confirmed.

## Recent log

- **27.11.2026 21:19** Development agent: fetches disclosed: besides the live tests (Berlin twice in `test_live_berlin.py`, once in `test_live_storage.py`), the Berlin PDF was downloaded once with `curl` into a scratch folder outside the repo to study the layout (now deleted), and sachsen-netze.de was read for the catalogue link (two HTML pages, and the PDF once to `/dev/null` to check the status and type). Gitleaks over the branch (`pre-commit run gitleaks --from-ref origin/main --to-ref HEAD`): Passed.

- **27.11.2026 21:19** Development agent: regions keep drawings that start in the main column whole (page 27: x1 460.65, still left of the sidebar at 460.8; the other 25 pages unchanged); `pytest tests/extraction`: 65 passed, 2 deselected. The SachsenNetze entry is marked unverified for MKC-27 (`operators.yaml` comment, decision 62).

- **27.11.2026 21:19** Development agent: red test: a drawing that starts in the main column but reaches past 75 % (page 27, to 461 pt) must stay whole in the region; with the old rule `test_segment_rules.py`: 1 failed, 13 passed.

- **27.11.2026 21:13** Development agent: `bash scripts/pre_pr.sh` at `89ec4d1`: exit 0, `741 passed, 1 skipped, 14 deselected in 143.46s`, "pre-PR gate: all steps passed"; commits over 200 lines: `419f6fc` (209), `e8ff7a8` (269). Every commit's `Refs:` line reads `qamran/`. Branch pushed; no PR yet (the coordinator runs the mutation pass first).

- **27.11.2026 21:10** Development agent: first `scripts/pre_pr.sh` run: exit 1 on `ruff check` (import order in `test_run_operations.py`, sorted while `mkc.extraction.operations` did not exist yet); pytest in that run: `741 passed, 1 skipped, 14 deselected in 134.66s`. Fixed with `ruff check --fix`. `pip-audit` (CI's command): `No known vulnerabilities found`.

- **27.11.2026 21:07** Development agent: docs: decisions 62 (editions), 63 (Storage), 64 (segmentation and run start) in design section 18, decision 56 (1) marked done, ADR 003 amendment, status doc line for MKC-21, runbook section "Fetch and segment" and inventory rows, backlog "As built". All `scripts/check_*.py` pass; markdownlint on the six changed files: 0 errors.

- **27.11.2026 21:04** Development agent: `DocumentOps` makes `fetch_document` and `segment_document` real in `default_registry(documents=...)` (placeholders without it, so `test_placeholders_return_not_implemented` is unchanged); `document_by_hash`; `mkc run start --operator <id>` fetches and segments inside the run's transaction and queues one item per concept (concept key = the number). `pytest tests/extraction tests/harness/test_registry.py tests/harness/test_tools.py tests/test_cli.py`: passed.

- **27.11.2026 21:01** Development agent: red tests for the run operations in the registry (`DocumentOps`), `document_by_hash` and `mkc run start --operator` (`test_run_operations.py`: 6 failed, 2 errors).

- **27.11.2026 21:00** Development agent: large turn results go through `blobs` (`run_item`, `process_run`, `_Ctx`, `load_resume_context`): Storage first, the `blob` table as fallback for old refs; the executor builds the store from the Storage settings. `pytest tests/harness tests/worker`: 312 passed, 1 skipped.

- **27.11.2026 20:55** Development agent: red tests for large turn results through the configured store, old `blob`-table refs on resume, and the executor's store from settings (`test_resume_storage.py`: 3 failed).

- **27.11.2026 20:54** Development agent: `mkc.harness.storage`: `StorageBlobStore` (S3 protocol, SigV4 by hand, object key `sha256/<hex>`), `LayeredBlobStore`, `FileBlobStore`, `storage_from_settings` and the five `MKC_STORAGE_*` settings; `test_storage.py test_config.py`: passed. Live write into `mkc-storage` (coordinator's go): 20:53:51 to 20:54:03, `tests/extraction/test_live_storage.py`: `1 passed in 8.26s` (Berlin PDF `4e12c90f…29a18` put, read back with the same hash, 26 regions; a missing object answers 404, read as `KeyError`). Only the `MKC_STORAGE_*` variables were exported, so the test database stayed local.

- **27.11.2026 20:52** Development agent: red unit tests for the Storage `BlobStore` (SigV4 vectors made with botocore in a scratch environment, a fake bucket over `httpx.MockTransport`, the layered and file stores, the settings): `tests/harness/test_storage.py`: 12 failed.

- **27.11.2026 20:51** Development agent: live Berlin run (`uv run pytest -m live tests/extraction/test_live_berlin.py`, in-memory store, no model calls): 20:50:56 the first run reported `26 regions`, hints 1 … 12, sha256 `4e12c90faeb35383dafe86f9ae55ddad220dea50d827167f009d22fe27b29a18` (the same hash as the MKC-12 plan). Checked by hand against the contents on page 2 (26 concepts, pages 8 to 33, one page each). `EXPECTED_BERLIN_CONCEPTS = 26`; the second run at 20:51:21: `1 passed in 6.49s`.

- **27.11.2026 20:50** Development agent: `segment_document` and `segment_berlin` (first main-column line `<n> <title>`, sidebar left out, bbox top-left origin); `pytest tests/extraction`: 56 passed, 1 deselected. On the scratch copy of the September 2026 PDF it finds 26 regions on pages 8 to 33, the same 26 numbers and pages as the contents on page 2.

- **27.11.2026 20:49** Development agent: the synthetic Berlin PDF now has the real layout (`<n> <title>` heading, sidebar, appendix table rows); red unit tests for the heading rule (`test_segment_rules.py`); `pytest tests/extraction`: 16 failed, 40 passed, 1 deselected.

- **27.11.2026 20:48** Development agent: `fetch_document`, `http_get` (https-only redirects, at most 5), `is_allowed_url`, the edition rules and `LOCAL_CACHE_DIR` (`backend/.cache/blobs`); `test_fetch_rules.py test_fetch.py test_storage_only.py`: 27 passed.

- **27.11.2026 20:46** Development agent: red unit tests for the edition rules (A, B, A gives edition 3), non-PDF responses, unknown operators and `http_get` redirects (`test_fetch_rules.py`: 9 failed).

- **27.11.2026 20:46** Development agent: dependencies `pdfplumber` (MIT; brings `pdfminer.six`, `pypdfium2`, `pillow`) and `httpx` (was only transitive) added with `uv add`.

- **27.11.2026 20:45** Development agent: `operators.yaml` (Berlin September 2026 edition; SachsenNetze `Standard-Messkonzepte.pdf` from its download centre), `load_operators`, `MKC_OPERATORS_FILE`, the YAML in the image, `.cache` kept out of the image; `test_operators_file.py test_operators_yaml.py test_config.py`: 35 passed.

- **27.11.2026 20:42** Development agent: migration `0012` (`operator`, `source_document`) and the models; `tests/extraction/test_source_tables.py tests/db`: 30 passed.

- **27.11.2026 20:42** Development agent: sub-issues #187 to #191 created and linked; red unit tests for where `load_operators` finds the YAML and for the image shipping it (`test_operators_file.py`: 6 failed).

- **27.11.2026 20:33** Test agent: commit `c9202aa`. The Storage-only test now also checks that `LOCAL_CACHE_DIR` is unchanged, and the `OPERATORS_YAML` path pin is dropped. Full suite (`uv run pytest -q`): `28 failed, 662 passed, 1 skipped, 13 deselected in 178.42s`; the 28 failures are the extraction tests.

- **27.11.2026 20:28** Test agent: red acceptance tests in `backend/tests/extraction/`. `uv run pytest tests/extraction -q`: `28 failed, 1 deselected` (22 × `No module named 'mkc.extraction'`, 2 × missing `operators.yaml`, 4 × missing tables). `ruff check` and `ruff format --check` pass.
