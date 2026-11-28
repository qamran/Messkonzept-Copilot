# Lane A2: SachsenNetze and gold

**Last updated:** 28.11.2026, 11:07

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md` (decision 61). Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-27` (done) → `MKC-24` (wave 4)
- **Branch and worktree:** `mkc-24-gold-tooling` (worktree `mkc-lanes/lane-a2`, cut from `main` `47e110a`)
- **Owns:** `mkc/extraction/sachsen*.py`, its tests and fixtures, and the gold tooling. Grants for MKC-24 (coordinator, wave 4): the new package `mkc/gold/`; the `gold_item` table appended at the end of `mkc/db/models.py` in a block commented `MKC-24`; the `gold` sub-app appended in `mkc/cli.py`; migration `0015_gold_item.py` with `down_revision = "0014"` (lane A may also add a `0015`; the coordinator re-chains the second PR); one append block each in `config.py` and `.env.example` if needed; `scripts/check_gold.py`; `backend/data/gold_split.yaml`. Lane A2 changes no lane A file (`mkc/extraction/draft.py` is imported read-only).
- **Decision numbers:** 75 and 88–89
- **Spend:** live `gold_draft` calls: €1.50 for MKC-24, public PDFs only, each call logged below with its printed cost. The test agent makes no live calls.

## Done

- `MKC-27` (`#27`): merged with PR #214, `3bacfc5` (27.11.2026 23:59), after a review PASS; decision 74.

## In progress

- `MKC-24` (`#24`): the test agent's red acceptance tests are committed (last red commit `cf4175f`, see "Red tests (MKC-24)"). Next: the development agent builds against them.

### Red tests (MKC-24)

All in `backend/tests/gold/` plus `backend/tests/test_check_gold.py`. Each test imports `mkc.gold` inside the test, so a missing module fails one test, not the collection.

- `conftest.py`: `draft_payload(**overrides)` (a valid `MesskonzeptDraft`; every draft-only value holds `SENTINEL`, the LBS code is `SENTINEL_LBS`), fixture `gold_engine` (migrated test DB, `gold_item` truncated).
- `test_gold_split.py` (named test `test_split_is_deterministic_and_balanced_per_operator`), module `mkc.gold.split`:
  - `concept_key(operator_id, number_hint)` gives `"<operator id>:<number hint>"`
  - `split_keys(keys, *, pinned_dev=()) -> GoldSplit` with `.assignments` (key to `dev` or `test`) and `.pinned_dev` (sorted tuple)
  - `dump_split(split) -> str` (the file text; no `\r`, one final newline), `load_split(path) -> GoldSplit`
  - per operator `|dev - test| <= 1`; pinned keys in dev; the same bytes for any input order and under `PYTHONHASHSEED` 0, 1 and 12345; pins that agree with the split change nothing; `ValueError` for an unknown pin, for more pins than `ceil(n/2)` of an operator, and for a key without `:`
- `test_gold_split_file.py`: `GOLD_SPLIT_FILE` is `backend/data/gold_split.yaml`; both operators of `operators.yaml`; SachsenNetze exactly `2-1, 2-1a, 2-2, 2-2a, 2-3, 2-3a, 2-3b, 2-5a, 3-1, 3-2, 3-5` (no `13`); 26 Berlin keys; balanced; pins in dev; equals `dump_split(split_keys(its keys, its pins))` (read with universal newlines); keys only (under 8,000 characters, lines up to 100, no `base64` or `data:`).
- `test_gold_draft.py` (named test `test_gold_draft_uses_gold_draft_role_model_not_extraction_model`), module `mkc.gold.draft`:
  - `ensure_independent(config: ModelsConfig)`: `ModelConfigError` when `gold_draft` has the same provider and model as `extract_vision`; the repo's `models.yaml` passes
  - `draft_concept(client, config, *, key, text, images=()) -> GoldDraft` (`.key`; `.payload` valid as `MesskonzeptDraft`; `.drafted_by` is `ModelReply.model_id`, for example `openrouter:anthropic/claude-haiku-5.5`)
  - through a real `ModelClient` with a recording factory: every trace has role `gold_draft`; only the gold model is built; a refused config makes no call; a reply that is not a `MesskonzeptDraft` raises `ModelError` or `ValueError`; the PDF text is in a user message, not the system prompt. The client method (`chat`, `vision`, `chat_structured`) is not pinned.
- `test_gold_table.py`: `mkc.db.models.GoldItem` on table `gold_item` with `kind, key, split, payload, drafted_by, verified_by, blind` (`blind` not null; `payload`, `drafted_by`, `verified_by` nullable); a `split` other than `dev` or `test` raises `IntegrityError`; `mkc.gold.store.store_gold_draft(session, draft, *, split)` writes kind `concept`, blind false and `drafted_by`; a second draft of the key replaces an unverified payload; a verified item is never overwritten.
- `test_gold_exchange.py` (named test `test_blind_mode_hides_draft_payload`), the CLI and `mkc.gold.exchange.export_items(session, *, blind=False, keys=None) -> dict`:
  - `mkc gold export --out FILE`: JSON `{"items": [...]}`, each item with `kind`, `key`, `split`, `blind`, `payload`, `drafted_by`
  - `mkc gold export --out FILE --blind --key K`: no draft value in the raw bytes (no `SENTINEL`, no LBS code, no model name); the item has `blind: true` and no payload or drafter; a blind item of `K` (`blind = true`, no drafter, no payload) exists next to the drafted one, which stays as it was
  - `mkc gold import FILE --verified-by NAME` (required): a filled-in blind label sets `verified_by` and `drafted_by` stays empty; an unfilled blind item is not verified; export, edit, import sets `verified_by` and keeps `drafted_by`; a re-import changes nothing; a payload that is not a `MesskonzeptDraft` exits 2, names its key and imports nothing
  - data rule: an export whose payload holds a data-URI image, a 1,200-character base64 run or a text block over 5,000 characters exits non-zero, names the key and writes none of it; a normal footnote of about 300 characters exports
- `test_gold_cli.py`: `mkc gold --help` lists `split`, `draft`, `export`, `import`; `mkc gold split --keys FILE [--pin-dev KEY ...] --out PATH` writes exactly `dump_split(...)` as bytes (LF also on Windows); twice gives the same bytes; an unknown pin exits 2, names the key and writes nothing; `mkc gold draft --help` exits 0.
- `test_check_gold.py`: `scripts/check_gold.py` with `problems(root) -> list[str]`, exit 1 on problems. The pinned line, in the status doc section whose heading starts with `## Lane A2` and names `MKC-24`:
  `- **Berlin gold batch 1:** <N> concepts verified, <H> h of the user's time`
  (N at least 1; H above 0 with a dot as decimal mark; more text may follow). Red until the user has verified the batch.
- Red run (28.11.2026, at `0ac90c2`): new files `65 failed, 1 passed, 16 errors in 5.19s`; the one pass was a false green (an unknown `gold` command also exits 2), fixed: the unknown-pin test now needs the key in the output, and that file then gave `4 failed in 1.37s`. Full non-live suite: `66 failed, 1262 passed, 2 skipped, 20 deselected, 6 warnings, 16 errors in 118.46s`; the baseline before the tests was `1262 passed, 2 skipped, 20 deselected, 6 warnings in 123.52s`. Reasons: `ModuleNotFoundError` for `mkc.gold` and `check_gold`, `UndefinedTable` for `gold_item`, no `gold` command.
- Commits over 200 lines (to disclose in the PR): `e41e032` (345), `becb54f` (258), `417a4bd` (317); each is one group of test files.

### Assumptions (for the coordinator to confirm)

1. **The user-task check blocks CI.** CI's docs job runs every `scripts/check_*.py`, and `test_check_gold.py::test_the_repo_passes` is in the backend suite, so the PR cannot go green until the user has verified the first Berlin batch and the line is in the status doc. The user can do the batch locally on the branch. If the PR should merge first, the coordinator decides how.
2. **Two items per key for blind labels.** A blind label is a second `gold_item` of the same key (`blind = true`, no drafter) next to the drafted one, so agreement between blind labels and verified drafts can be reported (design 11.1). Uniqueness is then per (kind, key, blind), not per (kind, key). The tests pin the behaviour, not the constraint.
3. Pins: a pinned key that is not among the keys, or more pins than `ceil(n/2)` for one operator, is a `ValueError` (CLI exit 2).
4. Independence: only the same provider and model as `extract_vision` is refused. The repo maps both roles to `openrouter` with models of different families; design 11.1 says "another provider". The tests accept the same route with another model.
5. `verified_by` comes from `--verified-by`, never from the file.
6. Not pinned: an import of a key that has no item; who picks the blind keys (the user, with `--key`); where a blind item takes its split from (the drafted item or the split file); the exact limits for "long text" and a base64 run (the tests stay far from any limit).
7. `drafted_by` is `ModelReply.model_id` (`provider:model`).
8. The split file also lists the pinned keys, so it can be written again from itself. Its YAML layout is free as long as `load_split` reads what `dump_split` writes.
9. Berlin's 26 keys need one live fetch and segment of the public PDF (no model call); the number hints are not in the repo.
10. `mkc gold draft`'s options, and how it gets a region's text or image (fetch, segment, text, render), are not pinned; the role, the provenance and the store are.

### Not covered by red tests

- The prompt's wording and how the PDF text is wrapped as data (only "in a user message").
- The `0015` revision id (the coordinator may re-chain it); `test_backup_runs_migration.py` already compares the ORM with the migrations.
- The decision log entries (75, 88–89), the ADR and the status doc text beyond the pinned line: review items.

## Next steps

1. Development agent: sub-issues for `#24`, then build `mkc/gold/`, the table, migration `0015`, the CLI, `scripts/check_gold.py` and `backend/data/gold_split.yaml` against the red tests.
2. Coordinator: answer assumptions 1 and 2.
3. User: verify the first Berlin gold batch and log the hours (the pinned line).
4. Test agent: mutation pass once the development agent is done.

## Recent log

- **28.11.2026 11:07** Test agent: MKC-24 red tests committed (`e41e032`, `becb54f`, `417a4bd`, `0ac90c2`, `cf4175f`): split, split file, draft role, table, export and import with blind mode, and the user-task check. New files: `65 failed, 1 passed, 16 errors` (the pass was a false green, fixed); full non-live suite: `66 failed, 1262 passed, 2 skipped, 20 deselected, 6 warnings, 16 errors in 118.46s`.
- **27.11.2026 23:59** PR #214 merged as `3bacfc5`: MKC-27 done.
- **27.11.2026 23:45** Development agent: `scripts/pre_pr.sh` at `9e6641e` exit 0 (`972 passed, 1 skipped, 17 deselected, 4 warnings in 100.86s`); PR #214 opened (createdAt `2026-11-27T22:45:05Z`, 23:45 CET), assigned to `qamran`; `#27`, `#201`, `#202` set to `Testing`.
- **27.11.2026 23:42** Development agent: coordinator ruling: the 9 survivors are accepted, no code change. Preparing the PR.
- **27.11.2026 23:40** Test agent: mutation pass on head `5b7b8b9`: 72 mutants applied, 47 killed, 25 survived; new tests `test_sachsen_rules.py` kill 16 more (63 killed, 9 survived, all near-equivalent or not pinned on purpose); `107 passed, 3 deselected`.
- **27.11.2026 23:24** Development agent: decision 74 (2) now states only what the PDF shows for the placeholder (title `Nr. (tbd)`, no image, `Anwendungen: -`); the design's open question on the split method is marked answered. No ADR describes segmentation (ADR 003 is the database), so no ADR change.
- **27.11.2026 23:24** Development agent: test `test_the_footer_band_keeps_a_frame_line_a_little_lower_than_page_8s` pins `FOOTER_BAND` (0.91): with 0.9 it fails (`1 failed, 5 passed`), with 0.91 `6 passed`.
- **27.11.2026 23:19** Development agent: decision 74 (design section 18), the status doc's Lane A2 section, the backlog's MKC-27 "As built" note and the `operators.yaml` comment (09/2025, 9 pages, 11 concepts). Decision 75 is left for MKC-24.
- **27.11.2026 23:19** Development agent: plan doc `docs/superpowers/plans/271120262318-mkc-27-sachsen-segmentation.md` (half page, with the reasons). The two log lines below had times written by hand; corrected to the commit times from git (23:15 and 23:18).
- **27.11.2026 23:18** Development agent: `mkc/extraction/sachsen.py` (half page split, heading `Messkonzept <n>:` on the half's first line, placeholder by its `Nr. (tbd)` title, footer band at 0.91 of the height) and `SEGMENTERS["sachsennetze"]`. `tests/extraction`: `1 failed, 87 passed, 3 deselected` (only the plan doc test is left). Live run (coordinator's go, no model call): `1 passed in 1.48s`, 11 regions on pages 3 to 8.
- **27.11.2026 23:15** Development agent: own red tests `test_sachsen_layout.py` (5 tests, the real page furniture: background, divider, frames, rule, logo; heading form; placeholder by title; any page width), red: `5 failed`.
- **27.11.2026 23:15** Development agent: sub-issues `#201` and `#202` created; the coordinator-granted edits in lane A's files (the test's operator id and the `NoSegmenter` docstring) done.
- **27.11.2026 23:10** Test agent: red tests for MKC-27 written; real PDF studied (9 landscape pages, 12 halves, 11 concepts plus one `Nr. (tbd)` placeholder).
