# MKC-13 plan: Provider layer (ModelClient)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ticket:** MKC-13 (#13). **Branch:** `mkc-13-provider-layer`.

**Goal:** one interface for every model call across four providers (OpenRouter, Gemini, Anthropic, Meta API; Meta replaced the closed Llama API during the build, decision 52), with EUR cost, latency, trace hooks and record/replay.

**Architecture:** package `mkc.models`.

- Our own plain types go in and out: `Message`, `Image`, `ToolSpec`, `ToolCall`, `Usage`, `ModelReply`. Callers never see LangChain objects.
- A YAML file inside the package maps each role to a provider and model and holds the price table. It is package data, so the image has it (unlike `backend/data/`, MKC-12 finding 1).
- `ModelClient` turns our messages into LangChain messages and calls a chat model built by a provider factory:
  - `bind_tools` for tools
  - `with_structured_output` for schemas
  - Then it records usage, cost and latency, and calls the trace hooks.
- Record/replay sits in front of the factory. Replay never builds a provider client and needs no key.

**Tech stack:**

- LangChain packages, pinned with `==`:
  - `langchain-core` 1.8.5
  - `langchain-openrouter` 0.3.0
  - `langchain-google-genai` 4.5.3
  - `langchain-anthropic` 1.7.13
  - `langchain-meta` 0.5.0
- **Not** the `langchain` meta-package: it depends on `langgraph`, which the build must not contain (AGENTS.md). For the same reason there is no `init_chat_model`; the factory builds the provider classes directly.

## Facts checked (26.11.2026)

- **`ChatOpenRouter`:**
  - `openrouter_provider` is sent as the request field `provider`.
  - The SDK's `ProviderPreferences` has `zdr: bool` and `data_collection: "allow" | "deny"`.
  - The timeout is in **milliseconds** (`timeout`, mapped to `timeout_ms`).
  - The SDK client is the field `client`, so a test can swap in an SDK client whose `httpx.Client` has a `MockTransport` and assert on the real request body.
- **Other chat models:** `ChatAnthropic(timeout=<s>, api_key=...)`, `ChatGoogleGenerativeAI(google_api_key=...)`. Changed during the build: `langchain_meta.ChatLlama` is deprecated because Meta shut down the Llama API on 6 July 2026; the provider `meta` uses `ChatOpenAI` on `https://api.meta.ai/v1` (`langchain-openai`) instead.
- **Fake model:** `langchain_core` has `FakeMessagesListChatModel`, which returns given `AIMessage`s (with `tool_calls` and `usage_metadata`). It has no `bind_tools`, so the tests use a small subclass that records the bound tools.
- **Prices:** OpenRouter `GET /api/v1/endpoints/zdr` on 26.11.2026. Where a model has several ZDR endpoints, the table takes the **highest** price, so the cost is an upper bound.
- **Exchange rate:** ECB reference rate of 25.11.2026: 1 EUR = 1.0935 USD, so `eur_per_usd` = 0.9145.

## Decisions taken in this ticket (decision 52, ADR 001)

- **Structured output:** one extra method `chat_structured(role, messages, schema: type[BaseModel]) -> ModelReply`.
  - `ModelReply.parsed` holds the validated result as a plain dict.
  - The schema's JSON schema is part of the replay key.
  - Reason: the contract test needs a structured-output round-trip, and replay must store it.
- **`MKC_MODEL_MODE` defaults to `replay`,** so no code path spends money by accident. The worker sets `live` when turns run (MKC-17).
- **Replay store:** one JSON file per key in `MKC_MODEL_REPLAY_DIR`.
  - Key: sha256 over canonical JSON (sorted keys) of role, `provider:model`, messages (image bytes as sha256 digests), tools and schema.
  - The file stores the reply only: text, tool calls, parsed result, usage, model id and latency. It never stores the request text or images.
  - A missing file in replay mode raises `ReplayMiss`.
- **Unknown model:** a role mapped to a model without a price is a config error at load time. Cost is never silently 0.
- **Timeout:** at or below 180 s (decision 42); the loader refuses more.
- **API keys:** `SecretStr` settings `MKC_OPENROUTER_API_KEY`, `MKC_GOOGLE_API_KEY`, `MKC_ANTHROPIC_API_KEY` and `MKC_LLAMA_API_KEY`. They are passed to the provider class explicitly; the provider's own environment variables are not read.

## Sub-issues

### MKC-13.1: dependencies and guards

- [ ] Red test `backend/tests/models/test_guards.py`. It checks four things:
  - every `langchain*` dependency in `pyproject.toml` is pinned with `==`
  - `uv.lock` has no `langgraph` and no `langchain` meta-package
  - no module under `src/` imports `langgraph` or names `create_agent` or `AgentExecutor`, checked by parsing the code with the `ast` module
  - provider packages (`langchain_openrouter`, `langchain_anthropic`, `langchain_google_genai`, `langchain_meta`, `openai`, `anthropic`, `google.genai`, `openrouter`, `llama_api_client`) are imported only in `src/mkc/models/providers.py`
- [ ] Commit `pyproject.toml` + `uv.lock` on their own. The lock diff is large: this is the one commit allowed over 200 lines.
- [ ] Green; push and watch `dependency-scan`, `image` and `kind`.

### MKC-13.2: types, role config and settings

- [ ] `mkc/models/types.py`:
  - `Role`, `Message`, `Image`, `ToolSpec` (name, description, Pydantic args model)
  - `ToolCall`, `Usage(input_tokens, output_tokens, cost_eur)`
  - `ModelReply(text, tool_calls, usage, model_id, latency_ms, parsed)`
  - `ReplayMiss`, `ModelConfigError`
- [ ] `mkc/models/models.yaml` and `mkc/models/config.py`. The loader `load_models_config(path) -> ModelsConfig` checks:
  - every role is mapped
  - the provider is known
  - every mapped model and every contract model has a price
  - `timeout_seconds` is at most 180
  - `cost_eur(model, usage)` uses the USD prices × `eur_per_usd`
- [ ] Settings: `model_mode`, `models_file`, `model_replay_dir` and the four keys; `.env.example` lists them.
- [ ] Tests first for each check.

### MKC-13.3: ModelClient over a fake model

- [ ] `ModelClient(config, settings, factory, tracers)` with `chat`, `chat_with_tools`, `vision` and `chat_structured`.
- [ ] Tests with the fake model:
  - text reply
  - tool calls are mapped
  - tools are bound from Pydantic models
  - images become content blocks
  - structured output is parsed
  - cost comes from the price table
  - latency is measured
  - each tracer gets one `CallTrace` per call, also on errors

### MKC-13.4: record/replay

- [ ] `ReplayStore` and the key function.
- [ ] Tests:
  - the key is stable and changes with each input part
  - record writes, and replay returns the same `ModelReply`
  - a replay miss raises `ReplayMiss`
  - replay never calls the factory
  - stored files hold no message text

### MKC-13.5: provider factory with zero data retention

- [ ] `mkc/models/providers.py`: `build_chat_model(provider, model, settings, timeout)` for the four providers.
- [ ] OpenRouter gets `openrouter_provider={"zdr": True, "data_collection": "deny"}`.
- [ ] Tests:
  - a request through the real `ChatOpenRouter` with a mock transport carries `provider.zdr = true` and `provider.data_collection = "deny"`, and its timeout in milliseconds
  - a missing key raises a clear error
  - the other three classes get the key and the timeout

### MKC-13.6: live contract tests and docs

- [ ] Register the `live` marker; it is deselected by default (`-m "not live"` in `addopts`).
- [ ] `tests/models/test_contract_live.py`: per provider, one tool-call round-trip and one structured-output round-trip through `ModelClient` in `live` mode. Skip when the key is missing.
- [ ] Run once with the user's keys. Note the result and the spend in the status doc.
- [ ] Docs:
  - decision 52 in the design doc
  - ADR 001 consequences
  - status doc
  - runbook inventory (the four keys live in `backend/.env` locally)
  - HANDOFF

## Success criteria (ticket)

- [ ] Role → provider/model mapping is in config, not code (13.2).
- [ ] LangChain packages are pinned; agent APIs are not imported anywhere, and a test enforces it (13.1).
- [ ] Live contract tests pass for OpenRouter, Gemini, Anthropic and the Meta API; run once, with the result in the status doc (13.6; needs the user's keys).
