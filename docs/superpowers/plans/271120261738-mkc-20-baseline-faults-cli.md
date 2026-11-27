# MKC-20 plan: Baseline mode, failure injection and CLI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ticket:** MKC-20 (#20). **Branch:** `mkc-20-baseline-cli`.

**Goal:** the same harness can run as the simple loop, faults can be injected on purpose, and runs are controllable from a CLI.

**Spec:** design doc 8.5 ("Baseline"), section 12 (E4 row), features 24, 25 and 26; backlog entry MKC-20; the review findings tagged MKC-20 in HANDOFF (19#1, 19#2, 19#3) and MKC-18 finding 2 (resume of a `stopped` run).

**Architecture:**

- `mkc.harness.mode` (new): `HarnessMode` (`full`, `baseline`) and `Switches` with exactly the five switches of design 8.5. `full` has all on, `baseline` all off.
- `mkc.harness.loop` (change): `run_item` and `process_run` take `switches` and an optional `memory`. With checkpoints and the durable queue off, the loop keeps turns, claims and end states in a `RunMemory` and writes them only when the run ends. It is the same loop, not a second one (design section 4, "Baseline comparison").
- `mkc.harness.baseline` (new): `RunMemory` (turns, end states, in-memory approvals, usage) and the in-memory `save_draft`.
- `mkc.harness.runner` (new): `execute_run(run_id, ...)` reads `run.mode`, builds the registry and memory for that mode, and calls `process_run`. The executor and the CLI both use it.
- `mkc.harness.faults` (new): `FaultPlan`, `load_fault_plans(path)`, `FaultInjector` with three hooks the loop calls (model call, tool call, item end), and `InjectedKill(BaseException)`.
- `mkc.cli` (new, Typer): `mkc run start|resume|status|inspect`.
- `mkc.observability` (change): MKC-19 findings 1 to 3.

## Global constraints

- Migrations are additive only (decision 48). `0011_run_mode` adds `run.mode` (text, not null, server default `full`).
- Every model call goes through `ModelClient`. Fault hooks wrap the callable given to `call_model`, so backoff and the re-prompt run as they would for a real fault.
- A fault plan never comes from an environment setting. The CLI (`--faults FILE --plan NAME`) or a test passes it explicitly, so a production worker can't inject faults.
- Run state writes only through `transition` (decision 54). The new edge `stopped -> running` is in `EDGES`, and `stopped` is no longer terminal.
- Typer is pinned with `==` in `backend/pyproject.toml` and `uv.lock`, and gets the script entry `mkc = "mkc.cli:app"`.
- Commits under 200 lines. A red test comes before its code and fails on an assertion, not an `ImportError`. HANDOFF goes in every commit, with clock times from git. No blank line between `Refs:` and `Co-Authored-By:`. `Refs: qamran/...` is checked before every push. Each sub-issue is `In progress` before its first commit.

## Decisions taken in this ticket

### Decision 60: baseline, faults and the CLI (taken by the development agent)

1. **Baseline is the full loop with five switches off.** The switches are `checkpoints`, `tool_cache`, `durable_queue`, `idempotency` and `durable_approvals`; a config test pins that list. Everything else is identical in both modes, asserted by a config test: limits (including the one corrective re-prompt), tools and their specs, the system prompt, the model role, retries and tracing. The note in `Limits` that baseline sets `max_reprompts` to 0 is wrong: the re-prompt is not one of the switches, and the note is removed.
2. **What "off" means:**
   - `checkpoints` off: no `turn` rows. Every item starts from its task, and there is no resume context.
   - `tool_cache` off: no `tool_cache` lookups or writes.
   - `durable_queue` off: the run's open items are read once at the start. Claims and end states stay in memory and are written in one transaction only when the run ends: it settles, or a run limit or setup error stops it. A crash or SIGTERM before that writes nothing, so the next attempt restarts from zero. `checkpoints` on needs `durable_queue` on (turn rows without durable claims would clash on a restart), and `Switches` refuses that mix.
   - `idempotency` and `durable_approvals` off: `save_draft` appends to an in-memory list in `RunMemory.approvals`, with no key and no `draft` row. A second save adds a second entry. The run ends `awaiting_approval` as in full mode, but the drafts die with the process.
3. **What stays durable in baseline:** the `run` and `item` rows that define the work, the lease, the end report, and tracing (`run_log`, Langfuse). E4 and `mkc run status` need them.
4. **Run limits in baseline** come from `RunMemory.usage()`: turns and cost in memory, and wall time on a monotonic clock since the attempt began. So baseline stops at the same limits as full.
5. **The mode belongs to the run.** `run.mode` is set when the run is created, from `--mode` or `MKC_HARNESS_MODE` (default `full`). The worker runs each run in its own mode.
6. **Fault plan:** `FaultPlan(timeout_at, rate_limit_at, malformed_at, kill_at_turn, kill_during_approval)`. Each field is a 1-based count or None, and each fault fires once per injector, which means once per process.
   - `timeout_at=n`: the n-th tool call times out. It returns `{"ok": false, "error": {"code": "timeout"}}` without running, and counts as a tool failure. This is the "tool timeout" of the E4 row; tools get real deadlines in MKC-22.
   - `rate_limit_at=n`: the n-th model call attempt raises `TransientModelError` (a 429, `retry_after=None`) before reaching the client, so `call_model` backs off and retries.
   - `malformed_at=n`: the n-th model call attempt returns a reply with text and no tool call, at zero cost, without reaching the client, so the re-prompt path runs.
   - `kill_at_turn=n`: the n-th model call attempt reaches the client, then `InjectedKill` is raised before its results are stored. The turn in flight is lost and billed, like a real kill.
   - `kill_during_approval=n`: `InjectedKill` is raised right after the n-th item ends `draft_saved` (approvals come in MKC-23; until then a saved draft is the pending approval). In full mode that end state is committed first; in baseline it is only in memory.
   - `InjectedKill` is a `BaseException`, so the loop's `except Exception` never catches it, and `with_deadline` passes it on. Outside tests, the CLI turns it into exit code 137 and releases the lease, so `mkc run resume` can continue at once. The lease expiry after a real kill is already tested (MKC-17).
   - YAML: `load_fault_plans(path) -> dict[str, FaultPlan]` reads a mapping of name to plan, with unknown keys refused. `backend/data/e4_faults.yaml` holds one plan per fault type for E4.
7. **Replay and faults (for MKC-32):** a re-prompt, a faulted tool result or a resume context changes the next request, so its replay key differs from a no-fault recording. E4 must record each fault arm once (`record` mode) before it can replay it; a `ReplayMiss` stops the run with `setup_error`. Noted in the backlog under MKC-32.
8. **CLI:**
   - `mkc run start --items FILE [--mode full|baseline] [--inline] [--faults FILE --plan NAME]`. The items file is synthetic YAML until MKC-21 brings `fetch_document` and `segment_document`: a list of `{concept_key, document_hash, task}`. `start` creates the run (`running`, with its mode) and its `queued` items, and prints the run id.
   - Without `--inline`, the worker picks the run up. With `--inline`, the CLI claims that run with a lease (owner `cli-<host>-<pid>-<random>`) and processes it in-process through the executor. A worker can't take the run meanwhile, and no heartbeat file is touched.
   - `mkc run resume RUN_ID [--inline ...]`: a `stopped` run goes back to `running` (new edge). `stop_reason` and `started_at` are cleared, so the wall-time limit counts from the resume, while steps and cost keep counting from the stored turns. A `running` or `waiting_for_database` run is left as it is. A `done` or `awaiting_approval` run is refused (exit code 1).
   - `mkc run status RUN_ID`: state, mode, stop reason, items per state, usage (steps, cost, wall time) and lease.
   - `mkc run inspect RUN_ID [--item ID]`: one line per item (state, failure reason, turns, cost), the run's latest 20 `run_log` rows, and with `--item` that item's turns (tool names and `ok` flags only).
9. **MKC-19 findings:** Langfuse gets only the error class (and HTTP status, if any) as `status_message`, while `run_log` keeps the text cut to 500 characters (finding 1). Stop details cut tool names at 100. With no trace id, the sink is skipped and only `run_log` records (finding 2). `span_*` build their record inside the tracer's guard, and `_trace_ids` drops a run's entry after `flush` (finding 3).

## Sub-issues

As built:

- `execute_run` takes `tool_tracers` and builds the registry per run and mode; the executor no longer holds one registry (`Executor(registry=None)`), so `test_build_executor_wires_one_tracer` now checks `_tool_hooks`. `test_execute_run_builds_the_registry_with_the_tool_hooks` pins that the hooks still reach every tool call.
- The executor takes `faults=` and `run_once(run_id)`; `build_executor` takes `make_client` and passes other options to the executor; the CLI uses it, so inline runs are traced like worker runs.
- An injected tool timeout never reaches the registry, so it has no `ToolTrace` (noted for MKC-32).
- `settle_run` leaves a `stopped` run alone explicitly, since `stopped` left `TERMINAL`.
- The two pins of review focus 1 and 3 passed on their first run: they pin behaviour built in MKC-20.2. Review focus 2, 4 and 5 are CLI tests (`test_resume_after_a_cost_stop_stops_again`, `test_start_refuses_a_bad_items_file`, `test_inline_on_a_leased_run_refuses`).
- Some red tests failed on a missing attribute or argument (`public_error`), not an assertion (MKC-20.5).

### MKC-20.1: harness mode and its switches

- **Files:** `src/mkc/harness/mode.py` (new), `src/mkc/config.py` (`harness_mode: HarnessMode = full`), `migrations/versions/0011_run_mode.py`, `src/mkc/db/models.py` (`Run.mode`), `tests/harness/test_mode.py`, `.env.example`, `harness/limits.py` docstring.
- **Produces:** `HarnessMode(StrEnum)`, `Switches(checkpoints, tool_cache, durable_queue, idempotency, durable_approvals)` (frozen; `__post_init__` refuses `checkpoints and not durable_queue`), `SWITCHES: Mapping[HarnessMode, Switches]`, `DOCUMENTED_SWITCHES` (the five names in design order).
- [x] Red: `test_switches_are_the_documented_five` (field names == `DOCUMENTED_SWITCHES`); `test_full_all_on_baseline_all_off`; `test_checkpoints_need_durable_queue`; `test_modes_share_everything_else`: two `Settings` differing only in `harness_mode` give equal `Limits.from_settings`, equal `[t.to_spec() for t in default_registry().for_context("item")]`, and the same `SYSTEM_PROMPT` and `ROLE`; `test_settings_differ_only_by_mode` (`model_dump()` diff == `{"harness_mode"}`); migration test: `run.mode` defaults to `full`.
- [x] Code: as above.

### MKC-20.2: baseline in the loop

- **Files:** `src/mkc/harness/baseline.py` (new), `src/mkc/harness/loop.py`, `src/mkc/harness/runner.py` (new), `src/mkc/worker/executor.py`, `tests/harness/test_baseline.py`.
- **Produces:**
  - `RunMemory(run_id)`: `.todo: list[int]`, `.turns: dict[int, list[TurnRecord]]`, `.ends: dict[int, tuple[ItemState, str | None]]`, `.approvals: list[dict]`, `.usage() -> RunUsage`, `.write_report(session, fence) -> None` (items `queued -> running -> end`, failure reasons; no drafts)
  - `make_memory_save_draft(memory) -> fn`
  - `process_run(..., switches=SWITCHES[FULL], memory=None, faults=None)` and the same keywords on `run_item`
  - `execute_run(run_id, *, session, client, sessions, limits, tool_tracers, stop_tracers, faults=None, **loop_kw) -> list[ItemOutcome]`
- [x] Red, in `tests/harness/test_baseline.py`, with the fake model of `test_loop.py`:
  - `test_baseline_crash_restarts_from_zero`: two items, `Crash` on the third call. No `turn` rows, items still `queued`, run `running`. A second `process_run` calls the model for item 1 again, and both items end.
  - `test_baseline_holds_approvals_in_memory_only`: save on both items. The run ends `awaiting_approval`, the items end `draft_saved`, the `draft` table is empty, `memory.approvals` has 2 entries, and a fresh `RunMemory` has none.
  - `test_baseline_saves_twice_without_a_key`: two saves of one item give two entries.
  - `test_baseline_stops_at_the_run_step_limit`: `max_steps_run=2` gives `stopped` with `run_step_limit`, the report written, and no turn rows.
  - `test_baseline_sends_the_same_requests_as_full`: the same no-fault script gives equal `model.seen` in both modes.
  - `test_baseline_skips_the_tool_cache`: no `tool_cache` rows with a `code_version` set.
  - `test_executor_runs_each_run_in_its_mode`: a `baseline` run under the executor writes no turns.
- [x] Code: the switches in `run_item`, `_Ctx`, `_run_limit` and `process_run`; `RunMemory`; `execute_run`; the executor calls `execute_run`.

### MKC-20.3: failure injection

- **Files:** `src/mkc/harness/faults.py` (new), `src/mkc/harness/loop.py` (three hook calls), `backend/data/e4_faults.yaml`, `tests/harness/test_faults.py`.
- **Produces:** `FaultPlan` (pydantic, frozen, `extra="forbid"`, fields `int | None` with `ge=1`), `load_fault_plans(path) -> dict[str, FaultPlan]`, `InjectedKill(BaseException)`, `FaultInjector(plan)` with `.model(fn) -> fn`, `.tool(call) -> ToolResult | None`, `.item_ended(outcome) -> None`, `.fired: list[str]`.
- [x] Red, one test per fault type:
  - `test_rate_limit_is_retried` (one backoff, item saves)
  - `test_tool_timeout_counts_as_a_tool_failure` (`ok: false`, code `timeout`, tool not run)
  - `test_malformed_reply_gets_the_reprompt` (re-prompt sent; item saves)
  - `test_kill_at_turn_resumes_in_full` (turn k lost; resume continues at k; no duplicate turn)
  - `test_kill_at_turn_restarts_baseline_from_zero`
  - `test_kill_during_approval_keeps_the_draft_in_full` (item stays `draft_saved`, not redone)
  - `test_kill_during_approval_loses_the_draft_in_baseline`
  - `test_each_fault_fires_once`
  - `test_fault_plans_load_from_yaml` (the E4 file: one plan per type; unknown keys and 0 are refused)
- [x] Code: as above.

### MKC-20.4: the CLI

- **Files:** `pyproject.toml` (`typer==<current>`, script `mkc`), `uv.lock`, `src/mkc/cli.py` (new), `src/mkc/harness/states.py` (edge `stopped -> running`; `stopped` leaves `TERMINAL`), `src/mkc/worker/lease.py` (`claim_run(..., run_id=None)`), `src/mkc/worker/executor.py` (`run_once(run_id=None)`, `faults=`), `tests/test_cli.py`, the state tests.
- [x] Red, using Typer's `CliRunner` against the test database:
  - `test_start_creates_a_queued_run` (prints the id; mode from the setting or `--mode`)
  - `test_start_inline_runs_it` (replay or fake client factory; the run ends)
  - `test_start_inline_with_a_kill_exits_137_and_resume_finishes`
  - `test_resume_restarts_a_stopped_run` (state `running`, `stop_reason` and `started_at` cleared)
  - `test_resume_refuses_a_done_run`
  - `test_status_shows_state_items_usage`
  - `test_inspect_lists_items_and_log`
  - `test_claim_run_by_id_takes_only_that_run`
  - edge test for `stopped -> running`
- [x] Code: as above. A client factory seam in `mkc.cli` (`client_factory = ModelClient.from_settings`) lets tests pass a fake.

### MKC-20.5: tracing findings of the PR #161 review

- **Files:** `src/mkc/observability/trace.py`, `src/mkc/observability/langfuse.py`, `src/mkc/harness/loop.py` (stop detail cut), `tests/observability/`.
- [x] Red: `test_langfuse_gets_only_the_error_class` (a `ModelError` whose text quotes a prompt: the sink's `status_message` has no prompt text, and `run_log.error` keeps the text); `test_stop_detail_cuts_tool_names_at_100`; `test_no_trace_id_skips_the_sink`; `test_span_record_errors_stay_inside_the_tracer`; `test_trace_id_cache_is_dropped_after_flush`.
- [x] Code: as decision 60 point 9.

### Docs (with the last sub-issue)

- Design: decision 60 in section 18; 8.2 (edge `stopped -> running`, `run.mode`); 8.5 "Built in MKC-20".
- Runbook section "Baseline, faults and the CLI" (settings, commands, E4 file, replay note), checked by `check_runbook.py`.
- Status doc, backlog notes on MKC-20 (as built) and MKC-32 (replay of fault arms), HANDOFF; ADR 001 or 002 only if a harness ADR names the baseline.

## Review focus

1. A baseline run interrupted by SIGTERM mid-item writes nothing. The next claim must restart from zero, not resume. Covered by the crash test through `should_stop` (add `test_baseline_sigterm_writes_nothing`).
2. A stopped run resumed after a cost stop stops again at once with `cost_limit`. This is expected, and `resume` must print the reason (`test_resume_after_cost_stop_stops_again`).
3. A baseline run left `running` in the database (from a full-mode item) must not crash the memory queue. `todo` takes `queued` and `running` items alike (`test_baseline_takes_running_items_too`).
4. A malformed YAML items file or fault file gives a clear exit code 2 and message, not a traceback (`test_start_refuses_a_bad_items_file`).
5. `--inline` while a worker holds the run: the claim finds nothing and the CLI says so, with exit code 1 (`test_inline_on_a_leased_run_refuses`).
