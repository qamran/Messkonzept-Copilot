# Lane A: Extraction

**Last updated:** 28.11.2026, 11:20

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-21` → `MKC-22` → `MKC-23` → `MKC-25` → `MKC-26` → `MKC-28` → `MKC-29` → `MKC-30`
- **Branch and worktree:** `mkc-25-vision-check` (worktree `mkc-lanes/lane-a`, cut from `main` `47e110a`)
- **Owns:** `mkc/extraction/`, the item tools in `mkc/harness/registry.py`, `backend/data/operators.yaml`; for MKC-25 (coordinator grants, wave 4): `mkc/extraction/vision_check.py`, `mkc/harness/drafts.py`, `mkc/harness/loop.py`, `backend/data/go_no_go/`, the status doc section `## Go/no-go vision check (MKC-25)`, the backlog's MKC-25 entry, decisions 85–87 and, only if the user decides Berlin only, one line in design section 15. No migration in this ticket (ruling 11)
- **Decision numbers:** 85–87 (wave 4; 82–84 used by MKC-23, 76–78 by MKC-22, 62–64 by MKC-21)
- **Budget (MKC-25):** live vision calls €1.00 in total, retries included, public PDFs only; every call logged here with its printed cost. Spent so far: €0.00.

## Done

- `MKC-21` (`#21`): merged with PR #197 (merge commit `2a841a2`). Its pinned interfaces, assumptions and mutation pass are in this file at `e40115b`.
- `MKC-22` (`#22`): merged with PR #215 (merge commit `6d3aee9`). Its pinned interfaces, assumptions and mutation pass (15 survivors) are in this file at `502c30a`.
- `MKC-23` (`#23`): merged with PR #225 (merge commit `6208e97`). Its as-built notes, assumptions and mutation pass (9 survivors) are in this file at `47e110a`.

## In progress

- `MKC-25` (`#25`, go/no-go vision check): `In progress`; sub-issues MKC-25.1 (`#228`, `draft_locked`), MKC-25.2 (`#229`, the module), MKC-25.3 (`#230`, sheet and docs). The test agent's red tests are `304a81c` to `942bf3a` (unchanged). Done: the `draft_locked` fix, the module and CLI, the blank sheet, the docs that can be written now. Waiting: the user fills in the sheet; then the live run (EUR 1.00, the coordinator's go), the table, a recommendation and the user's decision.

### Red tests (MKC-25; test agent, 28.11.2026)

- `backend/tests/extraction/test_vision_check.py` (30 tests, `64d0eb2`) pins `mkc.extraction.vision_check`:
  - `load_truth(path) -> list[dict]`: YAML, top key `concepts:`, entries `{operator, concept, page, meters, components}`; `meters` a list of `{label, upstream}`, `components` a list of `{kind, attached_to}`; `null` means not filled in.
  - `compare(truth_entry, read) -> verdict` with bool attributes `meters`, `upstream`, `components`; ValueError for an unfilled entry.
  - `check_concepts(client, pdf, truth, *, dpi) -> list[(concept, verdict)]` in truth order: Berlin segmenter, `render_region`, one `ModelClient.vision` call per concept (role `extract_vision`); ValueError and no call on an unfilled sheet, a concept the segmenter does not find, or a page that disagrees with it.
  - `results_table(rows) -> str`: header `| concept | meters correct | upstream correct | components correct |`, cells `yes` / `no`.
  - `python -m mkc.extraction.vision_check --help` exits 0 and mentions the truth sheet.
  - The sheet `backend/data/go_no_go/truth.yaml`: only the top key `concepts`, 5 distinct entries, operator `stromnetz-berlin`, `concept` a quoted string, `page` an int, only the keys above, every string at most 40 characters, the file under 8,000 bytes.
- `backend/tests/test_check_go_no_go.py` (32 tests, on synthetic docs; only the repo tests read the real files) and `scripts/check_go_no_go.py` (`097de14`, `942bf3a`): the status doc section `## Go/no-go vision check (MKC-25)` with the table above (5 rows, the sheet's concepts, `yes` or `no`) and one line `**Decision:** go (the user, dd.MM.yyyy)` or `**Decision:** Berlin only (the user, dd.MM.yyyy)`; for Berlin only, a line in design section 15 naming `MKC-25` and `Berlin only`; for go, no such line. A `**Recommendation:**` line beside it is allowed. The script reads the sheet's `concept:` values by regex (stdlib only); two tests pin that it reads them as YAML does. Red: `test_the_repo_passes`, the table-agreement test and the repo-sheet test; the other 29 pass.
- `backend/tests/harness/test_draft_locked.py` (9 tests, `304a81c`): the PR #225 finding 1 probe (A pending, B saves `v2` (a direct `save_draft` call) and is set `failed`, the draft row then B's and the queue row still A's (both asserted), A approved or committed, C's save must be `draft_locked`), the variant where the decided item owns neither the draft row nor the queue row, and the probe through the loop (C fails with `draft_locked`): 6 red. Three guards are green now and must stay green: a failed saver does not lock while A waits; an approved item of another concept or another document does not lock.
- **CI consequence:** CI's `docs` job runs every `scripts/check_*.py`, so `check_go_no_go.py` is wired in by its name (no change to `ci.yml` or `pre_pr.sh`; `check_pre_pr.py` stays green). The `docs` job, the backend's `test_the_repo_passes` and so `scripts/pre_pr.sh` stay red on this branch until the user's results and decision are in.

### Assumptions (the coordinator's rulings, 28.11.2026: 1 to 10 and 12 confirmed; 11 confirmed with no snapshot and no migration, MKC-29 decides; 13 granted)

1. The module is `mkc.extraction.vision_check`, with the five names above; the rest is the development agent's.
2. Comparison sets: meters = labels; upstream = (label, upstream) pairs, a root meter's upstream `null`; components = (kind, attached_to) pairs. Both sides strip and case-fold; duplicates collapse. Other draft fields in the read (`purpose`, `directions`, `types`) are ignored.
3. A missing meter also makes upstream wrong (its pair is missing); the tests assert only `meters` there.
4. Unfilled truth: `meters` null or empty, `components` null, or a field missing. `components: []` is a filled answer (a single-meter concept has none).
5. `check_concepts` refuses the whole sheet before any call when one entry is unfilled, a concept is not found by `segment_berlin`, or its page differs from the sheet's.
6. An unreadable reply (prose, wrong shape, empty, a meter without a label) either raises ValueError or gives three `no`; it never gives a `yes`.
7. Replay: the tests record into a temporary store with a fake model and replay with no provider; recordings hold replies only (no `base64` in the files). Whether real recordings are kept is the development agent's call.
8. The sheet is block-style YAML (one `concept:` line per entry, which the check script reads by regex); its `concept` is a quoted string (so `4.4` stays `4.4`); its strings are facts of at most 40 characters; no text blocks, no images.
9. Status doc pins: section `## Go/no-go vision check (MKC-25)`, the column names above, cells exactly `yes` or `no`, one decision line attributed `(the user, dd.MM.yyyy)`.
10. Berlin only needs a new line in design section 15 naming `MKC-25` and `Berlin only`; the existing "narrows to Berlin only" line does not count. A go must not have such a line.
11. `draft_locked`: once any item of the key (document hash and concept key) is `approved` or `committed`, or the queue row's item is, a save is refused. "The approved body stays" is asserted as the body just before the refused save (`v2` in the probe, the body in the row when A was approved). Whether MKC-29 keeps a snapshot of the body at approval time is the coordinator's call (it may need migration `0015`).
12. The CLI is not tested beyond `--help`: fetching the PDF and writing the table are live work under the €1.00 budget.
13. Grants: the brief granted lane A `drafts.py`, `loop.py` and `0015` for the sub-issue. The sheet folder `backend/data/go_no_go/`, the status doc's MKC-25 section and the section 15 line (Berlin only) are proposed here, and `scripts/check_go_no_go.py` was written by the test agent on ruling 5; the coordinator confirms.

### For the coordinator (MKC-25)

**Proposed concepts** (Berlin, "Messkonzepte" September 2026, sha256 `4e12c90f…29a18`). The reasons name the diagram type and why it tests vision, never the meters or components, so the user's truth stays blind:

1. **12, page 33**, "Verbrauch mit einer Messlokation (Standard)": the simple single-meter case; vision must get the plain case exactly right.
2. **3, page 14**, "Überschusseinspeisung mit Erzeugungsmessung": the standard PV (generation) concept, the most common household case after plain supply.
3. **11, page 31**, "Steuerbare Verbrauchseinrichtung nach § 14a EnWG mit separater Messung": heat pump or § 14a; a separately metered branch with a subscripted meter label and control devices.
4. **3.3, page 16**, "Überschusseinspeisung mit Erzeugungsmessung und mit Speicher (separate Wechselrichter)": storage; a cascade with a dashed control line and two inverters to tell apart.
5. **4.2, page 19**, "Überschusseinspeisung mit Erzeugungsmessungen, Abgrenzungsmessung und mit Speicher (separate Wechselrichter)": the hard diagram, the page with the most drawn objects of the catalogue (292 lines, rects and curves), a deep cascade with parallel branches.

**Labelling rules** (in the sheet's header comment, the vision prompt and decision 86): labels as printed without inner spaces (`Z 1` -> `Z1`, a lone `Z` -> `Z`, `Z` with subscript `SV` -> `Zsv`); `upstream` and `attached_to` = the nearest meter on the path to the grid, `null` if none; component kinds from `ComponentKind` in `mkc/extraction/draft.py` (G, B, WR, SE, SV, sVE, S); consumer arrows and the ownership boundary are not components.

**Questions and notes:**

- `compare` only strips and case-folds (ruling 4). A label written `Z 1` on one side and `Z1` on the other is a `no`. Both the sheet and the prompt say "no inner spaces"; should `compare` also drop inner whitespace? Not changed without your ruling.
- `mkc/harness/tools.py` (the `draft_locked` comment: "the key's draft is approved or committed") and the docstring of `Approval` in `mkc/db/models.py` are outside the grants and left as they are; both still read true but less precise than decision 85.
- The status doc's heading "the full log of 84 decision numbers" and the "Decision numbers per lane" table are the coordinator's to update for 85–87.
- The live run: `uv run python -m mkc.extraction.vision_check` (default sheet, fetches Berlin, 200 dpi). With `MKC_MODEL_MODE=record` and `MKC_MODEL_REPLAY_DIR` set outside the repo, a crash after some calls does not pay twice on a rerun.

## Next steps

1. Coordinator: confirm the 5 concepts and the labelling rules ("For the coordinator"), then give the sheet to the user.
2. The user fills in `backend/data/go_no_go/truth.yaml`.
3. Development agent, on the coordinator's go: the live run (EUR 1.00), the result table, a recommendation, the user's decision through the coordinator; then the gate and the PR.
4. Test agent: the mutation pass on `draft_locked` and `vision_check`.

## Recent log

- **28.11.2026 11:20** Development agent: the blank truth sheet `backend/data/go_no_go/truth.yaml` (MKC-25.3): concepts 12 (p. 33), 3 (p. 14), 11 (p. 31), 3.3 (p. 16), 4.2 (p. 19), `meters: null`, `components: null`, the labelling rules in its header comment; the proposal with a reason each is under "For the coordinator (MKC-25)". `pytest tests/extraction/test_vision_check.py tests/test_check_go_no_go.py`: `1 failed, 61 passed in 3.58s`, the 1 being `test_check_go_no_go.py::test_the_repo_passes` (no status section yet). Lane head rewritten to the rulings and grants.

- **28.11.2026 11:18** Development agent: `mkc.extraction.vision_check` (MKC-25.2): `load_truth`, `require_filled`, `compare` (decision 86), `parse_reply`, `check_concepts` (every entry checked, found and on its page before the first call; one `vision` call per concept, role `extract_vision`; system and user text are constants, the image the only document input; an unreadable reply is three `no`), `results_table`, and the CLI (`--truth`, `--pdf`, `--dpi`, default 200; fetches Berlin with the operator allow-list; prints each call's cost and the read). `pytest tests/extraction/test_vision_check.py`: `2 failed, 28 passed in 3.75s`, the 2 being the sheet tests (no sheet yet). `mypy`: "Success: no issues found in 78 source files". No model calls.

- **28.11.2026 11:16** Development agent: sub-issues MKC-25.1 to 25.3 created at 11:14 (#228 to #230, GitHub `createdAt` 10:14:35Z to 10:14:42Z), linked to #25, on the board `In progress`, assigned to `qamran`. `draft_locked` for the whole key (MKC-25.1): `_check_writable` locks the key's draft row and refuses when any item of the key, or the item its `approval` row points at, is `approved` or `committed`; `loop.py` unchanged. `pytest tests/harness`: `330 passed in 25.50s` (red before: `test_draft_locked.py` `6 failed, 3 passed in 2.91s`). Fetch disclosed: the Berlin PDF once with `curl` at 11:12 (sha256 `4e12c90f…29a18`) into the session scratchpad outside the repo, to read the concept list and look at five diagrams (rendered there at 70 dpi); deleted at 11:12. No model calls.

- **28.11.2026 11:09** Test agent: `942bf3a` (11:09): the check-script tests now build synthetic docs (copies of the real docs would break once the real MKC-25 section lands); two tests pin that the script reads the sheet's concepts as YAML does. Fresh runs at `942bf3a`: `ruff check .` "All checks passed!", `ruff format --check .` "267 files already formatted"; the three new files `39 failed, 32 passed in 3.83s`; full suite (`uv run pytest -q`) `39 failed, 1294 passed, 2 skipped, 20 deselected, 6 warnings in 117.87s (0:01:57)`, the 39 being exactly the new red tests (6 `draft_locked`, 30 vision check, 3 check script). The 11:05 time of the entry below was not taken from a clock: its commit `9d1e953` is 11:04:11.

- **28.11.2026 11:05** Test agent: MKC-25 red tests `304a81c`, `64d0eb2`, `097de14` (10:57 to 11:00). Red run of the three new files: `38 failed, 31 passed in 6.38s`. Full suite (`uv run pytest -q`): `38 failed, 1293 passed, 2 skipped, 20 deselected, 6 warnings in 127.46s (0:02:07)`; the 38 are exactly the new red tests (6 `draft_locked`, 30 vision check, 2 check script). `python scripts/check_go_no_go.py`: exit 1 (sheet missing, section missing); every other `scripts/check_*.py` exits 0. Commits over 200 lines: `64d0eb2` (421), `097de14` (367), test files only. No model calls, no fetches.

- **28.11.2026 09:31** Test agent: `bash scripts/pre_pr.sh` at `900883b`: exit 0, "pre-PR gate: all steps passed"; pytest `1262 passed, 2 skipped, 20 deselected, 6 warnings in 109.13s (0:01:49)`. Pushed `76c6240..900883b`. This entry's commit changes only this file.

- **28.11.2026 09:26** Test agent: mutation pass on `76c6240`: 72 tried, 63 killed, 9 survived (first run 46 killed, 26 survived; 23 new tests in `4d100c9`, `6bc7aba`, `aa034e2` killed 17 of them). The 9 survivors are equivalent or near-equivalent (section "Mutation pass (MKC-23)").

- **28.11.2026 08:39** Development agent: `bash scripts/pre_pr.sh` at `2bea0d8`: exit 0, "pre-PR gate: all steps passed"; pytest `1239 passed, 2 skipped, 20 deselected, 4 warnings in 115.16s (0:01:55)`; commits over 200 lines `5e00ed9` (253), `b1e5e98` (234), `ffd2601` (475), `4ac7548` (311). Every `Refs:` line reads `qamran/`. PR #225 opened (createdAt 2026-11-28T07:38:12Z, 08:38:12 CET), head `2bea0d8`, assigned to `qamran`; #23 and #219 to #224 moved to `Testing`. This commit changes only this file.

- **28.11.2026 08:35** Development agent: `bash scripts/pre_pr.sh` at `8ed6eda` failed on `check_handoff.py` (and its test): this file's "Last updated" line had lost its comma (`28.11.2026 08:32`); pytest in that run `1 failed, 1238 passed, 2 skipped, 20 deselected, 4 warnings in 114.26s (0:01:54)`, the 1 being `test_check_handoff.py::test_the_repo_passes`. Fixed.

- **28.11.2026 08:32** Development agent: `bash scripts/pre_pr.sh` at `dcfb1f5`: exit 0, "pre-PR gate: all steps passed"; pytest `1239 passed, 2 skipped, 20 deselected, 4 warnings in 112.63s (0:01:52)`; commits over 200 lines `5e00ed9` (253), `b1e5e98` (234), `ffd2601` (475), `4ac7548` (311). Then: `test_cli.py` `test_inspect_lists_items_and_log` also asserts the `enqueue_approval` row in `run_log` (decision 83 says it is traced); `fetch.py`'s module docstring names the hop rule. My tests against mutants: the owner check in `enqueue_approval` removed: `test_approval_queue.py` `1 failed, 8 passed`; `isascii` removed there: `1 failed, 8 passed`; `fetch_document` without `allowed_hosts`: `test_hop_allowlist.py` `1 failed, 1 passed`. `git diff 05c2c43 --stat` over the nine red test files: only `test_run_documents.py` (4 insertions, 2 deletions). The scratch copies of both operator PDFs and the rendered region are deleted.

- **28.11.2026 08:27** Development agent: the first `bash scripts/pre_pr.sh` at `b8369ed` failed only on mypy (`render.py`: `pypdfium2` has no `py.typed`); every other step passed. The import is marked `# type: ignore[import-untyped]` in `render.py` (no change to the shared `pyproject.toml`); `uv run mypy`: "Success: no issues found in 77 source files".

- **28.11.2026 08:23** Development agent: docs (MKC-23.6): decisions 82 to 84 in design section 18, decision 62 (5) reworded, sections 7 and 8.3 "Built in MKC-23", backlog "As built" and the success criterion ticked, status doc line, runbook "The allow-list" and "Render and the approval queue (MKC-23)" (`MKC_RENDER_MAX_DPI`); this file's head rewritten to the current state (PR #215 finding 1). Full suite at `2582dbb` (`uv run pytest -q`): `1239 passed, 2 skipped, 20 deselected, 4 warnings in 111.66s (0:01:51)`.

- **28.11.2026 08:18** Development agent: redirect hops held to the allow-list (MKC-23.5, PR #215 finding 8): `http_get(..., allowed_hosts=None)` checks every hop with `is_allowed_url` before requesting it (default: the given URL's host); `fetch_document` and `DocumentOps` default to `http_get` with the operator's `allowed_hosts`. Existing tests changed: `test_fetch_rules.py` `_chain` hops on the listed host instead of `cdnN.example`. My `test_hop_allowlist.py` (2 tests) was written with the code. Lane-file times above corrected from git (the 07:58, 08:06, 08:27 and 08:33 headers were not taken from a clock). `pytest tests/extraction`: `242 passed, 1 skipped, 5 deselected`; live fetch at 08:18:11 (`pytest -m live tests/extraction/test_live_berlin.py tests/extraction/test_live_extract.py`, no model calls): `3 passed in 12.25s`.

- **28.11.2026 08:16** Development agent (commit `b503163`): real runs get the real document tools (MKC-23.4, PR #215 finding 6): `execute_run(..., documents=...)` passes a `DocumentOps` to the default registry; the executor builds one on `storage_from_settings(settings)`, else the local cache `backend/.cache/blobs` (as `mkc run start` does), so `--inline` runs get it too. Red test changed: `test_run_documents.py` `replies()` passes the region's bbox to `extract_text` (reason in the PR body). `pytest tests/harness/test_run_documents.py tests/worker/test_executor_documents.py`: `2 passed`.

- **28.11.2026 08:13** Development agent (commits `2883c55` to `7a0b96d`): the approval queue (MKC-23.3): table `approval` (`2883c55`, migration `0014`), `save_draft` guards, `draft_locked` and the real `enqueue_approval` (`4ac7548`), and the loop: a turn with a `save_draft` call is fenced first (MKC-17 finding 2); a `draft_locked` save fails the item as `tool_error: draft_locked`; after an item ends `draft_saved` the harness runs `enqueue_approval` and moves it to `pending_approval` (after `faults.item_ended`), and every full run first queues the `draft_saved` items a crash left unqueued; the baseline queues in memory and its report walks `running -> draft_saved -> pending_approval`. `pytest tests/harness tests/worker tests/test_cli.py tests/observability tests/db`: `2 failed, 420 passed, 1 skipped` (the 2 are MKC-23.4). Existing tests changed (states `pending_approval`, the `enqueue_approval` trace): `test_baseline.py`, `test_faults.py`, `test_cli.py`. My `test_approval_queue.py` (9 tests) was written with the code.

- **28.11.2026 08:04** Development agent (commit `9a736ad`): `render_region` (`mkc/extraction/render.py`, PDFium) is real through `DocumentOps`; the PNG goes into the store, the result holds `image_ref`, `width`, `height`; page, bbox and the cap `render_max_dpi` (`MKC_RENDER_MAX_DPI`, default 300) are checked before anything is drawn (`ToolRefused("invalid_args")`); `page` and `dpi` are `StrictInt`, bbox coordinates refuse booleans (MKC-14 finding 10, also for `extract_text`). `pytest tests/extraction tests/harness/test_registry.py tests/harness/test_tools.py tests/harness/test_tools_hardening.py tests/test_config.py`: `3 failed, 310 passed, 1 skipped, 5 deselected` (the 3 are the redirect hops, MKC-23.5). Fetch disclosed: both operator PDFs with `curl` at 08:04 into a scratch folder outside the repo (Berlin `4e12c90f…29a18`, SachsenNetze `7200b472…0bec`): no page rotation, pdfium and pdfplumber agree on the page sizes, and Berlin page 14's region renders as concept 3.

- **28.11.2026 08:01** Development agent: `MesskonzeptDraft` and the schema export (`ffd2601`); sub-issues MKC-23.1 to 23.6 created at 07:56 (#219 to #224, GitHub `createdAt`), linked to #23, on the board `In progress`. Live redirect check at 07:49: both operator URLs answer 200 `application/pdf` with no redirect, so every hop is held to the allow-list (coordinator ruling on assumption 15).

- **28.11.2026 07:44** Test agent: red test `05c2c43` (a row-less `draft_saved` item in a full run, PR #167 finding 7). Red run at `05c2c43`: eight new test files `59 failed, 5 passed in 6.05s`; full suite `59 failed, 1169 passed, 2 skipped, 20 deselected, 4 warnings in 111.13s (0:01:51)`. Commit sizes corrected from `git log --shortstat`.

- **28.11.2026 07:40** Test agent: MKC-23 red tests committed (`5e00ed9` to `7923957`, 07:36) and the lane file (`11425dc`). Assumptions 1 to 15 above.

- **28.11.2026 00:37** Development agent: `bash scripts/pre_pr.sh` at `ec8fead`: exit 0, "pre-PR gate: all steps passed"; pytest `1080 passed, 2 skipped, 19 deselected, 4 warnings in 97.88s (0:01:37)`. PR #215 opened (createdAt 2026-11-27T23:37:01Z, 00:37:01 CET), head `ec8fead`, assigned to `qamran`; #22 and #208 to #213 moved to `Testing`. This commit changes only this file.

- **28.11.2026 00:33** Development agent: pulled the branch at `21d2b07` (the test agent's mutation pass and the coordinator's merge of `main`, MKC-27). The coordinator accepts the 15 survivors; no code change. Next: the gate and the PR.

- **28.11.2026 00:32** Test agent: the "Mutation pass (MKC-22)" section itself (the commit before, `e499198`, carried only its log line because an edit had failed).

- **28.11.2026 00:31** Test agent: mutation pass on `f0bf9e8`: 119 tried, 104 killed, 15 survived (first run 65 killed, 54 survived; 35 new tests in five commits killed 39 of them). The 15 survivors are equivalent or near-equivalent (section "Mutation pass (MKC-22)"). With the new tests: `231 passed, 1 skipped, 4 deselected in 6.51s`; `ruff check .`: "All checks passed!"; `ruff format --check .`: "230 files already formatted".

- **28.11.2026 00:30** Test agent: two tests in `test_lbs_digits.py` kill L2 (`check_digit` without `isascii`) and L3 (no length check).

- **28.11.2026 00:30** Test agent: `test_fetch_mutants.py` kills F9 (the `content-length` check before reading) and F11 (the default `max_bytes`).

- **28.11.2026 00:30** Test agent: `test_page_zero_is_invalid_args` kills R4 (`page` ge=0).

- **28.11.2026 00:30** Test agent: `test_table_grid_rules.py` (16 tests) and `test_naive_line_rules.py` (3 tests) kill the tables.py, cleantext.py and naive.py survivors B4 to B12, B16, B19 to B22, C3, C6, C7, C12, N2 to N5, N8, N10.

- **28.11.2026 00:30** Test agent (MKC-22 mutation pass): `test_text_layout_rules.py` (11 tests) kills text.py survivors T2, T4, T5, T8, T12, T14 to T17, T28, T29: pitch, indent, title stops, the list after `Anwendung:`, the 14th digit, a NaN bbox and a page past the end as `ValueError`.

- **28.11.2026 00:04** Development agent: `bash scripts/pre_pr.sh` at `af95d27`: exit 0, "pre-PR gate: all steps passed"; pytest `1011 passed, 2 skipped, 18 deselected, 4 warnings in 103.05s (0:01:43)`; commits over 200 lines `60c1f2e` (431), `b989630` (211), `fcd70e0` (239). Acceptance at `af95d27`: `uv run pytest tests/extraction -q`: `134 passed, 1 skipped, 4 deselected in 5.81s` (red at `c72296d`: `32 failed, 81 passed, 1 skipped, 4 deselected`); `test_tools_hardening.py test_lbs_digits.py`: `12 passed in 0.07s`. `git diff c72296d -- backend/tests`: 5 files, 276 insertions, all added files. Branch pushed; waiting for the mutation pass. This commit changes only this file.

- **28.11.2026 00:01** Development agent: the naive baseline resets its meter heading on each page; `join_lines` keeps the hyphen of a suspended compound (`Bezugs-` / `und`); decision 77 (4) and (7) say so. `pytest tests/extraction`: `134 passed, 1 skipped, 4 deselected in 6.30s`.

- **28.11.2026 00:00** Development agent: live run again at `334a483`, after the fetch hardening (23:57:24 to 23:57:35, 27.11.2026): `uv run pytest -m live tests/extraction/test_live_extract.py`: `2 passed in 9.08s`. Red tests: the naive meter heading must end with its page (`test_naive_rules.py`) and a suspended hyphen (`Bezugs-` / `und`) keeps its hyphen (`test_table_rules.py`): `2 failed, 3 passed in 0.37s`.

- **27.11.2026 23:54** Development agent: `bash scripts/pre_pr.sh` at `89b750d`: exit 0, "pre-PR gate: all steps passed"; pytest `1009 passed, 2 skipped, 18 deselected, 4 warnings in 106.90s (0:01:46)`. Commits over 200 lines: `60c1f2e` (431), `b989630` (211), `fcd70e0` (239). Every `Refs:` line reads `qamran/`. Branch pushed; no PR yet (the test agent's mutation pass comes first). This commit changes only this file.

- **27.11.2026 23:51** Development agent: docs: decisions 76 to 78 in design section 18, decision 62 (5) notes the hop rules, status doc line, backlog "As built", runbook "The allow-list". Full suite at `a4dc979` (`uv run pytest -q`): `1009 passed, 2 skipped, 18 deselected, 4 warnings in 103.00s (0:01:42)`. Fetch disclosed: the Berlin PDF was downloaded once with `curl` at 23:35 (sha256 `4e12c90f…29a18`) into a scratch folder outside the repo to read the real table grids and concept pages; deleted at 23:51. No model calls.

- **27.11.2026 23:49** Development agent: fetch hardening (PR #197 findings 1 to 4): a redirect to a URL with userinfo is refused before it is requested; the client's jar refuses every cookie; `is_allowed_url` allows only the default port and is False for a malformed one; `http_get` streams and raises `DownloadTooLarge` past `MAX_DOWNLOAD_BYTES` (50 MiB), `content-length` only as an early exit. `pytest tests/extraction`: `132 passed, 1 skipped, 4 deselected`. My `test_fetch_limits.py` (malformed `content-length`) was written with the code; against a plain `int()` it gives `2 failed, 1 passed`.

- **27.11.2026 23:47** Development agent: `extract_text` (`TextArgs`: `page`, optional `bbox` of four finite numbers, ordered) and `extract_tables` are real item tools through `default_registry(documents=DocumentOps(...))`; the PDF is read by the item's document hash. `test_extract_tools.py` (the red tests): passed; `pytest tests/extraction tests/harness/test_registry.py tests/harness/test_tools.py`: `11 failed, 148 passed, 1 skipped, 4 deselected`, the 11 all fetch hardening. My `test_extract_args.py` was written with the code; with the bbox rules taken out it gives `5 failed, 3 passed`, with them `8 passed`. Live run at 23:45:48: `uv run pytest -m live tests/extraction/test_live_extract.py`: `2 passed in 8.51s`.

- **27.11.2026 23:45** Development agent: `mkc/extraction/naive.py` (`naive_text`, `naive_tables`), pure Python: `test_tables.py`: `8 passed in 0.35s`. On the scratch copy of the Berlin PDF the baseline finds all 15 LBS codes and pairs 13 of them with the right concepts (`extract_tables`: 15 of 15); its labels are mostly cut. A first number for E1 (MKC-31), not a measurement.

- **27.11.2026 23:45** Development agent: `mkc/extraction/tables.py` (`extract_tables`, `table_rows`, `Row`): `test_table_rules.py test_tables.py`: 8 passed, the 3 naive-baseline tests still red. On the scratch copy of the Berlin PDF: 15 LBS rows (pages 6 and 7), 50 meter-tech rows (pages 4 and 5), the Z1 heading joined to `Bezugsmessung, Einspeisemessung (Z1 o. Zsv), Abgrenzungsmessung (Z3)`.

- **27.11.2026 23:43** Development agent: red tests for the grid-to-rows rules on grids in the real Berlin shapes (`test_table_rules.py`: the six-row Z1 header with `Abgren-`/`zungsmessung`, blank rows round the LBS header, a short code cell, the decoy): `3 failed`.

- **27.11.2026 23:43** Development agent: a footnote marker inside a footnote's text starts the next one: `test_text_rules.py test_text.py`: `10 passed in 0.42s`; Berlin page 22 now gives `*1)` and `*2)` apart.

- **27.11.2026 23:42** Development agent: red test: a `*2)` at the end of a footnote line starts the next footnote (Berlin page 22): `1 failed, 4 passed in 0.50s`.

- **27.11.2026 23:42** Development agent: `mkc/extraction/text.py` (`extract_text`, `read_page`, `TextFields`, `StatedLbs`) and `cleantext.py` (`clean`, `join_lines`): `test_text.py test_text_rules.py`: `9 passed in 0.34s`. On the scratch copy of the Berlin PDF all 26 regions give a title, applications and stated codes; on page 22 the PDF prints `*2)` at the end of the line before, so two footnotes merge (fixed next).

- **27.11.2026 23:40** Development agent: red tests for the open `extract_text` rules (`test_text_rules.py`: a wrong check digit kept as printed, wrapped bullets and conditions, a superscript after a code, a hyphenated title): `4 failed in 0.48s`.

- **27.11.2026 23:39** Development agent: `ToolRegistry.execute` gives `invalid_args` when a validator raises `TypeError`, `AttributeError` or `KeyError` (both the cached and the plain path), and `tool_failed` with the type name when an exception's `__str__` fails (MKC-14 finding 2): `test_tools.py test_tools_hardening.py`: passed.

- **27.11.2026 23:39** Development agent: sub-issues #208 to #213 created, linked to #22, on the board `In progress`. `is_valid_code` and `check_digit` take ASCII digits only (MKC-12 finding 11): `tests/reference`: passed.

- **27.11.2026 23:30** Test agent: lane file points at the final red commit `c72296d`; assumptions 5 to 7 added (the image test never ran; no `bbox` means the whole page; `runner.py` builds the item registry without `documents`).

- **27.11.2026 23:30** Test agent: tightened after a review of the red tests: the naive baseline must return a row for `9992000000133` (an empty list no longer passes); the streaming test uses a 10 MB body and asserts reading stops before its end (any chunk size); a NUL in a table cell must not reach `extract_tables`' result; `test_synthetic.py` proves `nul_for` yields a NUL. `uv run pytest tests/extraction -q`: `32 failed, 81 passed, 1 skipped, 4 deselected in 6.31s`. Full suite `uv run pytest -q`: `43 failed, 947 passed, 2 skipped, 18 deselected, 4 warnings in 105.80s (0:01:45)`; all 43 failures are this ticket's red tests (32 extraction, 7 tools hardening, 4 LBS digits).

- **27.11.2026 23:24** Test agent: pinned interfaces, assumptions and the items left to the development agent written above. Fetches disclosed: the Berlin PDF once with `curl` (sha256 `4e12c90f…29a18`, the same edition) into a scratch folder outside the repo to read the LBS table, the meter-tech tables and concept pages 14, 20 and 32; the folder is deleted. No model calls.

- **27.11.2026 23:23** Test agent: red tests outside lane A's package, allowed by the coordinator: `tests/harness/test_tools_hardening.py` (MKC-14 finding 2: a validator raising `TypeError`, `AttributeError`, `KeyError`; an exception whose `__str__` fails) and `tests/reference/test_lbs_digits.py` (MKC-12 finding 11: `²`, full-width and Arabic-Indic digits): `11 failed, 1 passed in 0.34s`. The live test `test_live_extract.py` pins the Berlin codes read by hand (3, 4.4, 11.1) and the Z2 row of concept 3; not run (it would only fail on the missing modules after two fetches).

- **27.11.2026 23:22** Test agent: red tests for the fetch hardening sub-issue (`test_fetch_hardening.py`): `11 failed, 3 passed, 1 skipped in 0.87s` with `test_image_operators.py`. Red: userinfo in a redirect, the hop cookie, four port cases, the download limit (`MAX_DOWNLOAD_BYTES`, `DownloadTooLarge`, `max_bytes`). Green pins: userinfo on a listed host (two cases) and `:443`. Skipped: the image test, which runs only with `MKC_TEST_IMAGE` set.

- **27.11.2026 23:20** Test agent: red tests `test_extract_tools.py` (the item tools through `default_registry(documents=...)`, JSON results, the tool cache, no NUL in a result): `7 failed in 1.52s` (`unexpected arguments: bbox`, `not_implemented`). `layout_pdf(nul_for=...)` maps one glyph to U+0000 through `/ToUnicode`; pdfplumber then reads `'PV-Anlagen \x00'`.

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
