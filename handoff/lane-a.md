# Lane A: Extraction

**Last updated:** 27.11.2026, 23:18

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-21` → `MKC-22` → `MKC-23` → `MKC-25` → `MKC-26` → `MKC-28` → `MKC-29` → `MKC-30`
- **Branch and worktree:** `mkc-22-text-tables`
- **Owns:** `mkc/extraction/`, the item tools in `mkc/harness/registry.py`, `backend/data/operators.yaml`
- **Decision numbers:** 76–78 (wave 2; 62–64 are used by MKC-21)

## Done

- `MKC-21` (`#21`): merged with PR #197 (merge commit `2a841a2`). Its pinned interfaces, assumptions and mutation pass are in this file at `e40115b`.

## In progress

- `MKC-22` (`#22`, `In progress`, assigned to `qamran`): the test agent is writing the red acceptance tests in `backend/tests/extraction/` (and two in `tests/harness/`, `tests/reference/`). The development agent starts once they are pushed.
- Sub-issues: none yet; the development agent creates them, among them "fetch hardening" (the wave 1 review findings 1 to 4 and 7 on PR #197).

## Next steps

1. Test agent: finish and push the red tests; pin the interfaces below.
2. Development agent: sub-issues, then build MKC-22 test-first against the pinned interfaces.
3. Test agent: mutation pass on the development agent's code.

## Recent log

- **27.11.2026 23:18** Test agent: red tests `test_tables.py` (incl. `test_pdfplumber_rows_correct` and the naive baseline) and `test_text.py` (incl. `test_stated_lbs_parsed`): `13 failed, 4 passed in 0.54s` with `test_synthetic.py`; every failure is `No module named 'mkc.extraction.tables'`, `'...naive'` or `'...text'`.

- **27.11.2026 23:18** Test agent (MKC-22): synthetic documents in the Berlin layout (`tests/extraction/synthetic.py`; `layout_pdf` and `ruled_table` in `conftest.py`; `MemoryStore.gets`). Fixture checks `test_synthetic.py`: 4 passed. The layout was read once from the real Berlin PDF (sha256 `4e12c90f…29a18`), fetched with `curl` into a scratch folder outside the repo.

- **27.11.2026 21:55** Development agent: `bash scripts/pre_pr.sh` at `abfee85`: exit 0, `753 passed, 1 skipped, 14 deselected in 97.10s (0:01:37)`. PR #197 opened (createdAt 2026-11-27T20:54:19Z, 21:54:19 CET), head `abfee85`, assigned to `qamran`; #21 and #187 to #191 moved to `Testing`. This commit changes only this file.

- **27.11.2026 21:50** Development agent: the gate at `dfc03e4` failed on markdownlint in this file (no blank line before `## Next steps` after the mutation section); fixed. Pytest in that run: `753 passed, 1 skipped, 14 deselected in 96.55s`.

- **27.11.2026 21:48** Development agent: redirect hops written down as a known limit in decision 62 (5) and the runbook ("The allow-list"): hops off the list are requested, with a plain GET only; the final host decides. `check_runbook.py` passes; markdownlint 0 errors. #187 to #190 moved back to `In progress` until the PR exists.

- **27.11.2026 21:47** Development agent: mutation survivors 13, 14 and 17 killed: `test_run_operations.py` checks edition and `new_edition` across the registry and in the CLI output (`edition 2, a new edition`), the edition of `segment_document`'s result, and that `--operator` with a real `--items` file is refused with "exactly one" before any fetch; 11 passed, the three mutants fail it.

- **27.11.2026 21:46** Development agent: mutation survivors 3 and 7 killed: `test_fetch_rules.py` pins `MAX_REDIRECTS = 5` (5 hops followed, the 6th refused) and the final URL in the edition row; a new test shows redirect hops get a plain GET with no body, auth or cookie header. 12 passed; both mutants fail it.

- **27.11.2026 21:46** Development agent: mutation survivors 15 and 16 killed: `test_storage.py` checks each request's signature for its own method (against the botocore-checked `sigv4_headers`) and the PUT's `content-type`; 13 passed, both mutants fail it.

- **27.11.2026 21:45** Development agent: mutation survivors 18 to 20 killed: `tests/worker/test_executor_storage.py` (2 passed) sends large results through `process_run` and the executor, also on the turn that ends the item; each of the three mutants re-applied makes it fail.

- **27.11.2026 21:43** Test agent: mutation pass on `7427125`: 85 tried, 63 killed, 22 survived; two new acceptance tests (`6161098`) kill two survivors, leaving 20 (listed under "Mutation pass").

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
