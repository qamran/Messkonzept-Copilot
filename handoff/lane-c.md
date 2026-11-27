# Lane C: Decision layer

**Last updated:** 27.11.2026, 20:28

Only lane C's agents write this file; the coordinator keeps `HANDOFF.md`. Times are local time (CET) from git and GitHub, never estimated.

- **Tickets, in order:** `MKC-46` → `MKC-47` (after MKC-36, MKC-26) → `MKC-48` (after MKC-31)
- **Branch and worktree:** `mkc-46-decision-spike`
- **Owns:** `mkc/decision/` and `tests/decision/`; one function appended at the end of `mkc/models/providers.py`; one appended block in `config.py`
- **Decision numbers:** 68–70

## In progress

- `MKC-46` (`#46`), decision-layer spike: the test agent's red acceptance tests are committed in `backend/tests/decision/` (see "Recent log" for the commit). The development agent builds next.

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

- `tests/decision/test_client.py` (14), `test_settings.py` (7), `test_providers.py` (5): red.
- `tests/decision/test_guards.py` (14): green today; it keeps `langchain_typesafe` and `httpx2` imports inside `providers.py`.
- `tests/decision/test_jev_live.py` (1, `@pytest.mark.live`): deselected by default; not run by the test agent.
- `tests/decision/fakes.py`: `FakeDecisionModel`, a `BaseDecisionModel` that replays a canned `ClassifierResponse` (the offline transport).

### Notes for the development agent

- Add `langchain-typesafe==0.1.0` (pinned with `==`; `test_repo_langchain_dependencies_are_pinned`) and say so in the PR; the coordinator runs `uv lock`. Do **not** add the `experimental` extra: it pulls in `langchain`, which the lock guard forbids.
- `langchain-typesafe` 0.1.0 re-exports its types from `langchain_core.decisions` (in `langchain-core==1.8.5`), so `mkc/decision/` imports only `langchain_core.decisions`.
- `TypeSafeClassifier` POSTs to `{base_url}/v1/systemone` with `Authorization: Bearer <key>`; it accepts a `client: httpx2.Client` for tests.
- In `test_jev_live.py`, ruff sorted `mkc.models.providers` into its own import group while `mkc.decision` did not exist; once the package exists, `uv run ruff check --fix tests/decision/test_jev_live.py` merges it (an import-order change only).
- The live run needs the coordinator's go (budget); record the spend and the result in ADR 004 and the status doc.

### Open questions (test agent's assumptions)

1. **Package name:** the MKC-47 interface line in the backlog says `mkc.decisions.client.DecisionClient`; the lane table and this lane use `mkc.decision`. Assumed `mkc.decision`; the backlog line needs a fix.
2. **Shared guard list:** `tests/models/guards.py` `PROVIDER_MODULES` lacks `langchain_typesafe` and `httpx2`; this lane checks them in `tests/decision/test_guards.py`. The coordinator may add them to the shared list.
3. **LLM fallback scope:** only the default setting is pinned here. The fallback backend itself is MKC-47 (feature 66); it needs a model role (no `decide` role in `Role` or `models.yaml`), which is coordinator-owned.
4. **`json_schema`:** ADR 004 says the fallback uses `method="json_schema"`, but `ModelClient.chat_structured` passes no method (LangChain's default). Not pinned; for MKC-47.

## Next steps

1. Development agent: build `mkc/decision/`, `build_decision_model`, the settings block and the dependency until the red tests are green; then the live spike with the coordinator's go.
2. Development agent: write the result into ADR 004, the status doc and the decision log (numbers 68–70).
3. Test agent: mutation pass on the development agent's code, then report the surviving mutants.

## Recent log

- **27.11.2026 20:28** Test agent: red commits `1ed966f` (settings, provider factory, this file), `81fc41c` (`DecisionClient`, 229 lines: one test file and its fake), and the guard and live tests in the commit that adds this line. Red acceptance tests and the pinned interface. `uv run pytest tests/decision tests/models/test_guards.py -q`: "26 failed, 69 passed, 1 deselected"; `uv run pytest tests/decision -q`: "26 failed, 14 passed, 1 deselected". Reasons: `ModuleNotFoundError: No module named 'mkc.decision'`, `ImportError: cannot import name 'build_decision_model'`, and `Settings` without `decision_backend`/`decision_model`.
