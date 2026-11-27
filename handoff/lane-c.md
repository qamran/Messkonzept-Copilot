# Lane C: Decision layer

**Last updated:** 27.11.2026, 20:46

Only lane C's agents write this file; the coordinator keeps `HANDOFF.md`. Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-46` → `MKC-47` (after MKC-36, MKC-26) → `MKC-48` (after MKC-31)
- **Branch and worktree:** `mkc-46-decision-spike`
- **Owns:** `mkc/decision/` and `tests/decision/`; one function appended at the end of `mkc/models/providers.py`; one appended block in `config.py`
- **Decision numbers:** 68–70

## In progress

- `MKC-46` (`#46`), decision-layer spike: the test agent's red acceptance tests are committed in `backend/tests/decision/` (last red commit `dd184a2`). The development agent is building.
  - Sub-issues: `MKC-46.1` (`#192`, settings, dependency, provider factory with ZDR routing; In progress), `MKC-46.2` (`#193`, `DecisionClient`; Ready), `MKC-46.3` (`#194`, live spike and docs; Ready).
  - Spike finding so far: `POST https://openrouter.ai/api/v1/systemone` (TypeSafe SDK path, documented in OpenRouter's OpenAPI spec as "System One", "Compatible with the TypeSafe SDKs") answers 200 for `~typesafe/jev-latest`, resolved to `typesafe/jev-1.14-20261014`. So the base URL is `https://openrouter.ai/api`.

### Live calls (MKC-46; the coordinator's go: up to €0.50)

Costs are copied from OpenRouter's `usage.cost` (USD) in each response.

| Time (CET) | Call | Model (response) | Result | Cost |
|---|---|---|---|---|
| 27.11.2026 20:40:47 | raw probe, `POST /api/v1/systemone`, one Noul | `typesafe/jev-1.14-20261014` | 200 | 0.000011886 |
| 27.11.2026 20:40:58 | raw probe, same with `provider: {zdr: true, data_collection: deny}` | `typesafe/jev-1.14-20261014` | 200 | 0.000011886 |
| 27.11.2026 20:40:58 | raw probe, `provider.only: [nonexistent-provider]` | none | 404 "No allowed providers are available" | none printed |
| 27.11.2026 20:42:12 | raw probe, same 404 again to print the routing funnel | none | 404, `failed_routing_step: "Filter by Allowed Providers"` | none printed |

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

### Notes for the development agent

- Add `langchain-typesafe==0.1.0` (pinned with `==`; `test_repo_langchain_dependencies_are_pinned`) and say so in the PR; the coordinator runs `uv lock`. Do **not** add the `experimental` extra: it pulls in `langchain`, which the lock guard forbids.
- `langchain-typesafe` 0.1.0 re-exports its types from `langchain_core.decisions` (in `langchain-core==1.8.5`), so `mkc/decision/` imports only `langchain_core.decisions`.
- `TypeSafeClassifier` POSTs to `{base_url}/v1/systemone` with `Authorization: Bearer <key>`; it accepts a `client: httpx2.Client` for tests.
- The live run needs the coordinator's go (budget); record the spend and the result in ADR 004 and the status doc.

### Open questions (test agent's assumptions)

1. **Package name:** the MKC-47 interface line in the backlog says `mkc.decisions.client.DecisionClient`; the lane table and this lane use `mkc.decision`. Assumed `mkc.decision`; the backlog line needs a fix.
2. **Shared guard list:** `tests/models/guards.py` `PROVIDER_MODULES` lacks `langchain_typesafe` and `httpx2`; this lane checks them in `tests/decision/test_guards.py`. The coordinator may add them to the shared list.
3. **LLM fallback scope:** only the default setting is pinned here. The fallback backend itself is MKC-47 (feature 66); it needs a model role (no `decide` role in `Role` or `models.yaml`), which is coordinator-owned.
4. **`json_schema`:** ADR 004 says the fallback uses `method="json_schema"`, but `ModelClient.chat_structured` passes no method (LangChain's default). Not pinned; for MKC-47.
5. **Pinned by assumption:** `DecisionError` subclasses `ModelError`, so the harness fails the item like any other model error (MKC-18); the guard also keeps `httpx2` (the transport of `langchain-typesafe`) inside `providers.py`, although the shared list does not forbid plain `httpx`.

## Next steps

1. Development agent: build `mkc/decision/`, `build_decision_model`, the settings block and the dependency until the red tests are green; then the live spike with the coordinator's go.
2. Development agent: write the result into ADR 004, the status doc and the decision log (numbers 68–70).
3. Test agent: mutation pass on the development agent's code, then report the surviving mutants.

## Recent log

- **27.11.2026 20:46** Development agent: red request tests `tests/decision/test_provider_requests.py` (`7175301`, red on `ImportError`), then `build_decision_model` at the end of `providers.py`: a `TypeSafeClassifier` subclass that adds `OPENROUTER_ROUTING` as `provider` to every body, base URL `https://openrouter.ai/api`. `uv run pytest -q tests/decision/test_providers.py tests/decision/test_provider_requests.py`: "9 passed"; `uv run mypy`: "Success: no issues found in 48 source files".
- **27.11.2026 20:43** Development agent: sub-issues `#192`–`#194` created, assigned to `qamran`, on the board and linked to `#46`. Added `langchain-typesafe==0.1.0` (`uv add`; lock adds only `langchain-typesafe`, deps `httpx2`, `langchain-core`) and the MKC-46 settings block. `uv run pytest -q tests/decision/test_settings.py`: "7 passed".
- **27.11.2026 20:37** Test agent (`dd184a2`): checked the fake end to end (a scratch script: the canned body validates; `.nouls`, `.choices`, `.model` and `seen` as the tests expect). Split the live test's imports so ruff stays green once `mkc.decision` exists. Whole backend suite `uv run pytest -q`: "26 failed, 676 passed, 1 skipped, 13 deselected" (the 26 are this lane's red tests); `uv run mypy`: "Success: no issues found in 48 source files"; every `scripts/check_*.py` exits 0.
- **27.11.2026 20:29** Test agent: red commits `1ed966f` (settings, provider factory, this file), `81fc41c` (`DecisionClient`, 229 lines: one test file and its fake), `485c89a` (guard and live tests). Red acceptance tests and the pinned interface. `uv run pytest tests/decision tests/models/test_guards.py -q`: "26 failed, 69 passed, 1 deselected"; `uv run pytest tests/decision -q`: "26 failed, 14 passed, 1 deselected". Reasons: `ModuleNotFoundError: No module named 'mkc.decision'`, `ImportError: cannot import name 'build_decision_model'`, and `Settings` without `decision_backend`/`decision_model`.
