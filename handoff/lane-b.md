# Lane B: Advisor

**Last updated:** 27.11.2026, 20:54

Only this lane's agents write this file; the coordinator keeps `HANDOFF.md`. Times are local time from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-36` → `MKC-37` (waits on lane A's MKC-30) → `MKC-38`
- **Branch and worktree:** `mkc-36-site-facts`
- **Owns:** `backend/src/mkc/advisor/`, the advisor API routes (`/api/advisor/*`), the advisor UI pages and components (`frontend/src/pages/AdvisorPage*`, `frontend/src/components/advisor/`, `frontend/src/lib/advisor*`)
- **Decision numbers:** 65–67

## In progress

- `MKC-36` (`#36`): the test agent's red tests are committed (red commits `f1d3a05` to `6de3f64`, tightened in `4be85d4`). The development agent builds against the interfaces below.

### Development agent

Sub-issues (all assigned to `qamran`, on the board, linked to #36): `MKC-36.1` (#176) SiteFacts model and extraction, `MKC-36.2` (#177) follow-up questions, `MKC-36.3` (#178) API routes, `MKC-36.4` (#180) facts card and advisor page, `MKC-36.5` (#183) docs.

- `MKC-36.1` (#176): built `mkc/advisor/facts.py`; `test_facts.py` and `test_facts_mapping.py` green (`22 passed`). Own tests in `test_facts_mapping.py` (prompt wrapping, note order).
- `MKC-36.2` (#177): built `mkc/advisor/questions.py`; `test_questions.py` and `test_questions_text.py` green (`17 passed`). Own tests in `backend/tests/advisor/test_questions_text.py` (texts, options, order).
- `MKC-36.3` (#178): built `mkc/advisor/api.py` and the `include_router` line in `mkc/api/app.py`; `uv run pytest tests/advisor -q` gives `53 passed`. Own tests in `test_api_errors.py`; `conftest.py` re-exports the fixtures of `test_api.py`.
- `MKC-36.4` (#180): built `frontend/src/lib/advisor.ts`, `frontend/src/components/advisor/FactsCard.tsx`, `frontend/src/pages/AdvisorPage.tsx` and the `/advisor` route in `App.tsx` (two operators as a constant); `npx vitest run`: `Test Files  10 passed (10)`, `Tests  49 passed (49)`; eslint, `tsc -b` and `npm run build` pass. `/advisor` has no nav link (`AppShell` is not lane B's file). Own tests in `FactsCard.details.test.tsx` and `AdvisorPage.details.test.tsx`.
- `MKC-36.5` (#183): decisions 65 and 66 (67 not used so far), design section 7 `SiteFacts`, the backlog's MKC-36 entry (questions route), the status doc's MKC-36 line.
- **Live calls:** 27.11.2026 20:49, a scratch script outside the repo, three `extract_facts` calls on synthetic text (`openrouter:google/gemini-3.8-flash`, role `facts`): the German example, a bakery, Modul 3. The provider accepted the schema; results matched (household facts; `commercial`; `modul3`). Costs from the trace: €0.0034271802, €0.005025954825, €0.004685212125; sum €0.013138. Nothing recorded for replay.

### Red tests (test agent)

Backend, `backend/tests/advisor/`:

- `fakes.py`: a real `ModelClient` over the fake chat model of `tests/models/fakes.py`; it answers with one `FactsExtraction` tool call, which the client validates against the schema the code passes.
- `test_facts.py`: `test_extracts_pv_battery_heatpump_modul2`, `test_english_input_handled`, `test_plugin_pv_out_of_scope`, `test_commercial_site_out_of_scope`, `test_empty_input_rejected`, `test_modul3_answered_as_out_of_scope`, `test_site_facts_reject_modul3`, plus user text sent as data, opaque `operator_id`, `unknown[]` filtering, medium voltage and off-topic.
- `test_questions.py`: `test_only_result_changing_unknowns_are_asked` and the gating cases.
- `test_api.py`: both routes, auth, 422 cases, Modul 3 through the route.

Frontend:

- `src/lib/advisor.test.ts`, `src/components/advisor/FactsCard.test.tsx`, `src/pages/AdvisorPage.test.tsx`.

Red state at 20:33: `uv run pytest tests/advisor -q` gives `3 errors in 0.65s` (each `ModuleNotFoundError: No module named 'mkc.advisor'`; collection errors also stop the full suite). `npx vitest run` on the three files gives `Test Files  3 failed (3)` (failed to resolve the missing modules); the full run gives `Test Files  3 failed | 5 passed (8)`, `Tests  26 passed (26)`. `npm run typecheck` gives 5 errors, all TS2307 for the missing modules. `ruff check`, `ruff format --check` and `npm run lint` pass.

`backend/pyproject.toml` got `[tool.ruff.lint.isort] known-first-party = ["mkc", "tests"]`: ruff matches the full module path, so imports of modules that did not exist yet sorted as third-party. Say so in the PR.

### Pinned interfaces (the development agent follows these)

`mkc/advisor/facts.py`:

- `FactKey = Literal["pv.kwp", "pv.feed_in", "pv.generation_metered", "battery.present", "battery.inverter", "sve.modul14a", "extra_households"]`
- `ScopeReason = Literal["modul3", "plug_in_pv", "commercial", "medium_voltage", "off_topic"]`
- `Pv(kwp: float | None, feed_in: "surplus" | "full" | None, generation_metered: bool | None)`
- `Battery(present: bool, inverter: "shared" | "separate" | None)`
- `Sve(type: "heat_pump" | "wallbox" | "other", modul14a: Literal[1, 2] | None)`: 3 fails validation (design 7)
- `ScopeNote(reason: ScopeReason, message: str)`: the message says "not covered, clarify with the operator" (it contains "operator")
- `SiteFacts(operator_id: str (min length 1), pv: Pv | None = None, battery: Battery | None = None, sve: list[Sve] = [], extra_households: int | None = None, unknown: list[FactKey] = [], out_of_scope: list[ScopeNote] = [])`
- `FactsExtraction`: the model-facing schema (class name is the tool name the fake answers with): `site_kind: "household" | "commercial" | "medium_voltage" | "off_topic"`, `pv: {kwp, feed_in, generation_metered, plug_in: bool} | None`, `battery: Battery | None`, `sve: list[{type, modul14a: Literal[1, 2, 3] | None}]`, `extra_households: int | None`, `unknown: list[str]`
- `MAX_TEXT_CHARS = 2000`
- `class EmptyInputError(ValueError)`
- `extract_facts(text: str, operator_id: str, client: ModelClient) -> SiteFacts`:
  - blank text raises `EmptyInputError` before any model call
  - one `client.chat_structured("facts", messages, FactsExtraction)`; the user text goes only into a `user` message, never the system message
  - mapping: `site_kind` other than household, `pv.plug_in`, or any `modul14a == 3` adds a `ScopeNote`; with any note, `pv`, `battery`, `extra_households` are `None` and `sve`, `unknown` are empty (never a forced match)
  - `unknown` keeps only `FactKey` values, in order

`mkc/advisor/questions.py`:

- `Question(field: FactKey, text: str, options: list[str])`
- `required_questions(facts: SiteFacts) -> list[Question]`, plain code, no model call:
  - out of scope: `[]`
  - asked: `unknown` keys that change the result (all `FactKey` except `pv.kwp`), plus missing values: PV present and `feed_in` is `None`; battery present and `inverter` is `None`; an SVE with `modul14a` `None`
  - not asked: PV keys without PV; `battery.inverter` without a present battery; `sve.modul14a` without an SVE
  - each field once; `options` are the allowed values (`pv.feed_in`: `["surplus", "full"]`, `battery.inverter`: `["shared", "separate"]`)

`mkc/advisor/api.py`:

- `router` (an `APIRouter`), included by `create_app` in `mkc/api/app.py`
- `get_model_client() -> ModelClient` (a FastAPI dependency, `ModelClient.from_settings`); tests replace it with `app.dependency_overrides`
- `POST /api/advisor/facts`, body `{text, operator_id}` → `SiteFacts`; `require_user` (any signed-in user, not admin); blank text, text over `MAX_TEXT_CHARS` and an empty `operator_id` are 422 with no model call; out of scope is a 200 with `out_of_scope` notes
- `POST /api/advisor/questions`, body `SiteFacts` → `list[Question]`; `require_user`; no model call

Frontend:

- `src/lib/advisor.ts`: types `SiteFacts`, `Question`, `ScopeNote` (the JSON above); `extractFacts(text, operatorId): Promise<SiteFacts>` and `requiredQuestions(facts): Promise<Question[]>` through `apiFetch`, `POST` with `Content-Type: application/json`; a non-ok response throws an error naming the status
- `src/components/advisor/FactsCard.tsx`: `FactsCard({ facts, onConfirm })`; shows the facts (e.g. "10 kWp", "surplus", "shared", "Modul 2"); buttons "Edit" and "Confirm"; edit mode has selects labelled "PV feed-in", "Battery inverter" and one "§14a module" per SVE (values `1` and `2` only); "Confirm" calls `onConfirm` with the edited facts; an out-of-scope site shows the note and no "Edit" or "Confirm"
- `src/pages/AdvisorPage.tsx`: `AdvisorPage({ operators: { id, label }[] })`; a textarea labelled "Site description", a select labelled "Operator", a button "Extract facts" (disabled while the description is blank); shows the facts card, then the questions after the confirm; shows request errors with the status
- `App.tsx`: route `/advisor` with the two catalogue operators as a constant until lane A serves an operator list (not tested here)

### Assumptions (the coordinator may overrule)

1. **Out of scope is a 200 `SiteFacts` with `out_of_scope` notes**, not an error status. MKC-47's scope guard builds on this shape.
2. **English input is extracted like German** ("handled"), not rejected; Review Focus 2's "not covered" applies to plug-in PV, commercial, medium voltage, off-topic and Modul 3.
3. **The result-changing facts** are those design section 9 names: feed-in, battery inverter, generation meter, §14a module, extra household, and whether there is a battery. The PV size alone is not asked for a household site. MKC-37's rule table may widen the set.
4. **`POST /api/advisor/questions`** is added so the UI can show the follow-up questions (feature 52); the ticket names only `required_questions`.
5. **`operator_id` is opaque:** any non-empty string; no operator lookup in lane B.
6. **Shared files:** the development agent edits `mkc/api/app.py` (one `include_router` line) and `frontend/src/App.tsx` (one route).

## Next steps

1. Test agent: mutation pass on the development agent's code (the coordinator starts it).
2. Development agent, on the coordinator's word: open the PR (`Closes #36`; disclose `frontend/src/test/setup.ts` and the test agent's ruff isort block), move #36 and #176–#183 to `Testing`.
3. Then MKC-37 waits on lane A's MKC-30.

## Recent log

- **27.11.2026 20:54** Development agent: `bash scripts/pre_pr.sh` on `d16ca1a`: exit 0, `715 passed, 1 skipped, 12 deselected in 129.53s`, `pre-PR gate: all steps passed`; CI frontend commands (`npm ci`, lint, typecheck, `npm test`: `Tests  49 passed (49)`, build) pass. No test agent test changed. Branch pushed; PR waits for the mutation pass.
- **27.11.2026 20:50** Development agent: live check of the `facts` schema, three calls, €0.013138; docs: decisions 65, 66, design 7, backlog and status doc lines.
- **27.11.2026 20:48** Development agent: `AdvisorPage.tsx` and the `/advisor` route; `npx vitest run` gives `Test Files  10 passed (10)`, `Tests  49 passed (49)`; eslint, `tsc -b`, `npm run build` pass.
- **27.11.2026 20:47** Development agent: `FactsCard.tsx` (view, edit with native selects, confirm; out of scope shows the notes only); `npx vitest run src/components` gives `Test Files  5 passed (5)`, `Tests  21 passed (21)`.
- **27.11.2026 20:47** Development agent: `frontend/src/test/setup.ts` unmounts after each test (`cleanup`): vitest runs without globals, so a second render in one file saw the first (the test agent's `FactsCard.test.tsx` renders five times).
- **27.11.2026 20:46** Development agent: `frontend/src/lib/advisor.ts` (types, `extractFacts`, `requiredQuestions`); `npx vitest run src/lib/advisor.test.ts` gives `Tests  3 passed (3)`.
- **27.11.2026 20:45** Development agent: red frontend tests `FactsCard.details.test.tsx`, `AdvisorPage.details.test.tsx` (`Test Files  2 failed (2)`, missing modules).
- **27.11.2026 20:44** Development agent: `mkc/advisor/api.py` (`POST /api/advisor/facts`, `POST /api/advisor/questions`, `get_model_client`); `uv run pytest tests/advisor -q` gives `53 passed in 12.44s`.
- **27.11.2026 20:44** Development agent: red test `test_api_errors.py` (`No module named 'mkc.advisor.api'`).
- **27.11.2026 20:42** Development agent: `mkc/advisor/questions.py` (`required_questions`); `tests/advisor/test_questions.py tests/advisor/test_questions_text.py` give `17 passed`.
- **27.11.2026 20:42** Development agent: red test `test_questions_text.py` (`1 error in 0.55s`, missing `mkc.advisor.questions`).
- **27.11.2026 20:41** Development agent: `mkc/advisor/facts.py` (SiteFacts, FactsExtraction, extract_facts); `tests/advisor/test_facts.py tests/advisor/test_facts_mapping.py` give `22 passed`.
- **27.11.2026 20:40** Development agent: sub-issues #176, #177, #178, #180, #183 created; red test `test_facts_mapping.py` (`1 error in 0.35s`, missing `mkc.advisor.facts`).
- **27.11.2026 20:33** Test agent: `4be85d4` tightens the red tests (page test no longer matches the typed text; `extra_households` cleared out of scope; no module question without an SVE). Backend `3 errors in 0.65s`; full vitest `Test Files  3 failed | 5 passed (8)`, `Tests  26 passed (26)`.
- **27.11.2026 20:29** Test agent: red tests committed, `f1d3a05` (ruff isort config) to `6de3f64`. Backend `3 errors in 0.74s` (missing `mkc.advisor`); frontend `Test Files  3 failed (3)` on the three new files.
