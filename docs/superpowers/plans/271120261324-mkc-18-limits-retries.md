# MKC-18 plan: Limits and retries

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ticket:** MKC-18 (#18). **Branch:** `mkc-18-limits-retries`.

**Goal:** runs stop cleanly at step, time, cost and retry limits; transient errors are retried sensibly.

**Spec:** design doc section 8.5 (limits, retries), 8.2 (states), features 21 and 22; backlog notes on MKC-18; the review findings tagged MKC-18 in HANDOFF.

**Architecture:**

- `mkc.harness.limits` (new):
  - `Limits(max_steps_item, max_steps_run, max_wall_s, max_cost_eur, max_retries_tool, ...)`, frozen, with `Limits.from_settings(settings)`
  - `StopReason` (StrEnum), `StopEvent` and `StopTracer` (the trace of every stop)
  - `run_usage(session, run_id) -> RunUsage` and `run_limit_hit(usage, limits) -> StopReason | None`
  - `stop_run(session, run_id, reason, *, detail, fence, tracers)`: the one writer of a run stop
- `mkc.harness.retry` (new): `call_model(fn, *, limits, sleep, should_stop)`: the turn deadline, backoff and retries
- `mkc.models` (change): `TransientModelError(retry_after)` and `ModelAuthError`; `ModelClient` maps provider errors to them with a classifier from `providers.py`
- `mkc.harness.loop` (change): `run_item` and `process_run` take `limits` instead of `max_steps`, plus `sleep` and `tracers`
- `mkc.worker.executor` (change): builds `Limits` from settings; writes the stop itself when the client can't be built; the holes of finding 17#6 closed

## Global constraints

- Migrations are additive only (decision 48): `0009_limits` adds `run.started_at` (nullable) and `item.attempts_without_progress` (integer, server default 0).
- Every state write goes through `transition` (decision 54). No new edge: `running -> stopped` exists.
- No transaction stays open across a model call; the limit query commits before it.
- Counts come from the database (`turn` rows, the run row), never from memory: `process_run` is re-entered after SIGTERM, a crash or an outage.
- Commits under 200 lines; a red test before its code, failing on an assertion, not an `ImportError`; HANDOFF in every commit with clock times from git; no blank line between `Refs:` and `Co-Authored-By:`; each sub-issue `In progress` before its first commit.

## Decisions taken in this ticket

### Decision 58: limits, stop reasons, retries (taken by the development agent)

1. **Stop reasons.** One `StopReason` enum, stored as its value:
   - item level, in `item.failure_reason` (the item goes `failed`):
     - `step_limit`: the item used `max_steps_item` model calls
     - `tool_retries`: one tool failed more than `max_retries_tool` times in the item
     - `malformed_output`: a reply without a tool call, after one corrective re-prompt
     - `resume_limit`: the item was resumed `max_resumes_item` times without a new turn
     - `model_error: <class>` and `tool_error: <class>`: a non-transient error (unchanged)
   - run level, in `run.stop_reason` (the run goes `stopped`):
     - `run_step_limit`, `wall_time`, `cost_limit`: the run limits
     - `setup_error`: a missing key or setting, a replay miss, a 401 or 402 (refused key, no credits: they would fail every item the same way, finding 15#6); a 403 is not one (on OpenRouter it can be a moderation flag on one input) and fails only its item
     - `model_unavailable`: a transient error (429, 5xx, timeout, network) that outlived every retry
2. **The trace.** Every stop, run or item, calls the `StopTracer` hooks with a `StopEvent(scope, run_id, item_id, reason, detail, steps, cost_eur)`, shaped like `CallTrace` and `ToolTrace`, and logs one line. MKC-19 sends it to Langfuse and `run_log`. "The run record and the trace" in the criteria means: the column above, and this event. Each per-limit test asserts both.
3. **A run stop leaves the work as it is.** The item in flight stays `running` with its checkpoint; queued items stay `queued` (design 8.2 notes). A later resume of a stopped run (the Runs page has resume buttons, design 9) can continue from there. `stopped` is terminal until that ticket adds an edge.
4. **Run usage is counted from the database**, before every model call:
   - steps = the run's `turn` rows; cost = the sum of their `cost_eur`
   - wall time = database `now()` minus `run.started_at`, which `process_run` sets on its first entry (not `created_at`: a run may wait in the queue). It includes outages and resumes: a run that waits out a long outage stops on wall time.
   - A model call that raises writes no turn row, so its cost is not counted, and its `CallTrace` has no usage, so it is recorded nowhere (only a call abandoned at the deadline that later returns is traced with usage). The cost limit can be overshot by one call. Both known limits.
5. **Retries of model calls** (`mkc.harness.retry`):
   - only `TransientModelError`, which `ModelClient` raises for HTTP 408, 429, 5xx and 529, network and timeout errors, and the turn deadline
   - wait = `max(Retry-After, backoff_base_s × 2^attempt)`, capped at `backoff_max_s`; no jitter (one worker per run)
   - `should_stop` is checked before each wait and each attempt, and the wait sleeps on the executor's stop flag, so SIGTERM ends it
   - after `max_retries_model` retries: run stop `model_unavailable`
   - every other model error fails the item (`model_error: <class>`); `ModelAuthError` and the setup errors stop the run (`setup_error`)
6. **Turn deadline.** The model call runs in a helper thread; after `turn_timeout_s` the loop stops waiting and treats it as a transient timeout. A thread can't be killed: the abandoned call may still finish and bill, and that cost is lost from `turn.cost_eur`. This closes MKC-13 finding 3 and finding 17#7.
7. **Malformed output** (feature 22): a reply with no tool call is stored as a turn with no results; the next request adds one corrective user message. A second such reply in the item fails it with `malformed_output`. "Re-prompt used" is read from the stored turns, and `load_resume_context` adds the corrective message when the last turn has no calls, so a resume keeps it.
8. **Tool retries.** Per item and per tool name, every result with `ok: false` counts (all error codes, refusals too), in total, not consecutively, read from stored turns plus the current one. The item fails when one tool's count goes over `max_retries_tool`.
9. **Resume cap.** `item.attempts_without_progress` goes up by one in the fenced commit that picks a `running` item to resume, and back to 0 with every stored turn. Over `max_resumes_item` the item fails with `resume_limit`. Deploys never add up: a resume after a stored turn counts 1 and the next stored turn sets it to 0 (`test_deploys_never_accumulate_resume_attempts`). A SIGTERM during a backoff or an outage before the item's first stored turn does count; a crash loop before the first stored turn ends. This also closes finding 16#2.
10. **The executor writes the stop when the client can't be built** (`ModelClient.from_settings` raises before `process_run` starts): it calls `stop_run(setup_error)`, fenced, then releases the lease. A run stopped this way is never claimed again (claim takes only `running` and `waiting_for_database`).
11. **Finding 15#9** (`next_item` does not lock the run row): the claim commit is fenced, and `fence` locks the run row, so the worker can't claim an item of a run it no longer holds. A stop written by the API (a later ticket) needs the same lock; re-deferred to that ticket.

### Defaults (success criterion 2)

| Setting | Default | Why |
|---|---|---|
| `MKC_ITEM_MAX_STEPS` | 12 | MKC-15: one concept needs about 5 to 8 calls (read pages, render, save); 12 leaves room for one correction round |
| `MKC_RUN_MAX_STEPS` | 300 | a document has up to about 20 concepts × 12 steps = 240; 300 stops a runaway run first |
| `MKC_RUN_MAX_WALL_SECONDS` | 7200 | 300 steps at about 20 s each is 100 minutes; 2 hours also covers a short outage |
| `MKC_RUN_MAX_COST_EUR` | 3.00 | the LLM budget is €20–30 in total; one runaway run may cost at most about 10 % of it |
| `MKC_TOOL_MAX_RETRIES` | 3 | three corrections per tool, then the model is stuck on it |
| `MKC_MODEL_MAX_RETRIES` | 4 | waits of 2, 4, 8 and 16 s (30 s in all) ride out a short 429 or 5xx burst |
| `MKC_MODEL_BACKOFF_BASE_SECONDS` | 2 | first wait |
| `MKC_MODEL_BACKOFF_MAX_SECONDS` | 60 | caps a long `Retry-After`; under the 120 s lease, which the lease thread renews anyway |
| `MKC_TURN_TIMEOUT_SECONDS` | 180 | the worker's turn budget (decision 42; `models.yaml` says "at most 180 s"), under the 300 s grace period |
| `MKC_ITEM_MAX_RESUMES` | 3 | three crashes in a row with no new turn means the item itself is the problem |

The re-prompt count (1) is fixed by feature 22 but stays a `Limits` field (`max_reprompts`), so MKC-20's baseline mode can switch retries and re-prompts off.

## Sub-issues

As built: a test of 18.2 set the attempts to 3 where it meant 2 (fixed in `05fde90`); the 18.2 code moved the end-of-item turn count before any write, so no autoflush splits the last commit.

### MKC-18.1: run limits and the stop record

- [x] Red: `backend/tests/harness/test_limits.py` (DB)
  - `Limits.from_settings` reads the settings; invalid values are refused
  - `test_run_step_limit_stops_run`, `test_wall_time_stops_run` (backdated `started_at`), `test_cost_limit_stops_run`: each asserts `run.state == stopped`, its own `stop_reason`, one `StopEvent` with that reason, the item still `running`, no further model call
  - usage is read from the database: a second `process_run` call counts the first call's turns
- [x] Code: migration `0009_limits`, `mkc.harness.limits`, settings, `process_run`/`run_item` take `limits` and `tracers`

### MKC-18.2: item limits

- [x] Red: `test_step_limit_fails_item` (reason `step_limit` + event), `test_tool_retries_fail_item` (a failing fake tool), `test_malformed_output_gets_one_reprompt_then_item_fails` (the second request carries the corrective message; a resume after the first no-call turn carries it too), `test_resume_limit_fails_item` (counter up on resume, reset by a stored turn)
- [x] Code: the item checks in `run_item`, the corrective message in `prompts` and `load_resume_context`, the counter in `process_run`

### MKC-18.3: retries, deadline and setup stops

- [x] Red:
  - `backend/tests/models/test_errors.py`: a real 429 (with `Retry-After`), 503 and `httpx.ReadTimeout` through the OpenRouter mock transport come out of `ModelClient` as `TransientModelError`; 401 as `ModelAuthError`; 400 unchanged
  - `backend/tests/harness/test_retry.py`: `test_429_backs_off_exponentially` (fake clock: waits 2, 4, 8, 16), `Retry-After` wins when longer, `should_stop` ends the waiting, the deadline turns a hung call into a timeout
  - loop: exhausted retries stop the run with `model_unavailable`; `ReplayMiss`, `ModelConfigError` and 401 stop it with `setup_error`; the executor stops a run whose client can't be built
- [x] Code: `mkc.models` errors and classifier, `mkc.harness.retry`, the loop and executor changes; the MKC-15 and MKC-17 tests that pinned the old behaviour change in red commits first

### MKC-18.4: executor holes and docs

- [x] Red: an unexpected error in the lease renewal, the heartbeat touch and the claim does not end the thread or the worker (finding 17#6); `scripts/check_runbook.py` requires the new settings
- [x] Code: broad catches with logging in `_renew`, `_touch_loop`, `run_once`
- [x] Docs: design 8.2 notes and 8.5, decision 58 in section 18, the stale wording of findings 17#1, 17#7 and 17#8, runbook settings table and "Limits and retries", `.env.example`, status doc, backlog "As built", HANDOFF
