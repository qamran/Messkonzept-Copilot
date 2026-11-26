# MKC-12 plan: Codeliste research and LBS reference data

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ticket:** MKC-12 (#12). **Branch:** `mkc-12-codeliste-lbs`.

**Goal:** know the current BDEW Codeliste der Lokationsbündelstrukturen (version, terms) and load its LBS codes into the repo and the database as cited facts.

**Architecture:** a research note records the source. A build script reads the Codeliste PDF at runtime (never committed) with pdfplumber and writes `backend/data/lbs_structures.yaml`. That file holds only codes, Bezeichnung, object composition and a page citation. The package `mkc.reference.lbs` validates and loads the YAML (check digit, no duplicates). Migration `0003` adds the table `lbs_structure`, and `mkc-load-lbs` upserts the YAML into it.

**Tech stack:** Python 3.12, PyYAML, SQLAlchemy 2, Alembic, pytest; pdfplumber only in the build script (`uv run --with pdfplumber`).

**Spec:** design doc section 6 (LbsStructure, research issue), feature 13; backlog entry MKC-12.

## Research results (26.11.2026, sources in the research note)

- **Current edition:** "Codeliste der Lokationsbündelstrukturen", version 1.0, "Konsolidierte Lesefassung mit Fehlerkorrekturen", Stand 13.12.2024, applicable from 01.10.2024, author BDEW. The BDEW MaKo platform's document list (`https://bdew-mako.de/api/documents`, entry 7713) shows it valid from 13.12.2024 with no end date and `isFree: true`. Mitteilung Nr. 58 of the BNetzA (01.10.2026) publishes no new Codeliste. PDF: `https://bdew-mako.de/pdf/Codeliste-Lokationsbu%CC%88ndelstrukturen_1_0_Fehlerkorrektur_20241213.pdf`, 52 pages.
- **Content:** 15 structure codes (`9992 00000 001 8` to `018 3`; `005`, `009`, `014` are not used) plus object codes (`9992 00000 1xx x`). Codes are written with spaces only for reading; in data exchange they have none.
- **History:** the consultation draft (Stand 01.08.2022) had 16 structures. The final 1.0 (31.03.2023) dropped `009 2` and renamed "Pooling" to "Summenmessung" and "dynamisch" to "flexibel". The corrected editions changed text and reference columns, not codes.
- **Check digit:** the Codeliste does not define one. Every code fits the Lok- und Waggon-Kennzeichnungsverfahren that BDEW uses for BDEW-Codenummern and the MaLo-ID (BDEW Anwendungshilfe "Identifikatoren in der Marktkommunikation" 1.2, 07.02.2025, section 8.1). Same format and method, but these are not BDEW-Codenummern: those have 0–8 at position 3, these have 9.
- **Licence:** no licence or copyright statement was found in the PDF, on the BNetzA pages or via the MaKo platform's API. The platform marks the document free. We commit no part of the document, only facts with a citation (AGENTS.md data rules).
- **Berlin:** Stromnetz Berlin "Messkonzepte", Ausgabe September 2026, 33 pages, `https://www.stromnetz.berlin/files/globalassets/dokumente/anschluss/messkonzepte_09-2026.pdf` (sha256 `4e12c90f…29a18`), pages 6–7: an LBS table that lists all 15 codes with "Bezeichnung nach edi@energy".

## Global constraints

- No BDEW, edi@energy or operator PDF in the repo; PDFs live in a temp dir only.
- The YAML holds only: code, Bezeichnung, object composition, page, and the source block. No prose, no diagrams.
- No mako in any form.
- Commits: `MKC-12: <summary>` + `Refs: qamran/Messkonzept-Copilot#<sub-issue>`; under 200 lines where possible; HANDOFF.md in every commit.
- Migrations are additive only (decision 48).
- ruff, mypy strict, all `scripts/check_*.py` green.

## Review focus

1. Codes loaded as YAML ints (unquoted) lose leading zeros or type: the loader rejects any non-string code.
2. pdfplumber column shifts or wrapped cells give a wrong composition: each object code must map to exactly one (Objekt, Richtung, Ebene) across all structures; the build script fails otherwise.
3. Umlauts in Bezeichnung (e.g. "Wärmepumpenkaskade") mangled by encoding: a test asserts the exact string after load.
4. A second load into the table duplicates rows: `sync_lbs` upserts by code; running it twice keeps 15 rows.
5. The check digit test only checks the data it validates: the AWH worked example (`4137355924` → `1`) is a fixed test vector.

## Sub-issues

| Key | What |
|---|---|
| MKC-12.1 | Research note `docs/261120261404-codeliste-research.md` + `scripts/check_codeliste_note.py` (red first); decision 50; status doc and design doc research item ticked |
| MKC-12.2 | `mkc.reference.lbs`: check digit, `LbsStructure`, `load_lbs(path)`; `scripts/build_lbs_yaml.py`; `backend/data/lbs_structures.yaml`; the three ticket tests and the review-focus tests |
| MKC-12.3 | Migration `0003` table `lbs_structure`, ORM model, `sync_lbs(session, structures) -> int`, CLI `mkc-load-lbs` |

**How rows reach `lbs_structure`:** no ticket reads the table yet (first readers: MKC-22 table check, the rule table, E2). This ticket gives the table and `mkc-load-lbs`; locally and in tests it is run by hand. Running it on deploy (Helm hook after `alembic upgrade head`, `backend/data/` copied into the image) is wired in the first ticket that reads the table. Recorded in decision 50.

---

### Task 1 (MKC-12.1): research note and its check

**Files:**

- Create: `scripts/check_codeliste_note.py`
- Create: `docs/261120261404-codeliste-research.md`
- Modify: design doc section 18 (decision 50) and the research item in section 6; `docs/241120261430-project-status.md` (line "Research: BDEW Codeliste…" ticked); `HANDOFF.md`

- [ ] **Step 1:** write `scripts/check_codeliste_note.py`: finds exactly one `docs/*-codeliste-research.md`. The note must contain the headings `## Version`, `## Source`, `## Format`, `## Licence and terms`, `## What may be committed`, `## Check digit`, and the strings `13.12.2024` and `https://`. Exit 0 = ok, 1 = problems with the list printed.
- [ ] **Step 2:** run `python scripts/check_codeliste_note.py`. Expected: FAIL "no research note". Commit (red).
- [ ] **Step 3:** write the note from the research results above, in plain English: version and edition history, source URLs (MaKo platform entry, BNetzA Mitteilungen 32, 33, 58), format (PDF + informative Word, tables per structure; no machine-readable form), licence (none found, where we looked, free on the platform), what may be committed, check digit (method, the AWH source, "not defined by the Codeliste"), Berlin's use of the codes.
- [ ] **Step 4:** run the check. Expected: ok. Decision 50 in the design doc; status doc; HANDOFF. Commit.

### Task 2 (MKC-12.2): loader, check digit, YAML

**Files:**

- Create: `backend/src/mkc/reference/__init__.py`, `backend/src/mkc/reference/lbs.py`
- Create: `backend/tests/reference/__init__.py`, `backend/tests/reference/test_lbs.py`
- Create: `scripts/build_lbs_yaml.py`, `backend/data/lbs_structures.yaml`
- Modify: `backend/pyproject.toml` (add `pyyaml>=6.0`, dev `types-pyyaml`)

**Interfaces (produces):**

- `check_digit(payload: str) -> int`: payload of digits; positions counted from the left starting at 1; odd positions weight 1, even weight 2; result `(10 - sum % 10) % 10`.
- `is_valid_code(code: str) -> bool`: 13 digits, last digit = `check_digit(code[:12])`.
- `@dataclass(frozen=True) LbsObject(code: str, objekt: str, richtung: str, ebene: int, flexibilitaet: str, anzahl: str)`
- `@dataclass(frozen=True) LbsStructure(code: str, bezeichnung: str, page: int, objects: tuple[LbsObject, ...])`
- `@dataclass(frozen=True) LbsSource(title: str, publisher: str, version: str, edition: str, applies_from: str, url: str, sha256: str)`
- `load_lbs(path: Path) -> list[LbsStructure]`, `load_lbs_source(path: Path) -> LbsSource`; `DEFAULT_PATH` = `backend/data/lbs_structures.yaml`; errors raise `LbsDataError(ValueError)`.

**YAML shape:**

```yaml
source: {title, publisher, version: "1.0", edition: "Konsolidierte Lesefassung mit Fehlerkorrekturen, Stand 13.12.2024", applies_from: "2024-10-01", url, sha256, retrieved: "2026-11-26"}
structures:
  - code: "9992000000026"
    bezeichnung: "Verbrauch mit einer Messlokation (Standard)"
    page: 19
    objects:
      - {code: "9992000001032", objekt: MeLo, richtung: "Verbrauch (Netzübergabe)", ebene: 1, flexibilitaet: Starr, anzahl: "1"}
```

- [ ] **Step 1:** write the failing tests in `backend/tests/reference/test_lbs.py`:
  - `test_check_digit_matches_awh_example`: `check_digit("4137355924") == 1`.
  - `test_lbs_codes_are_13_digits_with_valid_check_digit`: for every structure and object code in `load_lbs(DEFAULT_PATH)`, `is_valid_code` is true; `len(structures) == 15`.
  - `test_invalid_check_digit_is_rejected`: `is_valid_code("9992000000027") is False`; a YAML with that code makes `load_lbs` raise `LbsDataError`.
  - `test_loader_rejects_duplicate_codes`: a temp YAML with one code twice raises `LbsDataError` naming the code.
  - `test_loader_rejects_non_string_code`: a code as YAML int raises `LbsDataError`.
  - `test_every_code_in_berlin_table_exists`: `BERLIN_LBS_CODES` (the 15 codes, with a comment naming Stromnetz Berlin "Messkonzepte", Ausgabe September 2026, pages 6–7) is a subset of the loaded codes.
  - `test_umlaut_round_trips`: the structure `9992000000175` has Bezeichnung `"Verbrauchskaskade mit ungemessenen TR (Wärmepumpenkaskade)"`.
  - `test_object_codes_are_consistent`: each object code has one (objekt, richtung, ebene) across all structures.
  - `test_source_names_edition`: `load_lbs_source(DEFAULT_PATH).edition` contains `13.12.2024`, and `url` starts with `https://bdew-mako.de/`.
- [ ] **Step 2:** `cd backend && uv run pytest tests/reference -q`. Expected: FAIL (module `mkc.reference` missing). Commit (red).
- [ ] **Step 3:** implement `mkc/reference/lbs.py` (yaml.safe_load; validate every field type; codes unique across structures).
- [ ] **Step 4:** write `scripts/build_lbs_yaml.py` (run: `uv run --no-project --with pdfplumber --with pyyaml python scripts/build_lbs_yaml.py <pdf-path> <out-path>`): checks the PDF's sha256 against the pinned value; reads the overview table (page 16) and each structure table; merges wrapped cells (rows with an empty code column join the row above); skips tables without an "Objekt-Code" header (graphics); fails when an object code maps to two (objekt, richtung, ebene), or when a structure has no objects. The PDF is downloaded by the user of the script into a temp dir; the script never writes it into the repo.
- [ ] **Step 5:** generate the YAML; spot-check three structures (001 8, 008 4, 016 7) against the PDF pages by eye and note them in the PR.
- [ ] **Step 6:** run the tests, ruff, mypy. Expected: all pass. Commit (code), then commit (data file + build script) separately.

### Task 3 (MKC-12.3): table `lbs_structure` and `mkc-load-lbs`

**Files:**

- Create: `backend/migrations/versions/0003_lbs_structure.py`, `backend/src/mkc/reference/sync.py`
- Create: `backend/tests/db/test_lbs_structure.py`
- Modify: `backend/src/mkc/db/models.py` (model `LbsStructureRow`), `backend/pyproject.toml` (`mkc-load-lbs = "mkc.reference.sync:main"`)

**Interfaces:**

- Consumes: `load_lbs`, `load_lbs_source`, `DEFAULT_PATH` from Task 2.
- Produces: table `lbs_structure(code varchar(13) primary key, bezeichnung text not null, objects jsonb not null, source text not null, version text not null)`; `sync_lbs(session: Session, structures: list[LbsStructure], source: LbsSource) -> int` (upsert by code; returns rows written; `source` = the URL plus the page, e.g. `"<url>#page=19"`; `version` = `"1.0 (Stand 13.12.2024)"`); `main() -> int` loads `DEFAULT_PATH` into `DATABASE_URL`.

- [ ] **Step 1:** failing tests in `backend/tests/db/test_lbs_structure.py`:
  - `test_0003_creates_lbs_structure_and_downgrades`: upgrade head → the table has exactly the five columns; downgrade `0002` → table gone; upgrade twice → no error.
  - `test_sync_lbs_loads_15_rows_and_is_idempotent`: after `sync_lbs` twice, `count(*) == 15`; row `9992000000026` has `objects[0]["code"] == "9992000001032"` and `version` contains `13.12.2024`.
  - `test_models_match_migrations` (existing) stays green with the new model.
- [ ] **Step 2:** `docker compose up -d db`, `cd backend && uv run pytest tests/db -q`. Expected: FAIL (no revision 0003). Commit (red).
- [ ] **Step 3:** migration `0003` (create table only, additive), model, `sync_lbs` with `insert … on conflict (code) do update`, CLI.
- [ ] **Step 4:** run all backend tests, ruff, mypy, the check scripts. Expected: green. Commit. Shut Docker down afterwards.

### Close-out

- [ ] HANDOFF, status doc (MKC-12 done items, decision 50), PR from the template (`Closes #12` and the sub-issues), ticket to `Testing`, review agent.
