# MKC-14 plan: Tool registry and per-context allow-lists

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ticket:** MKC-14 (#14). **Branch:** `mkc-14-tool-registry`.

**Goal:** the model can only call allow-listed tools with validated arguments; everything else becomes a structured error that is counted in the trace.

**Architecture:** package `mkc.harness`, module `mkc.harness.tools`.

- `Tool(name, description, args_model, fn, side_effect, deterministic)`: a frozen dataclass. `description` is an addition to the ticket interface: `ModelClient.chat_with_tools` takes `ToolSpec(name, description, args)`, so `Tool.to_spec()` needs it.
- `ToolError(code, message)` and `ToolResult(ok, data, error)`: frozen Pydantic models. `ok=True` needs `data` and no `error`; `ok=False` needs `error` and no `data`. Both rules are enforced by a validator.
- `ToolRegistry(item=[...], run=[...], tracers=[...])`:
  - built once; no method adds a tool later; `for_context` returns a tuple (immutable)
  - construction refuses a `side_effect=True` tool in the item context, a duplicate name, or a name in both contexts
  - `execute(call: ToolCall, ctx) -> ToolResult`, in this order:
    1. unknown name → `unknown_tool`
    2. known, but not in this context → `tool_not_allowed`, the function is not called
    3. arguments fail the Pydantic model → `invalid_args` (the Pydantic error list, trimmed)
    4. the function raises → `tool_failed` (the exception does not propagate)
    5. otherwise `ok=True`, `data` = what the function returned
  - every call sends a `ToolTrace(tool, ctx, ok, error_code, refused, latency_ms)` to each tracer. `refused` is true for `unknown_tool` and `tool_not_allowed` only. A failing tracer is logged and never breaks the call (same as `ModelClient`).
- `ToolTracer = Callable[[ToolTrace], None]` is the stub the ticket allows until MKC-19. MKC-19's `Tracer.span_tool` can wrap it.
- `mkc.harness.registry.default_registry()`: the six item tools of design 8.1 and the four run-level operations. Their real functions come in MKC-21, 22, 23, 26 and 28; until then each placeholder raises `NotImplementedError`, which `execute` returns as the structured error `not_implemented`. Nothing fakes success.

## Decision taken in this ticket (decision 53, ADR 001)

**What `side_effect` means.** A tool has a side effect when it reaches outside its own item: the network, the catalogue, the approval queue, or any state that a re-run with the same arguments cannot overwrite by key.

- `save_draft` writes only its own item's draft, keyed by (document hash, concept number), idempotent (MKC-16). So it is `side_effect=False` and may be in the item context.
- The approval enqueue is the run-level operation `enqueue_approval`, run by harness code on `save_draft`'s result (design 8.1: "Code (side effect of `save_draft`)"). MKC-23 builds it that way.
- Reason: the design table already puts the enqueue in code, and AGENTS.md says the model never gets side-effect tools. This reading satisfies both.

## Placeholder argument models

The owning tickets replace these. They follow the backlog signatures and are kept small on purpose.

| Tool | Context | Args | `deterministic` | Owner |
|---|---|---|---|---|
| `extract_text` | item | `page: int ≥ 1` | yes | MKC-22 |
| `extract_tables` | item | `kind: "meter_tech" \| "lbs"` | yes | MKC-22 |
| `render_region` | item | `page ≥ 1`, `bbox` (4 floats), `dpi ≥ 1` | yes | MKC-23 |
| `read_diagram` | item | `image_ref: str` | no | MKC-26 |
| `validate_draft` | item | `draft: dict` | yes | MKC-28 |
| `save_draft` | item | `draft: dict` | no | MKC-23 |
| `fetch_document` | run | `operator_id: str` | no | MKC-21 |
| `segment_document` | run | `document_hash: str` | yes | MKC-21 |
| `enqueue_approval` | run | `draft_id: str` | no | MKC-23 |
| `commit_record` | run | `draft_id: str` | no | MKC-29 |

Run-level operations are `side_effect=True` except `segment_document` (it only reads the cached document; it is run-level because it is a code step, design 8.1).

## Sub-issues

### MKC-14.1: tool types and registry core

- [ ] Skeleton (empty classes) so the red tests fail on assertions, not on `ImportError`
- [ ] Red tests `backend/tests/harness/test_tools.py`:
  - `test_unknown_tool_returns_structured_error`
  - `test_run_level_tool_requested_in_item_context_is_refused_and_not_executed` (spy with plausible arguments; zero calls; Review Focus 5)
  - `test_invalid_args_return_validation_error`
  - `test_tool_exception_becomes_structured_error`
  - `test_refusals_are_counted_in_the_trace` (unknown and not-allowed count; invalid args do not)
  - `test_side_effect_tool_cannot_be_registered_in_item_context`
  - `test_duplicate_names_are_refused`, `test_registry_cannot_be_extended`
  - `test_tool_result_needs_exactly_one_of_data_and_error`
  - `test_to_spec_matches_model_client_tool_spec`
- [ ] Code until green; ruff, mypy strict

### MKC-14.2: default registry (design 8.1)

- [ ] Red tests `backend/tests/harness/test_registry.py`:
  - `test_item_context_exposes_exactly_the_six_tools`
  - `test_item_context_exposes_no_side_effect_tools`
  - `test_run_context_holds_the_four_run_level_operations`
  - `test_placeholders_return_not_implemented`
- [ ] Code until green

### MKC-14.3: docs

- [ ] Decision 53 in the design doc (section 18), ADR 001, the status doc, HANDOFF (note for MKC-23)
