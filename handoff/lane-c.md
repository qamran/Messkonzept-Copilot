# Lane C: Decision layer

**Last updated:** 27.11.2026, 21:16

Only lane C's agents write this file; the coordinator keeps `HANDOFF.md`. Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-46` → `MKC-47` (after MKC-36, MKC-26) → `MKC-48` (after MKC-31)
- **Branch and worktree:** `mkc-46-decision-spike`
- **Owns:** `mkc/decision/` and `tests/decision/`; in `mkc/models/providers.py`, new imports at the top (`cast`, `httpx2`, `langchain_core.decisions`, `TypeSafeClassifier`, `JsonValue`) plus, at the end, the constant `OPENROUTER_SYSTEM_ONE_BASE`, the subclass `_OpenRouterDecisionModel` and `build_decision_model`; one appended block each in `config.py` and `.env.example`
- **Decision numbers:** 68–70

## In progress

- `MKC-46` (`#46`), decision-layer spike: the test agent's red acceptance tests are committed in `backend/tests/decision/` (last red commit `dd184a2`). All green; the live spike passed; docs written; mutation pass done. Gate on `7a5efc8`: `bash scripts/pre_pr.sh` exit 0. The PR is opened right after this commit (its number goes into the next log entry).
  - Sub-issues: `MKC-46.1` (`#192`, settings, dependency, provider factory with ZDR routing; In progress), `MKC-46.2` (`#193`, `DecisionClient`; In progress), `MKC-46.3` (`#194`, live spike and docs; In progress). All three go to Testing with the PR.
  - **Spike result: the path works.** `POST https://openrouter.ai/api/v1/systemone` (TypeSafe SDK path, documented in OpenRouter's OpenAPI spec as "System One", "Compatible with the TypeSafe SDKs") answers 200 for `~typesafe/jev-latest`, resolved to `typesafe/jev-1.14-20261014`. So the base URL is `https://openrouter.ai/api`.

### Live calls (MKC-46; the coordinator's go: up to €0.50)

Costs are copied from OpenRouter's `usage.cost` (USD) in each response.

| Time (CET) | Call | Model (response) | Result | Cost |
|---|---|---|---|---|
| 27.11.2026 20:40:47 | raw probe, `POST /api/v1/systemone`, one Noul | `typesafe/jev-1.14-20261014` | 200 | 0.000011886 |
| 27.11.2026 20:40:58 | raw probe, same with `provider: {zdr: true, data_collection: deny}` | `typesafe/jev-1.14-20261014` | 200 | 0.000011886 |
| 27.11.2026 20:40:58 | raw probe, `provider.only: [nonexistent-provider]` | none | 404 "No allowed providers are available" | none printed |
| 27.11.2026 20:42:12 | raw probe, same 404 again to print the routing funnel | none | 404, `failed_routing_step: "Filter by Allowed Providers"` | none printed |
| 27.11.2026 20:47:56 | `uv run --env-file .env pytest -m live tests/decision/test_jev_live.py -v`: three Nouls, one Choice | not printed | "1 passed in 10.26s" | none printed |
| 27.11.2026 20:48:21 | the same request through `build_decision_model` and `DecisionClient` with a logging hook (scratch script) | `typesafe/jev-1.14-20261014` | 200; `has_pv` 0.99, `has_heat_pump` 0.99, `has_wallbox` 0.02, `scope` `household` (confidence 1) | 0.000017934 |

Six live calls. Printed costs: 0.000011886, 0.000011886, 0.000017934 USD; three calls printed none.

### Pinned interface (the test agent's tests hold the development agent to it)

- **`mkc/decision/types.py`** (plain frozen Pydantic models; callers never see LangChain types):
  - `NoulQuestion(instructions: str, yes: str = "", no: str = "")`; non-empty `yes`/`no` become `NoulCriteria(true=..., false=...)`, empty ones give `criteria=None`.
  - `ChoiceQuestion(instructions: str, criteria: dict[str, str])`, at least two labels (`ValueError` otherwise).
  - `NoulAnswer(probability: float)`, 0 to 1.
  - `ChoiceAnswer(choice: str, probabilities: dict[str, float], confidence: float)`.
  - `Decisions(nouls: dict[str, NoulAnswer], choices: dict[str, ChoiceAnswer], model_id: str)`, keyed by question id; `model_id` is the response's `model`.
  - `DecisionError(ModelError)`: a missing answer, an answer of the wrong type, or a choice outside the criteria. The message names the question id or the label.
- **`mkc/decision/client.py`:** `DecisionClient(decision_model: langchain_core.decisions.BaseDecisionModel)` with `decide(state: str, questions: Mapping[str, NoulQuestion | ChoiceQuestion]) -> Decisions`.
  - One `invoke({"state": state, "questions": {...}})` per call, with `langchain_core.decisions.Noul` and `Choice`.
  - 1 to 32 questions; otherwise `ValueError` (the message names "question" or "32").
- **`mkc/models/providers.py`** (append at the end, the only new provider code): `build_decision_model(settings: Settings, *, http_client=None) -> BaseDecisionModel`.
  - Model `settings.decision_model`; key `settings.openrouter_api_key` through `_key("openrouter", settings)` (so an empty key is a `ModelConfigError` naming `MKC_OPENROUTER_API_KEY`); never `TYPESAFE_API_KEY` or `TYPESAFE_BASE_URL`.
  - `base_url` contains `openrouter.ai`; the exact path is the spike's question.
- **`config.py`** (append-only block, comment "MKC-46"): `decision_backend: Literal["llm", "jev"] = "llm"` (`MKC_DECISION_BACKEND`) and `decision_model: str = "~typesafe/jev-latest"` (`MKC_DECISION_MODEL`). Add both to `.env.example` too.

### Red tests (test agent, phase 1)

- Red: `tests/decision/test_client.py` ("14 failed"), `test_settings.py` ("7 failed"), `test_providers.py` ("5 failed").
- `tests/decision/test_guards.py` ("14 passed"): green today; it keeps `langchain_typesafe` and `httpx2` imports inside `providers.py`.
- `tests/decision/test_jev_live.py` ("1 deselected", `@pytest.mark.live`): deselected by default; not run by the test agent.
- `tests/decision/fakes.py`: `FakeDecisionModel`, a `BaseDecisionModel` that replays a canned `ClassifierResponse` (the offline transport).

### Mutation pass (test agent, phase 2, head `f6216cb`)

One mutant at a time, each run against `uv run pytest tests/decision tests/models -q -x`, the file restored after each; no mutant was committed. Totals copied from the two scripts' output: "mutants tried: 33, killed: 22, survived: 11" (`types.py`, `client.py`, `config.py`, and two `providers.py` mutants) and "mutants tried: 7, killed: 6, survived: 1" (the other `providers.py` mutants): 40 tried, 28 killed, 12 survived.

Survivors (line numbers at `f6216cb`):

| # | File:line | Mutant | Verdict |
|---|---|---|---|
| 1 | `src/mkc/decision/types.py:20` | `NoulQuestion.instructions` without `min_length=1` | expected by the dev agent; an empty question is a caller bug |
| 2 | `src/mkc/decision/types.py:30` | `ChoiceQuestion.instructions` without `min_length=1` | expected, as 1 |
| 3 | `src/mkc/decision/types.py:36` | two-label check `< 2` → `<= 2` (a two-label choice refused) | **killed now** by `test_a_two_label_choice_question_is_accepted` (`8beb8c8`) |
| 4 | `src/mkc/decision/types.py:46` | `NoulAnswer.probability` without `ge`/`le` | expected; `langchain_core` already bounds `noul` to 0..1 |
| 5 | `src/mkc/decision/types.py:57` | `ChoiceAnswer.confidence` without `ge`/`le` | expected, as 4 |
| 6 | `src/mkc/decision/types.py:12` | `extra="forbid"` → `"ignore"` | accepted: callers build the types with keywords only |
| 7 | `src/mkc/decision/client.py:58` | criteria only when `yes and no` (a one-sided criterion dropped) | expected by the dev agent (one-sided criterion) |
| 8 | `src/mkc/decision/client.py:58` | one-sided criterion sent as `None` instead of `""` | expected by the dev agent |
| 9 | `src/mkc/decision/client.py:56` | Choice label texts sent as `""` | **killed now** by `test_a_choice_question_is_sent_with_its_instructions_and_label_texts` (`8beb8c8`) |
| 10 | `src/mkc/decision/client.py:56` | Choice instructions changed | **killed now** by the same test |
| 11 | `src/mkc/decision/client.py:87` | noul type check removed (a choice answer to a noul question gave `AttributeError`, not `DecisionError`) | **killed now** by `test_a_choice_answer_to_a_noul_question_is_a_decision_error` (`8beb8c8`) |
| 12 | `src/mkc/models/providers.py:195` | `timeout=settings.turn_timeout_seconds` removed | expected by the dev agent (TypeSafe's 30 s default would apply) |

The re-check of survivors 3, 9, 10 and 11 against `8beb8c8` printed "killed" for each. The three new tests pass on the dev agent's code unchanged: `uv run pytest tests/decision tests/models -q`: "202 passed, 13 deselected". Eight survivors remain (1, 2, 4–8, 12), each expected or accepted above; no production fix is asked for.

### Notes for the development agent

- Add `langchain-typesafe==0.1.0` (pinned with `==`; `test_repo_langchain_dependencies_are_pinned`) and say so in the PR; the coordinator runs `uv lock`. Do **not** add the `experimental` extra: it pulls in `langchain`, which the lock guard forbids.
- `langchain-typesafe` 0.1.0 re-exports its types from `langchain_core.decisions` (in `langchain-core==1.8.5`), so `mkc/decision/` imports only `langchain_core.decisions`.
- `TypeSafeClassifier` POSTs to `{base_url}/v1/systemone` with `Authorization: Bearer <key>`; it accepts a `client: httpx2.Client` for tests.
- The live run needs the coordinator's go (budget); record the spend and the result in ADR 004 and the status doc.

### Open questions (test agent's assumptions)

1. **Package name:** the MKC-47 interface line in the backlog says `mkc.decisions.client.DecisionClient`; the lane table and this lane use `mkc.decision`. Assumed `mkc.decision`; Fixed by the development agent (backlog line now `mkc.decision`).
2. **Shared guard list:** `tests/models/guards.py` `PROVIDER_MODULES` lacks `langchain_typesafe` and `httpx2`; this lane checks them in `tests/decision/test_guards.py`. The coordinator may add them to the shared list.
3. **LLM fallback scope:** only the default setting is pinned here. The fallback backend itself is MKC-47 (feature 66); it needs a model role (no `decide` role in `Role` or `models.yaml`), which is coordinator-owned.
4. **`json_schema`:** ADR 004 says the fallback uses `method="json_schema"`, but `ModelClient.chat_structured` passes no method (LangChain's default). Not pinned; for MKC-47.
5. **Pinned by assumption:** `DecisionError` subclasses `ModelError`, so the harness fails the item like any other model error (MKC-18); the guard also keeps `httpx2` (the transport of `langchain-typesafe`) inside `providers.py`, although the shared list does not forbid plain `httpx`.

## Next steps

1. Development agent: open the PR; set #46 and #192–#194 to Testing.
2. Coordinator: the review agent once `gh pr checks` is green.

## Recent log

- **27.11.2026 21:16** Development agent: pulled the test agent's `8beb8c8`, `0b4e268`, `7a5efc8`. `bash scripts/pre_pr.sh` exit 0: "709 passed, 1 skipped, 13 deselected in 124.87s (0:02:04)"; mypy "Success: no issues found in 51 source files"; over 200 lines: `81fc41c` (229). Fixed the "Owns" line (`providers.py` has new imports, a constant, a subclass and the function).
- **27.11.2026 21:12** Test agent (`0b4e268`): mutation pass on `f6216cb`: 40 mutants, 28 killed, 12 survived (see "Mutation pass"). Four survivors showed gaps in the parse criterion; three acceptance tests in `8beb8c8` kill them. `uv run pytest tests/decision tests/models -q`: "202 passed, 13 deselected".
- **27.11.2026 20:50** Development agent: live spike passed (see "Live calls"); the result in ADR 004 (amendment), the status doc (MKC-46 line, open item ticked), decisions 68 and 69 in the design doc; the backlog's MKC-47 interface line now says `mkc.decision.client.DecisionClient`. Decision 70 is not used yet (kept for MKC-47 or MKC-48).
- **27.11.2026 20:47** Development agent (`7f54dff`): `mkc/decision/` (`types.py`, `client.py`): `DecisionClient.decide` sends one `invoke` with `Noul`/`Choice`, checks 1 to 32 questions, and converts the reply into our frozen types; a missing, wrong-type or out-of-criteria answer is a `DecisionError`. `uv run pytest -q tests/decision`: "44 passed, 1 deselected"; `uv run mypy`: "Success: no issues found in 51 source files".
- **27.11.2026 20:46** Development agent (`aea6b8e`): red request tests `tests/decision/test_provider_requests.py` (`7175301`, red on `ImportError`), then `build_decision_model` at the end of `providers.py`: a `TypeSafeClassifier` subclass that adds `OPENROUTER_ROUTING` as `provider` to every body, base URL `https://openrouter.ai/api`. `uv run pytest -q tests/decision/test_providers.py tests/decision/test_provider_requests.py`: "9 passed"; `uv run mypy`: "Success: no issues found in 48 source files".
- **27.11.2026 20:43** Development agent: sub-issues `#192`–`#194` created, assigned to `qamran`, on the board and linked to `#46`. Added `langchain-typesafe==0.1.0` (`uv add`; lock adds only `langchain-typesafe`, deps `httpx2`, `langchain-core`) and the MKC-46 settings block. `uv run pytest -q tests/decision/test_settings.py`: "7 passed".
- **27.11.2026 20:37** Test agent (`dd184a2`): checked the fake end to end (a scratch script: the canned body validates; `.nouls`, `.choices`, `.model` and `seen` as the tests expect). Split the live test's imports so ruff stays green once `mkc.decision` exists. Whole backend suite `uv run pytest -q`: "26 failed, 676 passed, 1 skipped, 13 deselected" (the 26 are this lane's red tests); `uv run mypy`: "Success: no issues found in 48 source files"; every `scripts/check_*.py` exits 0.
- **27.11.2026 20:29** Test agent: red commits `1ed966f` (settings, provider factory, this file), `81fc41c` (`DecisionClient`, 229 lines: one test file and its fake), `485c89a` (guard and live tests). Red acceptance tests and the pinned interface. `uv run pytest tests/decision tests/models/test_guards.py -q`: "26 failed, 69 passed, 1 deselected"; `uv run pytest tests/decision -q`: "26 failed, 14 passed, 1 deselected". Reasons: `ModuleNotFoundError: No module named 'mkc.decision'`, `ImportError: cannot import name 'build_decision_model'`, and `Settings` without `decision_backend`/`decision_model`.
