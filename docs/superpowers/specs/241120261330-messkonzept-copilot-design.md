# Messkonzept-Copilot: design

**Status:** approved by the user, 24.11.2026 (revised after independent review) · **Course:** Turing College AI Engineering capstone, Case 5 (agent harness)

---

## 1. Intent and why

Every German grid operator (VNB) publishes its own catalogue of **Messkonzepte**: which meters go where, and how energy is calculated for sites with PV, batteries, heat pumps or wallboxes. The catalogues are PDFs. Each uses its own numbering, layout and level of detail. Stromnetz Berlin calls a case "4.4", SachsenNetze calls a comparable one "3-5", and neither number means anything outside its own catalogue. Wrong concepts get chosen, applications come back, and connections are delayed. SachsenNetze writes in its own catalogue that deviating from the standard concepts leads to "zusätzliche Prüfungen … Verzögerungen".

The only shared language is the **BDEW Codeliste der Lokationsbündelstrukturen (LBS)**. Some operators state LBS codes per concept (Berlin does), and others don't (SachsenNetze doesn't).

**The Messkonzept-Copilot does two things:**

1. **Catalogue extraction (the harness workflow).** An agent turns an operator's Messkonzept PDF into structured, comparable records: meters, topology, components, LBS code and page citation. It uses code where code works and a vision model where only images exist. A human approves every record before it enters the catalogue.
2. **Site advisor.** A user describes a household site in plain language. The app extracts the facts, asks follow-up questions for what's missing, and recommends the matching Messkonzept *for that operator*, with the LBS code, an explanation, page citations and, from the RAG phase on, the legal reasons.

**Why this project:**

- The user has 7 years in German energy IT at a Messstellenbetreiber and targets jobs at utilities, MSBs, VNBs and energy-IT vendors. The project should show domain depth and AI engineering skill together.
- The capstone brief (Case 5) asks for a reusable harness demonstrated on one narrow domain workflow, measured against a simple loop without checkpoints. Multi-page catalogue extraction is that workflow: long, interruptible, costly per step, with consequential writes.

**Prior-art check (2026-11-24):**

- No tool was found that turns operator Messkonzept PDFs into comparable data.
- An open-source Rust project (hupe1980/mako) models Messkonzept matching but ships no real operator data. **The user decided not to use it in any form.** It is mentioned only in the README's prior-art line.

## 2. Users

- **Primary user:** MSB, VNB and energy-IT staff (e.g. at a wettbewerblicher MSB or a service provider) who work across several grid areas. They need the LBS-level view: which Lokationsbündel a site needs, and what each operator calls the matching concept.
- **Secondary user:** installers (Elektrofachbetriebe) who want a pre-check before submitting an application.
- **Operator/expert user:** the person who runs extractions and approves records. In the demo that is the user, acting for the fictional company **"Stadtwerke Musterstadt Messtechnik GmbH"**.
- **Public visitor** (recruiter, reviewer): sees a read-only demo without logging in (section 12).

## 3. Goals, non-goals, anti-goals

**Goals (v1):**

- Extract both catalogues into approved structured records:
  - **Stromnetz Berlin**, "Messkonzepte", 09-2026, 33 pages, about 25 concepts
  - **SachsenNetze**, "Standard-Messkonzepte in Niederspannung", 09/2025, 9 pages, 11 concepts
- A reusable, hand-built harness: tool-calling loop, allow-list, argument validation, checkpoints and resume, approvals, limits on steps, time, cost and retries, and traces.
- A site advisor for household sites:
  - PV (surplus or full feed-in)
  - battery (shared or separate inverter)
  - heat pump or wallbox under §14a EnWG (Modul 1 or 2)
  - an extra household (Einliegerwohnung)
- **Grounded explanations (RAG)** over a narrow, high-value corpus (section 9).
- **Decision layer:** typed yes/no, choice and score decisions come from a decision model rather than generated text, with an LLM fallback (section 6).
- Measured evaluation E1–E8 (section 11), deployed on Kubernetes and Vercel with CI/CD and an eval gate.
- A **submittable release** before the RAG and decision-layer phase (section 20, Phase 6).

**Non-goals (v1):**

- More than two operators
- Medium-voltage or commercial sites (KWK, kaufmännisch-bilanzielle Weitergabe as a target scenario)
- **§14a Modul 3** (time-variable grid fees) as a recommendation input
- Submitting applications to operators
- MaKo/EDIFACT messages
- Installer accounts or multi-tenancy beyond Clerk login
- Automatic catalogue discovery

**Anti-goals (a failure even if it technically works):**

- Recommends a concept **without a citation**, or presents an inferred LBS code as if the operator had stated it.
- Commits a record to the catalogue without human approval.
- Puts operator PDFs, real customer data or secrets into the public repo.
- An evaluation where the AI grades itself without human-verified, independently drafted gold.
- Uses hupe1980/mako code, data model or ideas.

## 4. Constraints

- **Builder:** solo.
- **Process:**
  - atomic issues, each with a goal, a test and a success measure
  - every commit atomic, under 200 lines where possible, and referencing its issue with the stable `MKC-<n>` key
  - tickets on a public GitHub Projects board; the full workflow is in section 14 and ADR 005
  - AGENTS.md as the project's agent instructions, with CLAUDE.md pointing to it
  - documentation is kept current in the repo: the design doc, Architecture Decision Records (ADRs) in `docs/adr/`, and the status doc
- **Repos:**
  - The **user's personal GitHub repo** is home. It is **public from day one** and holds CI/CD, the eval gate, deployment and all secrets.
  - The **Turing College repo** is a submission mirror with no deploy secrets.
- **Data:**
  - Operator PDFs are fetched at runtime from allow-listed URLs and never committed.
  - Gold data holds only extracted facts and page references.
  - All sites are synthetic, and the company is fictional.
- **Privacy:**
  - OpenRouter is the default route, with zero-data-retention providers.
  - The Gemini free tier may use inputs for training. That is allowed only because inputs are public PDFs and synthetic sites, and it is documented in the README.
- **Budgets:** LLM spend €20–30 in total; the user's verification time **10–12 hours** in total (section 11).
- **No Streamlit. No LangGraph in the build** (see ADR 001). LangChain is used **only for model and tool integration** (chat models, tool schemas, structured output). The execution loop and all control logic are our own.

## 5. Approaches considered

### 5.1 Harness: chosen **custom harness on LangChain plumbing** (ADR 001)

| | A. Hand-built (Python, Postgres, Pydantic) | B. LangGraph | C. Mix |
|---|---|---|---|
| Checkpoints, approvals, limits | Our own code, about 300–500 lines | Built in | LangGraph loop + our approvals and limits |
| Fit with Case 5 | The brief describes exactly this | The core work is done by the framework | Partial |
| Baseline comparison | Same code with checkpoints switched off, a clean experiment | A separate hand loop vs the framework | Mixed |
| Risk | More code, but simple and fully understood | Hidden behaviour, learning curve | Two mental models |

The workflow is a mostly linear item queue, so LangGraph's strength (branching, multi-agent graphs) goes unused.

- **Refinement (user decision):** LangChain handles the routine plumbing (provider chat models, tool schemas, structured output) underneath our `ModelClient`, but its agent APIs are not used.
- The loop, checkpoints, approvals, limits and baseline switch are ours, because they are what Case 5 grades and what the E4 experiment needs to control.
- A LangGraph port as a third evaluation arm is in the optional Phase 8.

### 5.2 Extraction: chosen **code first, vision where needed**

Evidence from spikes on 2026-11-24:

| | A. Text only (pdftotext) | B. Vision only | C. Code first + vision |
|---|---|---|---|
| Berlin tables | ❌ rows shift silently; wrong meter types and wrong LBS codes | ✅ but costly and non-deterministic | ✅ pdfplumber reads every row correctly |
| Berlin diagrams (vector) | labels only, no topology | ✅ | ✅ vision |
| SachsenNetze diagrams (raster) | ❌ nothing | ✅ some small and low resolution | ✅ vision at high DPI |

C is the most accurate and the cheapest. It also gives a good evaluation story: the naive text path is measurably wrong.

### 5.3 Matching: chosen **deterministic rules + LLM at the edges**

- The LLM turns free text into site facts and writes the explanation.
- **Code** maps site facts to candidate LBS structures and filters the approved operator concepts. That keeps recommendations reproducible and testable, and the LLM cannot invent a concept.
- Rejected: letting the LLM pick the concept directly from the catalogue, because it can't be reproduced and is hard to test.

## 6. Architecture

```text
Public visitor ─► read-only demo (no login)
React on Vercel (Vite, shadcn/ui, Clerk) ──HTTPS──► FastAPI API on k3s / Oracle (Clerk JWT check)
                                                        │ enqueue runs, approvals
                                                        ▼
                                   Harness worker on k3s (1 replica: queue lease, loop, tools,
                                   checkpoints, limits, traces, commits after approval)
                                                        │
        Site advisor (API) ── rules engine, explainer, RAG retriever, decision layer
                                                        │
            Supabase Postgres (runs, checkpoints, approvals, catalogue, gold, rules, RAG chunks + pgvector)
            + Supabase Storage (private: PDF cache, page renders)
                                                        │
   Provider layer (LangChain chat models behind our ModelClient) ──► OpenRouter (default) · Gemini · Anthropic · Meta API
   Decision layer (DecisionClient) ──► Jev via OpenRouter (after spike) · LLM fallback
   Langfuse (traces, tokens, cost, latency)
```

- **Backend:** Python 3.12, uv, FastAPI, Pydantic v2, pdfplumber, PyMuPDF for rendering, Postgres (Supabase; local and CI Postgres in Docker), SQLAlchemy + Alembic migrations, pytest.
- **Frontend:** React, Vite, TypeScript, shadcn/ui, Clerk React SDK.
- **Two backend processes** from the same image:
  - **API:** stateless, may run more than one replica.
  - **Harness worker:** one replica. It runs the work queue (section 8).
- **Provider layer:** a thin `ModelClient` interface (`chat`, `chat_with_tools`, `vision`), chosen per role in config (`extract_vision`, `facts`, `explain`, `judge`, `gold_draft`).
  - Underneath, it uses **LangChain chat models** (the provider packages, built directly; not `init_chat_model`, whose `langchain` package pulls in LangGraph) for OpenRouter, Gemini, Anthropic and the Meta API (decision 52), LangChain's **tool schema binding** (`bind_tools`, from our Pydantic argument models) and **`with_structured_output`**.
  - Our wrapper adds: OpenRouter zero-data-retention routing parameters, token and EUR cost recording per call, timeouts, trace hooks, and a **record/replay mode** (stores model responses keyed by request hash; used by E4 and the CI gate).
  - **The loop never calls LangChain's agent APIs** (`create_agent`, AgentExecutor).
  - LangChain versions are pinned; a contract test per provider catches upgrade breakage.
  - **Jev Router** (`typesafe/jev-router` on OpenRouter, which picks the model and reasoning effort per request) is one option in E6.
- **Decision layer:** a `DecisionClient` that answers Noul (yes/no), Choice and Score questions with probabilities. Up to 32 questions go in one request.
  - **Target backend: Jev via OpenRouter** (`~typesafe/jev-latest`: text and image input, "decisions" output), through `langchain-typesafe` (alpha, pinned).
  - **The call path is unverified:** the library's documentation shows TypeSafe's own API and the LangSmith Gateway, not OpenRouter. **The first issue of the decision-layer phase is a spike** that proves the path. Until it passes, every decision **defaults to the LLM fallback** (structured output with `method="json_schema"`), switched by config.
  - **Thresholds** are tuned on the dev split, compared against bands rather than exact values, and pinned per model id.
- **Retrieval (RAG):**
  - a corpus loader and chunker
  - **one multilingual embedding model** (chosen in the plan; no bake-off), stored in **pgvector in Supabase**
  - Postgres German full-text search
  - hybrid ranking (keyword + vector, merged by reciprocal rank fusion) handles references like "§ 14a" and "BK6-22-300"

## 7. Data model (our own, from primary sources only)

Sources: the BDEW Codeliste (LBS codes and their object composition), the operator PDFs, and the user's domain knowledge.

- **Operator:** id, name, voltage level, allow-listed catalogue URL, edition.
- **SourceDocument:** operator, URL, sha256, fetched_at, page count. The file is cached in a private Supabase Storage bucket, never in the repo.
- **Messkonzept** (one record per concept):
  - operator, `number` (as printed), title, applications[]
  - `meters[]`: label (Z1, Z2, Z3, Zsv…), purpose (Bezug, Einspeisung, Zweirichtung, Erzeugung, Abgrenzung, sVE), direction(s), `upstream` (label of the parent node, giving a topology tree from the grid connection), and optional meter type per power band
  - `components[]`: G (generator), B (battery), WR (inverter), SE (control unit), SV/sVE, S (sensor), each with `attached_to`
  - `formulas[]`, optional: as printed, or derived and marked as such
  - `lbs[]`: {code, condition (e.g. "mit gemessener Erzeugung"), provenance `stated` | `inferred`, rationale}
  - footnotes[], `source` {document, page}, `status` draft | pending_approval | approved | rejected, approved_by and approved_at
- **LbsStructure:** code, Bezeichnung, object composition from the Codeliste. This is reference data.
  - **Research issue (Phase 0):** find the current Codeliste version, whether a machine-readable form exists, and its licence terms. **Done (MKC-12.1, 26.11.2026):** version 1.0, corrected edition of 13.12.2024; PDF and Word only; no licence statement found; see `docs/261120261404-codeliste-research.md` and decision 50.
  - Until the terms are clear, the repo holds **only the codes and their object composition as facts, with a source citation**, never the BDEW document.
- **Rule table** (site facts → candidate LBS structures → concept attributes): AI-drafted from the Codeliste and both catalogues; **the user verifies it.** Provenance is recorded per row.
- **CorpusDocument / Chunk:** source type, URL, version or date, licence class, section or paragraph reference, text, embedding, full-text vector.
- **SiteFacts:** operator, pv {kWp, feed_in}, battery {present, inverter shared | separate}, sve[] {type, modul14a ∈ {1, 2}}, extra_households, plus `unknown[]` (facts still needed).
- **Recommendation:** operator, ranked concept ids, LBS code, explanation, citations[] (document, page or paragraph), questions to clarify with the operator.
- **Run / Item / Turn / Approval:** harness state (section 8).

## 8. Workflow 1: catalogue extraction (the harness demo)

**Input:** an operator id. **Output:** approved Messkonzept records. **Done when:** every concept in the PDF has a record that is approved or rejected (or a failed item with a reason), and the run report is written.

### 8.1 Who does what

| Step | Executed by | Model involved? |
|---|---|---|
| Fetch the document (allow-listed URL), hash, cache | **Code** (run-level step) | no |
| Segment into concept items (Berlin: one per page; SachsenNetze: two per landscape page) | **Code** (run-level step); decision-layer page triage as an assist from the RAG/decision phase on | optional |
| Per concept item: extract, render, read, assemble, validate, save the draft | **Model-driven tool loop** | yes |
| Enqueue for approval when a draft is saved | **Code** (`enqueue_approval`, run by the harness on `save_draft`'s result; decision 53) | no |
| Approve / edit / reject | **Human** (review UI → API) | no |
| Commit an approved record to the catalogue | **Code** (worker, on the approval event) | no |
| Run report | **Code** | no |

**Item-loop allow-list (the only tools the model sees):**

- `extract_text`
- `extract_tables`
- `render_region`: page and bbox validated against the page count and page size; DPI capped
- `read_diagram`: vision
- `validate_draft`
- `save_draft`

**Run-level operations** (`fetch_document`, `segment_document`, `enqueue_approval`, `commit_record`) are harness code with the same validation, tracing and idempotency rules, but they are **never exposed to the model**. That is least privilege: the model cannot fetch new URLs or write to the catalogue.

- All tool arguments are Pydantic models. Invalid arguments are returned to the model as a structured error.
- A typical agentic step: validation fails, so the model re-renders at a higher DPI and reads the diagram again.

### 8.2 States

- **Item:** `queued → running → draft_saved → pending_approval → approved → committed`; or `→ rejected`; or `→ failed(reason)`.
- **Run:**
  - `running` while items are queued or running
  - `awaiting_approval` when no items are left to process but drafts await a decision. **Extraction never waits for approvals**; only commits do.
  - `done` when every item is committed, rejected or failed
  - `stopped(limit)` when a run-level limit is hit
  - `waiting_for_database` after the worker lost the database in the middle of the run (MKC-17, decision 57); the next claim sets it back to `running`
- **Edge table (decision 54).** `mkc.harness.states.transition` allows exactly these edges and refuses every other pair; every state write goes through it.

  | Entity | From | To | Who |
  |---|---|---|---|
  | item | `queued` | `running` | queue (`next_item`) |
  | item | `running` | `draft_saved` | loop (`save_draft` returned ok) |
  | item | `running` | `failed` | loop (model error, tool error, an item limit: `step_limit`, `tool_retries`, `malformed_output`, `resume_limit`; MKC-18) |
  | item | `draft_saved` | `pending_approval` | harness `enqueue_approval` (MKC-23) |
  | item | `pending_approval` | `approved` | human (MKC-29/30) |
  | item | `pending_approval` | `rejected` | human (MKC-29/30) |
  | item | `approved` | `committed` | worker `commit_record` (MKC-30) |
  | run | `running` | `awaiting_approval` | `settle_run`: nothing queued or running, a draft awaits a decision or commit |
  | run | `running` | `done` | `settle_run`: every item `committed`, `rejected` or `failed` (also a run with no items) |
  | run | `running` | `stopped` | `stop_run` (MKC-18): a run limit, a setup error or a provider outage; `stop_reason` says which |
  | run | `awaiting_approval` | `done` | `settle_run`, as above |
  | run | `running` | `waiting_for_database` | worker, once the database is back after an outage (MKC-17) |
  | run | `waiting_for_database` | `running` | worker `claim_run` (MKC-17) |
  | run | `stopped` | `running` | `mkc run resume` (MKC-20): clears `stop_reason` and `started_at` |

  - Terminal: `committed`, `rejected`, `failed`; `done`. A `stopped` run waits for a resume (MKC-20, decision 60). A run stop leaves its items as they are (decision 58): the item in flight stays `running` with its checkpoint and queued items stay queued, so a later resume of a stopped run can continue there.
  - Reasons are columns, not states: `item.failure_reason`, `run.stop_reason`.
  - Resume adds no edge: an interrupted item stays `running`, and `process_run` serves `running` items before queued ones (decision 56). MKC-17 added `waiting_for_database` (decision 57).
- **Approval decisions** are stored durably. The worker commits on the approval event, idempotently, keyed by (document hash, concept number). A commit interrupted by a crash is retried from the stored decision.

### 8.3 Checkpoints and resume

- **Granularity: turn boundaries.** A turn is one model response plus the results of all its tool calls. After each complete turn, one Postgres transaction stores {run, item, turn number, the assistant message, the tool results (as references to Storage for large outputs), cost so far}. Tool-call/result pairs are therefore always complete in a checkpoint.
- **Resume:**
  - Completed items are never redone.
  - An interrupted item continues from its last complete turn, with the context rebuilt as: item task + compact summary of earlier turns + the last turn's tool results.
  - A turn that was in flight when the crash happened is discarded and re-requested.
- **Tool-result cache:** deterministic tools (`extract_text`, `extract_tables`, `render_region`) are cached by (tool, code version, arguments hash, document hash; the code version since decision 56). Re-issued calls cost nothing.
- **Idempotency:** `save_draft` and `commit_record` use idempotency keys, so a draft or commit is never duplicated.
- **Built in MKC-16 (decision 56):**
  - `mkc.harness.checkpoint.save_turn` refuses a turn whose calls and results don't pair; a turn cut short by an escaped tool error answers every call with an error.
  - Large results: refs into the `blob` table (Supabase Storage from MKC-21).
  - `load_resume_context`: system prompt, one user message (item task + `<earlier_turns>` summary built in code), the last turn's assistant message and tool results. A turn in flight has no row; its model cost is lost from `turn.cost_eur` (known limit; the trace keeps it).
  - Tool cache: `tool_cache` keyed by (tool, code version, args hash, document hash); `run_item(code_version=None)` switches it off. Since MKC-20 the baseline turns it off with the `tool_cache` switch (decision 60).
  - `save_draft`: table `draft`, unique (document hash, concept key) from `ToolEnv`.

### 8.4 Run executor

- **One worker Deployment** (one replica) claims runs from Postgres with a **lease**: `SELECT … FOR UPDATE SKIP LOCKED`, a heartbeat, and a lease expiry.
- **On `helm upgrade` / SIGTERM:** the worker finishes the current turn, checkpoints, releases the lease and exits. The new pod picks the run up. The pod's grace period is 300 s, the turn budget (decision 42); the worker Deployment uses `Recreate`, so two workers never run at once.
- **On a crash:** the lease expires and the next worker resumes from the last checkpoint.
- **Honest limit:** everything runs on one Oracle VM. The loss of the VM means downtime, **not data loss** (state is in Supabase and backed up nightly). The API may run more than one replica; the worker stays at one.
- **Built in MKC-17 (decision 57):**
  - Lease: `run.lease_owner` and `run.lease_expires_at` (migration 0008), database clock. `mkc.worker.lease.claim_run` takes the oldest `running` or `waiting_for_database` run whose lease is free, expired or its own (`FOR UPDATE SKIP LOCKED`).
  - Fencing: `fence` runs in the transaction of every turn, item end state and item claim; a worker whose lease was taken over gets `LeaseLost` and writes nothing more.
  - `mkc.worker.executor.Executor`: `run_once`, `graceful_shutdown`, one thread that touches the probe file and one that renews the lease (120 s lease, renewed every 20 s). No error ends the worker: database errors go to the outage handling, others are logged and the worker pauses.
  - Stop: `process_run(should_stop=...)` is checked after each committed turn and before each claim; the item stays `running` and the run is not settled.
  - Outages: a database error counts as an outage only if `SELECT 1` fails too. The worker probes with backoff (up to 30 s) and keeps its heartbeat. Once the database is back, it writes `running -> waiting_for_database` and claims the run back a moment later. Nothing can be written while the database is down, so the outage shows only briefly in the run row and in the worker log (`database unavailable`, `database available again`); there is no state history table (the MKC-17 test used a test-only trigger). MKC-19's run log is where an outage becomes a durable record.
  - Timings: runbook section "Worker lease and outages".
  - A model call that hangs is cut off by the turn deadline (MKC-18, 180 s) and retried; a model client that can't be built stops the run (`setup_error`) instead of being claimed again every 30 s.

### 8.5 Limits, retries, traces, baseline

- **Limits:** max steps (per item and per run), wall time, cost (EUR, from provider token prices) and retries per tool. Each has its own stop reason in the trace.
- **Retries:** exponential backoff on transient errors (timeouts, 429). A malformed model output gets one corrective re-prompt, then the item is marked failed.
- **Built in MKC-18 (decision 58):**
  - `mkc.harness.limits`: `Limits` (from settings; defaults and their reasons in the MKC-18 plan, settings in the runbook section "Limits and retries"), `StopReason`, `StopEvent`, `stop_run` (the one writer of a run stop).
  - Item reasons in `item.failure_reason`: `step_limit`, `tool_retries: <tool>`, `malformed_output`, `resume_limit`, `model_error: <class>`, `tool_error: <class>`. Run reasons in `run.stop_reason`: `run_step_limit`, `wall_time`, `cost_limit`, `setup_error`, `model_unavailable`. Every stop is also a `StopEvent` to the trace hooks (MKC-19 sends it on) and a log line.
  - Run usage is counted from the database before each claim and model call: stored turns, their cost, and wall time since `run.started_at` (migration 0009), by the database clock. A failed call writes no turn, so its cost is not counted, and the cost limit can be overshot by one call.
  - `ModelClient` maps provider errors (`classify_error` in `providers.py`): 401 and 402 (refused key, no credits) are `ModelAuthError` (a setup error); 408, 429, 5xx, timeouts, network errors and a 402 with `Retry-After` are `TransientModelError`; a 403 fails only its item. `mkc.harness.retry.call_model` retries those: waits 2, 4, 8, 16 s (a longer `Retry-After` wins, capped at 60 s), each attempt under a 180 s turn deadline. SIGTERM ends a wait. After the last retry the run stops (`model_unavailable`), so an outage never fails item after item into a `done` run.
  - Re-prompt: a stored turn without calls is followed by one corrective user message, also after a resume. Tool retries: failed results per tool name in the item. Resume cap: `item.attempts_without_progress` (migration 0009), up on each resume, 0 after each stored turn.
- **Traces:** every model request and tool call, with tokens, cost, latency and errors, goes to Langfuse and to a run log in Postgres for the UI.
- **Built in MKC-19 (decision 59):**
  - `mkc.observability.trace.Tracer` turns each `CallTrace` (every model call attempt), `ToolTrace` (every tool call) and `StopEvent` (every stop), plus every database outage the worker waits out, into one record: a row in `run_log` (migration 0010; no foreign keys, so a log insert never waits for `fence`) and one Langfuse observation (`mkc.observability.langfuse.LangfuseSink`). Each side is guarded on its own; a tracing failure never fails a run.
  - Every event carries its run, item and step by value (`TraceScope` on each model call, `ToolEnv.step`), so a call abandoned at the turn deadline that reports late still lands in its place and its cost is in the trace.
  - One trace per run: `run.trace_id`, 32 random hex digits, set once by the executor before work starts.
  - Metadata only: no prompts, replies, tool arguments or PDF text leave for Langfuse. Cost goes to Langfuse in USD (Langfuse's currency), never for replayed calls; `run_log.mode` keeps spend sums to live calls.
  - Without Langfuse keys (CI, local) only `run_log` records. Settings and queries: runbook section "Tracing".
- **Baseline ("simple loop"):** the same tools and prompts with checkpoints, the tool-result cache, durable queue state, idempotency keys and durable approvals **switched off by config**.
  - Pending approvals live in memory only.
  - A crash means restarting from the beginning and re-extracting everything.
- **Built in MKC-20 (decision 60):**
  - `mkc.harness.mode`: `HarnessMode`, `Switches` (the five switches above), `SWITCHES`; `MKC_HARNESS_MODE` sets the mode of new runs, `run.mode` (migration 0011) keeps it.
  - The same `run_item`/`process_run` with the switches off; `mkc.harness.baseline.RunMemory` holds the queue, turns, end states and pending approvals, and writes the ended items once, when the run settles or stops. `mkc.harness.runner.execute_run` runs a run in its mode (the executor and the CLI use it).
  - Failure injection: `mkc.harness.faults` (`FaultPlan`, `FaultInjector`, `InjectedKill`, `load_fault_plans`), hooked into the model call, the tool call and the item end; `backend/data/e4_faults.yaml`.
  - CLI `mkc run start|resume|status|inspect`. Settings, commands and fault plans: runbook section "Baseline, faults and the CLI".

## 9. Workflow 2: site advisor

1. The user types e.g. "EFH in Dresden, 10 kWp PV Überschuss, Batterie am gleichen Wechselrichter, Wärmepumpe Modul 2". The operator is chosen by dropdown, or derived from the place name with confirmation.
2. An LLM extracts **SiteFacts** (structured output) and lists `unknown[]`.
3. The UI shows the facts for confirmation. The agent asks **follow-up questions only for missing facts that change the result** (e.g. "Should the PV generation be measured separately?").
4. The rules engine:
   - maps site facts to candidate LBS structure(s)
   - filters the approved concepts of that operator by LBS and attributes (battery inverter, generation meter, §14a module)
   - ranks the matches
5. The explainer writes the recommendation, citing only fields of approved records and their pages (checked in code).
6. No match, or several equal matches: the app says so and lists what to clarify with the operator. It never guesses silently.

**Added in the RAG and decision-layer phase (Phase 7):**

7. **Legal reasons with sources.** Retrieved passages are quoted with their source.
   - **Narrow corpus:** EnWG §14a, MsbG, BNetzA BK6-22-300 (with Anlage 1), BNetzA BK8-22/010-A (the Modul 1/2 grid-fee rules that the advisor's §14a cases depend on), and the operator catalogue texts.
   - Laws and BNetzA decisions are official texts and free to use.

8. **"Ask why":** follow-up questions about a recommendation, grounded only in retrieved passages and approved records. The answer is "not covered by the sources" when retrieval finds nothing relevant.
9. **Decisions:**
   - a scope guard (household / commercial / medium voltage / off-topic)
   - a yes/no question per required fact ("is it stated?") for follow-up gating
   - an injection guard on user input and retrieved text

## 10. Safeguards

- **Prompt injection:** PDF text, images and retrieved passages are untrusted content.
  - Prompts wrap them as data.
  - Tools can't be added at runtime.
  - **The model never sees side-effect tools** (no fetch, no commit; section 8.1).
  - Commits need human approval.
  - Synthetic injection PDFs and injection passages (generated in tests) must not change any tool call or record (E5).
  - From Phase 7, an injection guard (decision layer, LLM fallback until the spike passes) screens user input and retrieved or extracted text. Flagged content is shown to a human, not silently dropped.
- **Access:**
  - Clerk login for all write and LLM-calling routes, with an admin role for runs and approvals.
  - The **public read-only demo** serves approved catalogue records and **precomputed** advisor examples only: no LLM calls, rate-limited.
- **Input validation:** Pydantic on all API and tool inputs; size and page limits on documents; allow-listed fetch domains only.
- **Output validation:** schema checks and cross-checks (section 8). Citations must point to approved records or retrieved chunks, checked in code.
- **Secrets and CI/CD on a public repo:**
  - GitHub Secrets → Kubernetes Secrets; gitleaks in pre-commit and CI; `.env` is gitignored.
  - Workflows triggered by fork PRs (`pull_request`) get **no secrets**; `pull_request_target` is not used.
  - Deploy jobs run only on pushes to `main`, inside a **protected `production` environment** (required reviewer: the user).
  - The **k3s API is not exposed to the internet.** CD connects over SSH to a restricted deploy user on the VM, which runs `helm upgrade`. The SSH key lives in the protected environment.
- **Cost:** per-run limits, a spending cap at each provider, and a daily cap in the app.
- **Data:** no personal data stored. Site descriptions in the demo are synthetic, and the retention note is in the README.

## 11. Evaluation

### 11.1 Gold data: independent by construction

- **A different model drafts the gold** than the one under test (the `gold_draft` role uses another provider), so systematic errors of the extraction model are not copied into the gold.
- **Blind subset:** the user labels about 10 concepts and 10 advisor scenarios **from scratch, without seeing any draft**. Agreement between blind labels and verified drafts is reported.
- **Dev/test split,** fixed in the repo before prompt tuning:
  - concepts and scenarios are split about 50/50 per operator
  - prompts, thresholds and the rule table are tuned on **dev only**
  - reported numbers come from **test**
- Berlin's printed LBS codes are an independent check for E2.
- Provenance (drafted by, verified by, blind or not) is stored per gold item.

### 11.2 The user's verification time: 10–12 hours

| Item | Hours |
|---|---|
| E1: 36 topology records (verify) + blind subset | ~3.5 |
| E2: LBS judgements for SachsenNetze | ~1.5 |
| Rule table | ~1 |
| E3: expected answers for 25 scenarios × 2 operators + blind subset | ~2.5 |
| E7: gold passages for ~20 "why" questions | ~1.5 |
| E8: labelled sets for the decision questions | ~1 |
| **Total** | **~11** |

Labelling starts as soon as the first Berlin drafts exist, and uses the review-queue UI.

### 11.3 LLM budget: €20–30 in total

| Item | Budget (approx.) |
|---|---|
| Development runs (cheap models, record/replay wherever possible) | €6–8 |
| Gold drafting (different model) | €2–3 |
| Full evaluation E1–E3, E5, at most 3 times | €4–6 |
| E4: fault mechanics on **replay** (≈ €0), plus one live no-fault and one live fault run | €1–2 |
| E6 model comparison on a subset (incl. Anthropic, Meta Llama, Jev Router via OpenRouter, about 5 concepts each) | €3–4 |
| E7 RAG (embeddings + RAGAs judge) | €1–2 |
| E8 decision layer (Jev vs LLM fallback) | €1–2 |
| CI gate (replay unless prompts or models change) | €1–2 |

Spending caps are set at each provider.

### 11.4 The evaluations

| ID | What | Set | Metrics |
|---|---|---|---|
| E1 | Extraction accuracy | ~36 concepts (test split reported) | field-level precision and recall (meters, upstream links, components, applications) and exact match per record |
| E2 | LBS inference | SachsenNetze (user-verified), plus Berlin with printed codes **masked** | top-1 and top-2 accuracy |
| E3 | Site advisor | 25 synthetic household scenarios × 2 operators | top-1 concept accuracy, LBS accuracy, citation validity, necessary vs unnecessary questions; explanation quality by an LLM judge against a rubric, spot-checked by the user |
| E4 | Harness vs simple loop | **Arm 1, no faults:** checkpoint overhead (time, cost, steps). **Arm 2, faults:** tool timeout, 429, malformed model output, process kill at turn k, kill during a pending approval | completion rate, cost, repeated side effects (must be 0), recovery time, steps. Fault mechanics run on **replayed** model responses for determinism and cost; one live run of each arm for realism |
| E5 | Safeguards | injection PDFs and passages, disallowed URL, invalid tool arguments, attempts to call a non-allow-listed tool, over-limit runs | blocked or handled correctly (pass/fail per case) |
| E6 | Model comparison | E1/E2 subset across providers, incl. Jev Router | accuracy vs cost vs latency, per role |
| E7 | RAG retrieval and grounding | ~20 "why" questions with gold passages | precision@k, recall@k (hybrid vs vector vs keyword); RAGAs faithfulness, answer relevancy, context precision |
| E8 | Decision layer | labelled sets: scope, fact-stated, injection, page triage | accuracy and calibration per question; latency and cost vs the LLM fallback |
| E9 | Agent trajectory (decision 55) | the E1 items, from the `turn` rows of each run | per item: task completion (draft saved), tool-choice accuracy against the expected tools per concept type, rate of valid tool arguments, refused or unknown tool calls, steps and cost per item |

E3 and E5 are **re-run after Phase 7**, because the advisor and the injection guard change there.

### 11.5 Regression and CI gate

- A small, fixed eval subset (about 5 concepts and 5 scenarios, from the test split) runs in GitHub Actions on PRs that touch prompts, models, extraction, rules or retrieval.
- It uses **replayed** responses unless prompts or models changed. Then it runs live, within a cost cap.
- The PR fails if accuracy drops below the stored baseline minus a tolerance, or if cost per item rises above a threshold.
- Full evaluations run on demand, and their reports are committed.
- **Per-case regression (decision 55):** every report stores pass or fail per case, not only averages. The runner diffs it against the previous report on the same split and lists each case that passed before and fails now. The CI gate fails on any such case in its subset, unless the PR names it as an accepted change.

### 11.6 Eval-driven improvement log (decision 55)

- Each eval run that leads to a change gets an entry in `eval/iterations.md`: the result that prompted it, the change (prompt, model, rule, tool), the metrics before and after, and the cases that changed state.
- Tuning uses the dev split only; the log reports test-split numbers after a change is final.
- The log is the evidence for the capstone criterion "effective use of evals" (added by Turing College on 27.11.2026, 13 % of the score; every capstone must include evals) and is shown in the review.

## 12. UI (React + shadcn/ui)

1. **Advisor:** free-text box, operator select, facts card with confirm/edit, follow-up questions, and a recommendation card (concept, LBS, explanation, citations, open questions; legal reasons and "ask why" from Phase 7).
2. **Review queue:** draft record next to the rendered PDF region. Approve, edit or reject; the inferred LBS is highlighted.
3. **Runs:** list with status (running, awaiting approval, stopped by limit, failed, done), start and resume buttons, and a cost/steps summary.
4. **Run trace:** a timeline of model calls and tool calls with tokens, cost, latency and errors, linking to Langfuse.
5. **Catalogue and comparison:** approved concepts per operator, side by side by LBS code (the "Berlin 4.4 ≈ SachsenNetze 3-5" view). **This is the most domain-distinctive screen and is kept.**
6. **Eval report:** the latest E1–E8 results.
7. **Public demo (no login):** the catalogue and comparison view plus precomputed advisor examples, with a short "how it works" panel.

## 13. Deployment and DevOps

- **Split hosting (ADR 002):**
  - **Frontend** (static React build) on **Vercel**: global CDN, automatic HTTPS, a **preview URL for every PR**, production on merge to `main`.
  - **Backend** (API + harness worker) on **k3s** on the Oracle Always Free ARM VM. Long-running, resumable runs don't fit serverless.
- **Glue between the two:**
  - CORS allow-list on the backend: the production Vercel domain plus the preview-domain pattern, the same for the token's `azp` check (decision 45)
  - `VITE_API_URL` per Vercel environment
  - **Clerk:** the **development instance for every environment** (local, previews, production; decision 39, ADR 002). Clerk production keys don't work on `*.vercel.app` previews, and the workaround needs Vercel Pro. Accepted limits: the "Development" badge, at most 100 users, a relaxed security posture.
  - Preview frontends point at the production backend; only admin users can start runs or approve.
- **Version sync:** the backend exposes `/api/version`. The frontend warns on a mismatched API version (decision 46), and CD deploys the backend before promoting the frontend.
- **Containers:** one backend image (API and worker entrypoints), multi-arch (amd64 + arm64), on GHCR. The frontend container is only for local Compose.
- **Local:** Docker Compose (`compose.yaml`: API, worker, Postgres, frontend; decision 41).
- **Server:** Oracle VM `mkc-k3s` with k3s, Traefik and cert-manager; API host `92-6-240-17.sslip.io` (decisions 43, 44; runbook `docs/251120261645-runbook.md`).
- **Kubernetes:** one Helm chart, `deploy/helm/mkc/` (API and worker Deployments, Service, Ingress with cert-manager TLS, Secret; decision 42). `scripts/kind_smoke.sh` installs it on a throwaway kind cluster, locally and in CI.
- **CI (GitHub Actions, personal repo):**
  - ruff, mypy, pytest
  - frontend lint, typecheck and tests
  - gitleaks and a dependency/image scan
  - the eval gate
  - Helm chart lint, plus an install on a throwaway **kind** cluster with a smoke test
- **CD:** on push to `main`, in the protected `production` environment: SSH to the VM's deploy user → `helm upgrade` → automated smoke test → rollback on failure; then the Vercel production deploy (`.github/workflows/cd.yml`, decision 47; runbook "Deploy and rollback").
- **State (ADR 003):**
  - **Supabase Postgres** (runs, checkpoints, approvals, catalogue, gold, rules, RAG chunks with pgvector) and **Supabase Storage** (private bucket: cached PDFs and renders).
  - Clerk stays the only login. The backend uses a server-side Supabase key that is never exposed to the frontend.
- **Supabase free tier** (checked 2026-11-24): 500 MB database, 1 GB file storage (max 50 MB per file), 5 GB egress per month, 2 active projects, pausing after 1 week of inactivity (accepted; wake before demos). Three rules keep usage well inside the limits:
  1. **Small checkpoints:** turn records with references to Storage for large outputs; step detail of finished runs is pruned after N days.
  2. **Renders cached by content key** (document hash + page + region + DPI).
  3. **A local render cache on the worker pod.** Evaluations and CI run against Docker Postgres and local files, never against Supabase.
  - The Runs page shows database and storage usage. Hitting a limit is a documented failure mode, with the Pro plan as the upgrade path.
- **Backups (the free tier has none):**
  - A nightly Kubernetes **CronJob** runs `pg_dump`, compresses it and uploads it to **Oracle Cloud Object Storage** (Always Free), with 14 days of retention. It never goes to GitHub.
  - **One documented restore drill:** restore the latest dump into a throwaway Postgres, check the row counts of the catalogue and gold tables, and record the steps and timing in the runbook. (An automated monthly restore test is on the deferred list, section 20.)
  - The approved catalogue and gold data can also be exported as JSON.
  - A failed backup shows up in the logs and as an alert on the Runs page.
- **Config:** env vars and Helm values; the provider per role is set in config.
- **Observability:** Langfuse Cloud (free tier), plus structured app logs.
- **Turing repo:** receives pushes of the same commits for submission, with no deploy secrets.
- **Accounts in place (2026-11-24):** Oracle Cloud account, Clerk, Langfuse, the personal GitHub repo. *Correction 25.11.2026:* the Oracle VM did not exist yet; it was created on 25.11.2026 in MKC-10 (decision 44, runbook "Server setup").
  - **User-only setup tasks at the start:**
    - a Supabase project (Postgres + private Storage bucket) (done 25.11.2026)
    - a Vercel account linked to the personal repo (done 25.11.2026: project `messkonzept-copilot`)
    - provider API keys with spending caps (OpenRouter with zero-data-retention routing, Gemini, Anthropic, Meta API)
    - GitHub Secrets and the protected `production` environment (done 25.11.2026: `VERCEL_TOKEN`)
    - a domain with TLS (for the backend API; Clerk needs none, decision 39) (done 25.11.2026: `92-6-240-17.sslip.io`, decision 43)
  - **Fallback** if k3s blocks deployment: keep the Helm chart tested on kind in CI, deploy with Compose on the same VM, and document the limitation.
- **Remotes (set up 24.11.2026):** `origin` = <https://github.com/qamran/Messkonzept-Copilot> (personal, public, home); `turing` = <https://github.com/TuringCollegeSubmissions/qshahz-AE.CAP.AFA.1.1> (submission mirror). `main` is pushed to both after every merge, so both show the same commit; the current one is in HANDOFF.md.

## 14. Agentic-coding practice and ticket workflow (review topic; ADR 005)

- **Tickets** live as GitHub Issues (with native sub-issues) in `qamran/Messkonzept-Copilot`, on a **public GitHub Projects board**. Status: `Backlog → Ready → In progress → Testing → Done`.
- **Stable keys:** `MKC-<n>` in the issue title, the branch name (`mkc-<n>-<slug>`) and every commit (`MKC-<n>: <summary>` plus `Refs: qamran/Messkonzept-Copilot#<issue>`). Unambiguous across both remotes.
- **Turing mirror (code only, decision 35):** `main` is pushed to both remotes, so the Turing repo has the same commits but no issues. The README links to the public board, the issue list, the design doc, the ADRs and HANDOFF.md; `scripts/check_readme.py` checks the board and issue links. No token or secret is needed.
- **Roles:**
  - **Development agent (Claude Opus 5.5):** pulls a ticket, breaks it into issues and sub-issues, works it in atomic commits (under 200 lines where possible) that each reference their issue, pushes to a separate branch, and moves the ticket to `Testing`.
  - **Review agent (Fable):** reviews the PR, merges it, and closes the ticket. It never writes the code it reviews.
  - **From 27.11.2026 (decision 61):** with parallel lanes there are four roles: a coordinator (the main session), a test agent and a development agent per lane, and a review agent per PR that starts only when `gh pr checks` is green. Details: AGENTS.md "Roles" and "Parallel lanes", ADR 005 amendment.
- **Flow per ticket** (triggered in-session with "next ticket"; after that the development agent continues to the next ticket or step without asking, and stops only for a genuine decision, decision 36):
  1. The development agent takes the top `Ready` ticket, sets it to `In progress` and **assigns it, its sub-issues and its PR to the user (`qamran`)**.
  2. It creates issues and sub-issues, each with a goal, a test and **success criteria** (a checklist of what must be delivered and true; ticket format in the backlog plan).
  3. It branches from `main`, works test-first, and makes atomic commits (under 200 lines where possible), each referencing its sub-issue.
  4. It pushes, opens a PR (`Closes #<issue>`), and sets the ticket to `Testing`.
  5. The **review agent** (Fable) reviews item by item against the success criteria and the repo standards, and posts its verdict on the PR.
  6. **Pass + green CI:** it merges (no squash, so atomic commits stay), the ticket goes to `Done`, and `main` is pushed to both remotes. **Fail:** back to `In progress`, with findings, for the development agent.
- **HANDOFF.md** (repo root) is the restart file for agents: what is done, in progress, next, blocked, and a newest-first log. It is updated in every commit and after every important ticket change (status change, sub-issue created or closed, PR opened or merged, review verdict); changes made outside a branch are recorded in the next commit. `scripts/check_handoff.py` checks its sections. When a session's context passes about 80 %, the development agent tells the user and recommends a restart, after making sure HANDOFF.md is current. *(Added 24.11.2026 at the user's request.)* *(From 27.11.2026, decision 61: `HANDOFF.md` is the coordinator's file; each parallel lane writes only `handoff/lane-<x>.md`, checked by the same script.)*
- **Branch protection:** PRs only, required CI checks, no force-push. The gate is green CI plus the review agent's verdict comment, because a bot cannot approve its own PR.
- **AGENTS.md** (with CLAUDE.md, one line importing it; added in MKC-3) holds the project rules and the review agent's checklist, checked by `scripts/check_agents.py`: this workflow, commit format and size, test-first, docs kept current (design doc, ADRs, status doc), the no-PDF-in-repo rule, the no-mako rule.
- Planning through spec → plan → tickets. Skills used: brainstorming, writing-plans, TDD, code review.

## 15. Build order

The build follows the phases in section 20, ordered by dependency:

- **Phase 2 ends with a go/no-go check:** vision reading on 5 Berlin concepts must work, or the scope narrows to Berlin only.
- **Phase 6 is the submittable release:** everything graded is in place before RAG and the decision layer are added in Phase 7.

## 16. Risks

| Risk | Mitigation |
|---|---|
| Vision misreads small raster diagrams (SachsenNetze 3-5) | Render at high DPI; the validator cross-checks labels in the diagram against the text; human approval; report the error rate honestly |
| Gold copies the model's errors | A different drafting model, a blind subset, a dev/test split (section 11.1) |
| Verification takes longer than 10–12 h | Review-queue UI reused for labelling; blind subsets kept small; numbers reported with set sizes |
| The decision-layer call path via OpenRouter doesn't work | Spike first; LLM fallback is the default until it passes; E8 reports whichever backend is used |
| `langchain-typesafe` alpha breaks | Pinned version; fallback switch in config |
| Site-advisor scope creep | Fixed device list; anything else gets "not covered, clarify with the operator" |
| ARM image or k3s issues | Multi-arch build and kind test in CI from the start; deploy early |
| Provider differences (tool calling, vision) | Contract tests per provider; OpenRouter is the default |
| Frontend and backend out of sync | `/api/version` check; backend deploys first; smoke test after each deploy |
| A public repo leaks something, or CI is abused | gitleaks; no secrets on fork PRs; protected environment; k3s API not exposed |

## 17. Left to the builder (plan stage)

- The exact models per role, chosen from a short E6 comparison early in the build.
- The embedding model (one multilingual model).
- The prompt wording and the vision output schema.
- Limit defaults: steps, time, cost, retries; lease and heartbeat timings.
- UI layout details within the screens listed.
- How SachsenNetze pages are split into concept regions (detected layout vs a fixed half-page split).

## 18. Decision log

| # | Decision | By |
|---|---|---|
| 1 | Idea D, Messkonzept-Copilot | user |
| 2 | Hand-built harness; LangGraph not used (ADR 001) | user (agent recommended) |
| 2a | LangChain for model and tool integration only (chat models, bind_tools, structured output); the loop and control stay custom | user (agent recommended) |
| 3 | FastAPI + React (Vite, shadcn/ui); Clerk for login | user |
| 4 | Operators: Stromnetz Berlin + SachsenNetze (low voltage) | user (SachsenNetze picked by agent after spike) |
| 5 | Household site scope; free-text input + follow-ups | user |
| 6 | Gold: AI drafts, user verifies | user |
| 7 | Providers: OpenRouter default + Gemini free, Anthropic, Meta Llama API | user |
| 8 | Langfuse (Cloud free tier) | user (cloud vs self-host: agent's call) |
| 9 | Docker, GitHub Actions, GHCR, Helm, kind in CI, k3s on Oracle Always Free | user |
| 10 | Personal repo is home, public from day one; Turing repo is a mirror | user |
| 11 | hupe1980/mako not used in any form | user |
| 12 | Code-first extraction + vision; deterministic matching | agent, based on spike evidence |
| 13 | Supabase Postgres + Storage instead of SQLite; Clerk remains the only login (ADR 003) | user (agent proposed) |
| 14 | Code-driven work queue + model-driven tool loop per item | agent (after builder check) |
| 15 | Extraction continues past approvals; only commits wait; the baseline holds approvals in memory | agent (after builder check) |
| 16 | Rule table and E3 gold: AI drafts, user verifies; Codeliste licence researched first | agent, consistent with decision 6 |
| 17 | LLM budget €20–30 | user |
| 18 | Frontend on Vercel (preview per PR) from the start; backend on k3s (ADR 002) | user (agent had recommended k3s only) |
| 19 | Supabase free tier; nightly pg_dump to Oracle Object Storage | user (agent proposed) |
| 20 | RAG in the core | user (agent recommended) |
| 21 | Decision layer: Jev via OpenRouter (`~typesafe/jev-latest`) through langchain-typesafe, LLM fallback; Jev Router in E6 (ADR 004) | user (agent proposed placement) |
| 22 | Verification budget raised to 10–12 h | user, after independent review |
| 23 | Narrow RAG corpus (EnWG §14a, MsbG, BK6-22-300, BK8-22/010-A, operator texts); one embedding model; no reranker | user, after review (BK8-22/010-A kept by agent because the §14a Modul 1/2 cases depend on it) |
| 24 | One documented restore drill instead of a monthly automated restore test | user, after review |
| 25 | Features cut in review are moved to a deferred list, not dropped | user |
| 26 | Harness made consistent: run-level operations are code, never model tools; checkpoints at turn boundaries; a single-replica worker with a Postgres lease; honest single-VM limit | agent, after review |
| 27 | Decision layer defaults to the LLM fallback until the OpenRouter call path is proven by a spike | agent, after review |
| 28 | Submittable release (Phase 6) before RAG and the decision layer; E3 and E5 re-run afterwards | agent, after review |
| 29 | Independent gold: a different drafting model, blind subsets, a dev/test split | agent, after review |
| 30 | E4 gets a no-fault arm; fault mechanics on replayed responses | agent, after review |
| 31 | Public read-only demo; primary user MSB/VNB/energy-IT staff; §14a Modul 3 out of scope; CI/CD hardening for a public repo; Clerk preview check | agent, after review |
| 32 | Ticket workflow: GitHub Issues + sub-issues on a public Projects board; `MKC-<n>` keys; Turing repo as a code-only mirror (decision 35; first planned as an issue-mirror Action); branch per ticket; development agent (Opus 5.5) builds, review agent (Fable) reviews and merges after green CI (ADR 005) | user (agent recommended; agent roles and models: user) |
| 33 | Tickets being worked on, their sub-issues and PRs are assigned to the user (`qamran`) | user |
| 34 | HANDOFF.md as the agents' restart file, updated with every commit and important ticket change; restart recommended at about 80 % context | user |
| 35 | Turing repo is a code-only mirror (ADR 005 option (c)): no issue-mirror Action and no token; the README links to the board, issues, design doc, ADRs and HANDOFF.md | user |
| 36 | The development agent continues to the next ticket or step without asking for permission; it stops only for genuine decisions (scope or design choices, user-only setup tasks) | user |
| 37 | FastAPI's test client uses `httpx2` instead of the deprecated `httpx`; Starlette deprecation warnings fail the tests (MKC-6.1) | user |
| 38 | CI (MKC-6): jobs backend, frontend, gitleaks, dependency-scan and docs are required checks on `main`, pinned to the GitHub Actions app, with "branch must be up to date" on; no `paths` filters, so every job always reports; the frontend job reports success until MKC-7; gitleaks runs as a checksum-pinned release binary with a fake-key self-test; dependency scan is pip-audit on the hashed `uv export`; all tracked Markdown must pass markdownlint (ADR 005) | agent |
| 39 | Clerk development instance for every environment (local, Vercel previews, Vercel production), permanently; no production instance. Reason: production keys don't work on `*.vercel.app` and the workaround needs Vercel Pro. Sign-in by email and Google; the user's Google account is the admin (ADR 002) | user (agent laid out the options) |
| 40 | Admin role = Clerk public metadata `{"role": "admin"}`, carried as the session-token claim `role`; the backend verifies tokens with the instance's public JWKS only (RS256, `exp`, `nbf`, `iss`, `sub`, `azp` allow-list), no Clerk secret key; the CI frontend job runs lint, typecheck, test and build; the dependency scan adds `npm audit` (shipped packages at any level, all packages at high) (MKC-7) | agent |
| 41 | Containers (MKC-8): one backend image (`backend/Dockerfile`, multi-stage, uid 10001, base images pinned by digest, `MKC_COMMIT` build argument; API by default, `mkc-worker` for the worker); `compose.yaml` (db, api, worker, frontend) replaces `docker-compose.yml`; CI job `image` runs a Compose smoke test, a Grype scan (high or critical with a fix fails) and a `linux/amd64,linux/arm64` build on every PR; the only write permission in CI is `packages: write` in the job `publish`, which runs only on a push to `main` in `qamran/Messkonzept-Copilot` (Actions also run on the Turing mirror) and logs in with `github.token`, not a stored secret; image `ghcr.io/qamran/messkonzept-copilot-backend`, tags `<commit sha>` and `main`; `image` is a required check on `main`, `publish` is not (ADR 002, ADR 005) | agent |
| 42 | Helm chart (MKC-9): `deploy/helm/mkc/` deploys the API (replicas from values) and the worker (`replicas: 1` in the template, `strategy: Recreate`); probes on `/health` for the API and `mkc-worker-health` (heartbeat file) for the worker; uid 10001, read-only root filesystem; secrets from values or an existing Secret, never in `values.yaml`; Ingress TLS via a cert-manager annotation (no `Certificate` or `ClusterIssuer` in the chart). Worker `terminationGracePeriodSeconds: 300` = turn budget: model call 180 s + tool calls 60 s + checkpoint and lease release 30 s + margin 30 s; the `ModelClient` timeout must stay at or below 180 s and MKC-10's `helm upgrade --timeout` must be longer than 300 s; once turns run (MKC-17, MKC-20), the worker must beat its heartbeat during a turn or the 30 s max age must be raised. CI job `kind` (Helm 4.3.1, kind 0.33.0, node v1.37.0 like k3s stable) runs `helm lint --strict` and `scripts/kind_smoke.sh` on every PR and is a required check; `publish` needs it (ADR 002, ADR 005) | agent |
| 43 | API host name `92-6-240-17.sslip.io` (sslip.io: free, no sign-up, no DNS record; tied to the VM's IP; Let's Encrypt rate limits may be shared). An own domain can replace it later by changing the Helm values, `VITE_API_URL` and CORS (ADR 002, runbook) | user |
| 44 | Server (MKC-10 setup, 25.11.2026): Oracle VM `mkc-k3s`, `VM.Standard.A1.Flex` 4 OCPUs / 24 GB, Ubuntu 24.04 arm64, ephemeral public IP; ports 80 and 443 open in the security list and in iptables (plus the k3s pod and service ranges; Oracle's FORWARD reject removed), 6443 never opened; k3s v1.37.2+k3s1 with Traefik; cert-manager v1.21.3 with HTTP-01 ClusterIssuers `letsencrypt-staging` and `letsencrypt-prod`, no ACME e-mail; Vercel project `messkonzept-copilot` (root `frontend`, Node 24, preview per PR); GitHub environment `production` (required reviewer `qamran`, protected branches only, secret `VERCEL_TOKEN`). Steps in `docs/251120261645-runbook.md` (ADR 002) | agent |
| 45 | Origins (MKC-10): `MKC_CORS_ORIGINS` and `MKC_CLERK_AUTHORIZED_PARTIES` list the production site `https://messkonzept-copilot.vercel.app` exactly; `MKC_CORS_ORIGIN_REGEX` adds the Vercel previews (`^https://messkonzept-copilot-[a-z0-9-]+-qamran\.vercel\.app$`, full match) to **both** CORS and the token's `azp` check, so a preview that passes CORS is not refused by the verifier. Accepted risk (stated after the PR #109 review; accepted by the user on 26.11.2026): a name pattern can't be made safe. Vercel gives every project the host `<project>.vercel.app`, first come, first served, so any Vercel account can create a project named `messkonzept-copilot-<x>-qamran` whose host matches. The Clerk publishable key is public, so such a page can show our sign-in; if a user signs in there, the page gets a token the API accepts with that user's rights. Not tested whether Clerk's development instance lets such a page finish a sign-in; assume it can. Rule: sign in only on the production site or on a preview opened from a PR in our repo; revisit before any real data or a Clerk production instance. Ways to remove the risk: drop previews from the `azp` check (previews then can't call signed-in endpoints), or put previews on a domain we own. Previews stay behind Vercel Authentication (ADR 002) | agent |
| 46 | API-version warning (MKC-10): CD builds the production frontend with `VITE_COMMIT=<commit>`; the page compares it with `commit` from `/api/version` and shows a warning on a mismatch. Builds without `VITE_COMMIT` (local, previews, which call the production API) skip the check; a failed request shows nothing | agent |
| 47 | Continuous deployment (MKC-10): `cd.yml` on push to `main` only, home repo only; job `image` waits for `:<commit>` (no secrets), `backend` and `frontend` run in the `production` environment. The backend deploys over SSH to the VM user `mkc-deploy`, whose key is limited to a forced command (`deploy <40-hex commit>`, `rollback`, `status`); only commits on `main` are deployed (GitHub serves fork commits under our URL too); namespace `mkc` enforces Pod Security `restricted`; the chart comes from GitHub at that commit, the values from root-owned `/etc/mkc/values.yaml`; Kubernetes rights are the `admin` role in namespace `mkc` only; Helm `--rollback-on-failure --wait=watcher --timeout 600s` (> 300 s grace period); smoke test over HTTPS, `helm rollback` on failure; then `vercel build` + `vercel deploy --prebuilt --prod`. Vercel's Git integration builds previews but never `main` (`frontend/vercel.json`). `check_workflows.py` allows secrets only in `cd.yml`, only in `production` jobs. No database migration on deploy yet: the running code uses no tables; the first ticket that needs one adds it (ADR 002, runbook). *Superseded for migrations by decision 48 (26.11.2026).* | agent |
| 48 | Migrations on deploy (MKC-11.1, replaces that part of decision 47): a Helm hook Job (`pre-install,pre-upgrade`) runs `alembic upgrade head` with the release's image before any pod changes; `backoffLimit: 0`, deadline 300 s, Pod Security `restricted`. A failed migration fails the upgrade and `--rollback-on-failure` keeps the old release (tested on kind). With a chart-built Secret the hook reads a hook Secret of its own (a pre-install hook runs before the chart's resources exist); production uses `existingSecret`. Migrations are **additive only**: `helm rollback` does not undo a schema change, so the previous release must keep working on the new schema (ADR 003, runbook) | agent |
| 49 | Backups (MKC-11): a Helm CronJob (03:30 Europe/Berlin, `concurrencyPolicy: Forbid`) runs `mkc-backup`: `pg_dump --schema=public --no-owner --no-privileges` (pg_dump 17 = Supabase's server version) → gzip → PUT to Oracle Object Storage bucket `mkc-backups` (eu-frankfurt-1) under `nightly/mkc-<UTC>.sql.gz`. The upload link is a pre-authenticated request that can only write objects under `nightly/` (no read, list or delete), kept as `MKC_BACKUP_UPLOAD_URL` in `mkc-secrets`; it expires and is renewed by hand (runbook). Retention: a bucket lifecycle rule deletes `nightly/` objects after 14 days. Every run is a row in `backup_runs`; `GET /api/admin/backup-status` reports it, with `stale` after 26 h without a good backup. Only `public` is dumped: Supabase's own schemas don't restore into a plain Postgres. `scripts/restore_backup.sh` restores into a throwaway Postgres; CI runs it on every Compose smoke test (ADR 003, runbook) | agent |
| 50 | LBS reference data (MKC-12): the source is the BDEW Codeliste der Lokationsbündelstrukturen 1.0, corrected edition of 13.12.2024 (current on 26.11.2026). No licence statement was found, so the repo holds only facts with a citation: code, Bezeichnung, page and object composition in `backend/data/lbs_structures.yaml`, built by `scripts/build_lbs_yaml.py` from a PDF outside the repo. The Codeliste defines no check digit; the loader checks BDEW's Lok- und Waggon-Kennzeichnungsverfahren (AWH Identifikatoren 1.2, 8.1), which every code fits. The table `lbs_structure` is loaded by `mkc-load-lbs`; running it on deploy is wired by the first ticket that reads the table | agent, consistent with decisions 6 and 16 |
| 51 | Deploy approvals (26.11.2026): the `production` environment keeps its required reviewer `qamran`, but the development agent gives both approvals (`backend`, then `frontend`) through `gh api .../pending_deployments` with the user's login, only after the review agent merged on PASS with green CI. It checks the smoke results and logs each approval in HANDOFF.md. The user can reject a waiting deploy at any time; the gate itself is unchanged (changes the approval practice of decision 47) | user |
| 52 | Provider layer (MKC-13): `mkc.models.ModelClient` over `langchain-core` plus the provider packages, all pinned with `==` (not the `langchain` meta-package: it depends on LangGraph). **Meta:** Meta shut down the Llama API (api.llama.com) on 6 July 2026, so the fourth provider is Meta's OpenAI-compatible API (`api.meta.ai/v1`, standard tier `muse-spark-1.3`, never the `-contributor` tier that may train on inputs) through `langchain-openai`; open-weight Llama 4 stays reachable via OpenRouter (replaces the Meta Llama API of decision 7; the user chose the Meta API on 26.11.2026). The base URL `api.meta.ai/v1` was confirmed by the live contract run of 26.11.2026. Role → model mapping and USD prices in the packaged `mkc/models/models.yaml` (OpenRouter's zero-data-retention list of 26.11.2026, highest endpoint price; ECB rate 1 EUR = 1.0935 USD of 25.11.2026); a model without a price is a config error. OpenRouter requests carry `provider: {zdr: true, data_collection: deny}`. Timeout 120 s (≤ 180 s, decision 42); no retries inside the provider clients (the harness owns retries, E4). Extra method `chat_structured(role, messages, schema)` with `ModelReply.parsed`. `MKC_MODEL_MODE` defaults to `replay`; the replay key is a sha256 over role, model, method, messages (images as digests), tools and schema; stored files hold only the reply. Live contract tests are marked `live` and deselected by default | agent; Meta API: user |
| 53 | Tool registry (MKC-14): `mkc.harness.tools.ToolRegistry` holds the item tools and the run-level operations, built once (no tool can be added later). `execute` checks in order: unknown tool, context allow-list, unexpected or invalid arguments, then runs the tool; each failure is a structured `ToolError` (`unknown_tool`, `tool_not_allowed`, `invalid_args`, `not_implemented`, `tool_failed`) and nothing raises. `unknown_tool` and `tool_not_allowed` count as refusals in the trace (`ToolTrace`, a stub hook until MKC-19). **`side_effect` means the tool reaches outside its own item:** the network, the catalogue, the approval queue, or state that a re-run with the same arguments cannot overwrite by key. The registry refuses such a tool in the item context. `save_draft` writes only its own item's draft, idempotently, so it is an item tool; harness code runs `enqueue_approval` on its result (section 8.1). `Tool` gained a `description` (for `ToolSpec`) | agent (MKC-14); confirmed by the user on 27.11.2026 |
| 54 | Item loop (MKC-15): the state edge table of section 8.2 and one function `mkc.harness.states.transition` for every run and item state write (an AST guard test checks this); the state columns have no CHECK constraint, because migrations are additive (decision 48) and later tickets add states. Tables `run`, `item` (with `document_hash` and the `task` the model is told) and `turn` (one row per model call: assistant message, tool results, cost in EUR). Tools get a `ToolEnv(run_id, item_id, document_hash, concept_key)` from the harness (run-level operations get only what exists: `fetch_document` runs before there is an item), so the model never sets those keys; `ToolRegistry.execute(call, ctx, env)` and `fn(args, env)`; an item-context call without the item ids raises (a harness bug). The loop uses the role `extract_vision`, wraps tool results as `<tool_result name="…">{json}</tool_result>` with no `<` inside, lets setup errors (`ModelConfigError`, `ReplayMiss`) propagate so a run never reads `done` because of them, fails an item on any other model error, a tool exception, a reply without tool calls or `MKC_ITEM_MAX_STEPS` (default 12); a failed item or a waiting draft never stops the queue | agent (MKC-15) |
| 55 | Evals criterion (27.11.2026): Turing College added "effective use of evals for optimising and ensuring the reliability of core AI functionalities" (13 % of the score, under "AI engineering techniques"; the official table of 27.11.2026 lowers the other shares, and AI evaluations are now the one review topic every capstone must implement). The plan of section 11 already covered test sets, metrics, an LLM judge, RAGAs and a CI gate. Added: **E9 agent trajectory** (task completion, tool choice, valid arguments, refusals, steps and cost per item, from the `turn` rows); **per-case regression** (reports store pass/fail per case; the runner and the CI gate list cases that passed before and fail now); **an eval-driven improvement log** `eval/iterations.md` (result → change → before/after → changed cases). No change to the budget or the ticket order | user (27.11.2026) |
| 56 | Checkpoints and resume (MKC-16): (1) a tool result whose JSON is over `MKC_TURN_INLINE_MAX_BYTES` (16384) is stored as a content-addressed ref (`blob:sha256:<hex>`) in the Postgres table `blob` until MKC-21 adds a Supabase Storage store (refs stay valid; done in MKC-21, decision 63); (2) an interrupted item stays `running`, no new edge: `process_run` serves `running` items first (one worker per run, MKC-17's lease; `uq_turn_item_number` stops a second writer), turn number, steps and cost continue, and the resume context is the item task with an `<earlier_turns>` summary built in code in one user message plus the last turn in full; (3) the tool cache is opt-in per tool (`Tool.cacheable`: `extract_text`, `extract_tables`, `render_region`) and keyed by (tool, code version, sha256 of the validated arguments, document hash), so a code fix never serves an old result; only `ok` results, each write commits on its own; (4) tools reach the database through a factory at registry build (`default_registry(sessions=...)`), `ToolEnv` stays ids only; (5) `save_draft` is idempotent by `record_key(env)` = (document hash, concept key) from the harness; `commit_record` uses the same key (MKC-30 must add the unique constraint) | development agent (27.11.2026) |
| 57 | Run executor (MKC-17): (1) the lease lives on the run row (`lease_owner` = `<host>-<pid>-<random>`, `lease_expires_at`; migration 0008, nullable columns) and uses the database clock; `claim_run` takes a free, expired or own lease with `FOR UPDATE SKIP LOCKED` and sets a `waiting_for_database` run back to `running`; (2) fencing: `fence` locks the run row in the transaction of every turn, item end state and item claim and raises `LeaseLost` unless the worker still holds the lease, so a worker that lost its lease never writes again (`uq_turn_item_number` stays as a backstop); (3) one thread touches the probe file every `MKC_WORKER_POLL_SECONDS` and a second one renews the lease every `MKC_WORKER_LEASE_RENEW_SECONDS` (20) for `MKC_WORKER_LEASE_SECONDS` (120; three renewals must fit); a renewal that finds another owner marks the lease lost, a renewal that fails on a database error does not, and a hanging renewal never delays the probe file; (4) `graceful_shutdown` lets the turn finish and commit, leaves the item `running`, releases the lease; (5) a database error is an outage only if `SELECT 1` also fails: the worker probes with backoff up to `MKC_WORKER_DB_BACKOFF_MAX_SECONDS` (30), then writes `running -> waiting_for_database` and claims the run back (new edges both ways); the engine gets `MKC_DATABASE_CONNECT_TIMEOUT_SECONDS` (10) and TCP keepalives; (6) setup errors and any other unexpected error release the lease and pause the worker for the backoff maximum (MKC-18 turns setup errors into a run stop); no error ends the worker process; (7) the model client is built only once a run is held, so the worker runs without a database or model settings; (8) a wall-clock turn deadline (MKC-13 finding 3) is a run limit and goes to MKC-18 | development agent (27.11.2026) |
| 58 | Limits and retries (MKC-18): (1) one `StopReason` enum; item reasons in `item.failure_reason` (the item fails), run reasons in `run.stop_reason` (the run stops); every stop is also a `StopEvent` for the trace hooks and a log line; (2) a run stop leaves the items as they are (the item in flight keeps its checkpoint); (3) run usage is counted from the database (stored turns, their cost, wall time since `run.started_at` by the database clock), so a failed call's cost is not counted (and its `CallTrace` has no usage either); (4) `ModelClient` maps provider errors by status code to `TransientModelError` (408, 429, 5xx, timeouts, network, a 402 with `Retry-After`) and `ModelAuthError` (401, 402: a refused key or no credits, which fail every item alike); a 403 is not mapped (on OpenRouter it can be a moderation flag on one input), so it fails only its item; (5) transient errors are retried with exponential backoff (2 s doubling, `Retry-After` if longer, at most 60 s, 4 retries), each attempt under a 180 s turn deadline (an abandoned call may still bill); exhausted retries stop the run with `model_unavailable`; setup and auth errors stop it with `setup_error`, also when the executor can't build the client; (6) one corrective re-prompt after a reply without a tool call, kept across a resume; (7) tool retries counted per tool name per item (every `ok: false`); (8) a resume cap counts resumes without a new stored turn (`item.attempts_without_progress`, migration 0009); a deploy after a stored turn is reset by the next turn, while a SIGTERM during a backoff or an outage before the first turn counts; (9) defaults: item 12 steps, run 300 steps, 7200 s, €3.00, 3 tool retries, 3 resumes, with reasons in the MKC-18 plan; (10) finding 15#9 (`next_item` does not lock the run row) stays open for the ticket that lets the API stop a run: the worker's claim is fenced, and `fence` locks the row | development agent (27.11.2026) |
| 59 | Tracing (MKC-19): (1) one `Tracer` per worker; each model call attempt, tool call, stop and waited-out database outage is one `run_log` row (migration 0010, no foreign keys) and one Langfuse observation (generation, tool, event), each side guarded so tracing never fails a run; (2) events carry run, item and step by value (`TraceScope` passed with each model call and kept out of the replay key; `ToolEnv.step`), never as tracer state; (3) one trace per run, `run.trace_id` random and set once; Langfuse `environment` per deployment (`development`, `production`), `release` = the commit; (4) metadata only, no content: the model route has zero data retention and Langfuse keeps what it gets; the SDK exports only its own observations (`should_export_span=is_langfuse_span`), since it becomes the global OpenTelemetry provider and would pass other libraries' `gen_ai.*` spans with prompts; tool names cut to 100 and errors to 500 characters; (5) a failed call is recorded without tokens or cost (not estimated); replayed calls send no cost to Langfuse and `run_log.mode` keeps spend sums to live calls; cost goes to Langfuse in USD at the `models.yaml` rate; (6) a span starts when its hook fires and ends `latency_ms` later (the SDK takes no start time); flush after each run and on shutdown, bounded by a 5 s export timeout; (7) finding 18#1: `process_run` checks the run limits only while an item is left | development agent (27.11.2026) |
| 60 | Baseline, faults and the CLI (MKC-20): (1) baseline is the full loop with five switches off (`checkpoints`, `tool_cache`, `durable_queue`, `idempotency`, `durable_approvals`; `mkc.harness.mode`); limits (with the one re-prompt), tools and specs, prompts, model role, retries and tracing are identical, asserted by a config test; (2) off means: no `turn` rows and no resume; no tool cache; open items read once into a `RunMemory`, claims and end states kept there and written in one transaction when the run settles or stops, so a crash or SIGTERM restarts from zero; `save_draft` appends to an in-memory list with no key; only the combinations the loop honours are accepted: `checkpoints` with `durable_queue`, `idempotency` with `durable_approvals`, `tool_cache` free; (3) baseline still writes the run and item rows, the lease, the end report and `run_log`; its run limits count turns and cost in memory and wall time from the attempt's start, so a baseline run that crashes again and again in the worker has no cap across attempts (known limit: run baseline with `--inline`); `mkc run status` reads a baseline run's usage from `run_log`; (4) the mode belongs to the run: `run.mode` (migration 0011, default `full`), set from `--mode` or `MKC_HARNESS_MODE`; `mkc.harness.runner.execute_run` runs a run in its mode for the executor and the CLI; (5) `FaultPlan(timeout_at, rate_limit_at, malformed_at, kill_at_turn, kill_during_approval)`, 1-based counts, each fault once per injector (process), through the real paths: a tool timeout result (code `timeout`), a 429 before the call (backoff), a reply without a tool call (re-prompt), `InjectedKill` (a `BaseException`) after the n-th call's reply or after the n-th item ends `draft_saved`; plans only from the CLI or a test, never a setting; `backend/data/e4_faults.yaml`; (6) fault arms change later requests, so E4 must record them before replaying (MKC-32); (7) CLI `mkc run` with `start`, `resume`, `status` and `inspect` (Typer); a synthetic items file until MKC-21; `--inline` claims that run with its own lease (`claim_run(run_id=...)`); `resume` adds the edge `stopped -> running` (`stopped` is no longer terminal) and clears `stop_reason` and `started_at`; an injected kill exits 137 with the lease released; (8) PR #161 findings 1 to 3: Langfuse gets only `public_error` (error class and HTTP status, tool error code, or tool name cut to 100), `run_log` keeps the text; no sink call without a trace id; hooks guarded while the record is built; the trace id cache is cleared on flush | development agent (27.11.2026) |
| 61 | Parallel lanes (MKC-168): **the user's choices (27.11.2026):** (1) a ticket that can be built by parallel agents is built now, whatever its phase, so MKC-46 and MKC-49 (Phase 7) join wave 1; (2) PRs merge as soon as they are ready (green CI and review PASS), not in ticket-number order; the backlog's cross-lane dependencies still hold; (3) Phase 7 code may reach production before the Phase 6 release, with no feature flag; the release notes say which parts are Phase 7 and still unused; (4) after this setup ticket, development goes on with wave 1 (MKC-21, MKC-36, MKC-46, MKC-49). **The mechanics (development agent, from the plan `docs/superpowers/plans/271120261901-parallel-lanes.md`):** (5) lanes A extraction, A2 SachsenNetze, B advisor, C decision layer, D RAG, each owning its package; a lane pauses when its next ticket waits on another lane; (6) four roles: the coordinator (the main session: worktrees, shared files, merge queue, `HANDOFF.md`, the `turing` push and the deploy gates), a test agent per lane (red acceptance tests before the development agent, a mutation pass after), a development agent per lane, and a review agent per PR that starts only when `gh pr checks` is green; (7) shared files have one rule each: lane restart files `handoff/lane-<x>.md` checked by `check_handoff.py`; migrations chained on `main`'s head with `test_single_migration_head`; decision-number blocks per lane (wave 1: 62–64 lane A, 65–67 B, 68–70 C, 71–73 D); append-only `config.py` and `.env.example`; `uv lock` by the coordinator; (8) the pre-PR gate `scripts/pre_pr.sh` runs CI's exact `backend` and `docs` commands (`check_pre_pr.py` keeps them in step) and `commit_report.py` (subject, `Refs:` line, commits over 200 lines); a PR opens only when it exits 0; (9) the HANDOFF log of 24.11. to 26.11.2026 moved unchanged to `handoff/271120261920-handoff-log-archive.md` | user (1–4), development agent (5–9) (27.11.2026) |
| 62 | Editions of a catalogue (MKC-21): (1) an operator's first fetch is edition 1 with `new_edition` false; (2) a fetch whose sha256 equals the latest edition's adds no row and returns that edition with `new_edition` false; (3) any other hash is the next edition with `new_edition` true, also when an older edition had the same hash (A, B, A gives editions 1, 2, 3): an edition is one publication in time; (4) `source_document` is unique on (operator, edition), not on the hash; `operator.edition` is the latest number; the operator row is locked while the number is chosen, so two fetches never take the same one; (5) order of checks: the configured URL must be https and on the operator's `allowed_hosts` (exact host, no userinfo) before any request; `http_get` follows at most 5 redirects, each to https only; the final URL must be allow-listed; the bytes must parse as a PDF; only then the Storage write and the row, so a refused or broken download writes nothing; (6) the allow-list is `backend/data/operators.yaml` (Berlin September 2026, SachsenNetze `Standard-Messkonzepte.pdf` from its download centre); the image copies it and sets `MKC_OPERATORS_FILE` | development agent (27.11.2026) |
| 63 | Storage (MKC-21): (1) PDFs and large turn results go to the private Supabase bucket `mkc-storage` over its S3 protocol, object key `sha256/<hex>`, the same content address as the ref `blob:sha256:<hex>`, so refs need no mapping; (2) the store signs SigV4 by hand with `httpx` (only PUT and GET of one object; signatures tested against botocore's), not an AWS SDK; a missing object (404) is `KeyError`; (3) five settings `MKC_STORAGE_*`, all or none; none means a local run: PDFs in the gitignored `backend/.cache/blobs` (`FileBlobStore`, also kept out of the image's build context) and turn results in the `blob` table; (4) with Storage set, the executor writes large turn results to Storage and reads a ref from Storage first, then from the `blob` table, so refs from before MKC-21 stay readable (decision 56 (1) done); the `blob` table is now the fallback; (5) the S3 key is Storage-only (`mkc-backend`), never the service key; production needs the five values in `mkc-secrets` (runbook "Fetch and segment"); (6) no PDF is ever written to local disk when a store is given, nor to Postgres | development agent (27.11.2026) |
| 64 | Segmentation and run start (MKC-21): (1) Berlin (September 2026) has one concept per page, opening with `<number> <title>` on the first line of the main column; the sidebar (from 75 % of the page width) is left out; a concept number has at most two digits per part (`1`, `4.1`, `11.1`, `2a`) and must be followed by a word that starts with a letter, so table rows (`4.2 2RZ 60 A`), headers and years give no region; the live run found 26 regions on pages 8 to 33, the same 26 concepts as the contents on page 2; (2) `ConceptRegion.bbox` is `(x0, top, x1, bottom)` in PDF points with the origin at the top left (pdfplumber's `crop` convention): the main column from the heading down; (3) the document hash is the PDF's sha256; `segment_document(document_hash)` takes the newest edition with that hash (identical bytes); (4) `default_registry(documents=DocumentOps(...))` makes `fetch_document` and `segment_document` real run-level operations; without it they stay placeholders; (5) `mkc run start --operator <id>` runs both through the registry inside the run's own transaction and queues one item per region (concept key = the number, task = operator, edition, page, bbox, number), so a worker never sees a run without its items and a failed fetch leaves no run; (6) PDF library: pdfplumber (MIT), as the spike chose; PyMuPDF (AGPL) not used | development agent (27.11.2026) |

## 19. Course coverage

The course concepts (Key-Concepts.md, sections 1–18) are mapped to where the project shows them.

- ✅ **Implemented:** the project builds it, with evidence.
- 📝 **Explained:** discussed in an ADR or the README, with the reason it isn't built.
- ➖ **Not used:** out of scope, with the reason.

| Course area | Status | Where it shows up in the project |
|---|---|---|
| **1. LLM fundamentals** (tokens, context window, hallucinations) | ✅ | Small per-item contexts and turn-level compaction (context rot); hallucination guarded by citations, deterministic matching and approval gates; token and cost accounting per call |
| **2. Reasoning models** | ✅ | Reasoning effort as a per-role setting (higher for LBS inference, low for fact extraction), compared in E6 |
| **3. Prompting**: roles, best practices | ✅ | System prompts per role, versioned in the repo, with untrusted content wrapped as data |
| 3. Zero-shot | ✅ | Site-fact extraction |
| 3. Few-shot | ✅ | Diagram reading and LBS inference with approved examples from the other operator |
| 3. Chain-of-thought | ✅ | LBS inference writes its reasoning into `rationale`, which the reviewer sees in the review queue |
| 3. Prompt injection | ✅ | Injection PDFs and passages (E5); content isolation; no side-effect tools for the model; injection guard |
| **4. Structured output** | ✅ | Pydantic schemas for SiteFacts, draft records, tool arguments and recommendations; validated and re-prompted once on failure |
| 4. Temperature, max tokens | ✅ | Set per role in config; temperature 0 for extraction; limits enforced by the harness |
| **5. OpenRouter + zero data retention** | ✅ | Default provider with zero-data-retention routing; Gemini free tier documented as the exception |
| 5. Open-weight vs proprietary | ✅ | Meta Llama 4 (open-weight, via OpenRouter on zero-data-retention endpoints; decision 52) vs Anthropic, Gemini and Meta's Muse (proprietary) in E6 |
| 5. Local LLMs (Ollama, LM Studio) | 📝 | Possible as a provider adapter; explained in the README |
| **6. Git/GitHub, uv, Pydantic, software engineering** | ✅ | uv project, typed Python, ruff/mypy, pytest, GitHub flow with PRs and issues |
| 6. Streamlit | ➖ | Replaced by React (UI quality, 15% of the grade) |
| **7. Agentic coding** (Claude Code, AGENTS.md/CLAUDE.md, skills, plugins, context engineering) | ✅ | AGENTS.md plus CLAUDE.md; superpowers skills (brainstorming → spec → plan → TDD → code review); Context7 for current library docs; an independent review of this design; evidence kept in PRs |
| **8. Systematic evaluation**: datasets, metrics (precision/recall) | ✅ | E1–E8, independent gold with dev/test split, field-level precision and recall |
| 8. LLM-as-a-judge | ✅ | Explanation quality in E3, judged against a rubric, spot-checked by the user |
| 8. Comparing prompt variants | ✅ | Prompt versions compared on the dev split; the CI gate guards regressions |
| 8. Benchmarks and leaderboards | 📝 | Used to shortlist models for E6 |
| 8. DeepEval / Promptfoo / RAGAs | ✅ RAGAs / 📝 others | RAGAs for E7; the rest uses our own runner because the metrics are domain-specific |
| **8. Observability: Langfuse** | ✅ | Every model and tool call traced, with tokens, cost, latency and errors |
| 8. LangSmith | 📝 | Considered; Langfuse chosen (open source, framework-neutral) |
| 8. Tool-calling evaluation (three levels) | ✅ | E4/E5: right tool chosen, valid arguments, correct outcome, including attempts to call tools outside the allow-list |
| **9. RAG** | ✅ | Legal reasons and "ask why" over EnWG §14a, MsbG, BNetzA §14a decisions and operator texts; chunking per paragraph; hybrid retrieval |
| **10. Embeddings and vector DBs** | ✅ | One multilingual embedding model; pgvector in Supabase; cosine similarity plus German full-text |
| **11. LangChain** | ✅ (partial, deliberate) | Chat models for 4 providers, tool binding from Pydantic schemas, `with_structured_output`, the TypeSafe classifier runnable. Agent APIs deliberately not used (ADR 001) |
| **12. Tools and function calling** | ✅ | Model-driven tool loop per item; per-context allow-list; Pydantic argument validation; tool design best practices |
| 12. MCP | ➖ / optional | Phase 8: the approved catalogue as a read-only MCP server, with the security notes |
| **13. Agents**: pipelines vs agents, ReAct, runaway loops | ✅ | Code-driven queue plus model-driven loop per item (a deliberate hybrid, explained); ReAct-style loop; limits stop runaway loops |
| **14. Agent state and middleware** | ✅ | Durable run, item and turn state; harness hooks before and after each tool call (validation, limits, tracing), our own equivalent of middleware |
| **15. LangGraph** | 📝 | ADR 001: why hand-built; optional comparison arm in Phase 8 |
| **16. Memory** | ✅ | Long-term: approved records and approved examples reused as few-shot examples. Short-term: compact item state |
| 16. Human-in-the-loop (and its risks) | ✅ | Approval gate before commits; the advisor confirms facts; rubber-stamping risk handled by showing the source region beside the draft and by blind gold subsets |
| **17. Agent harness**: compaction, resume | ✅ | **The core of the project:** turn-level checkpoints, resume without repeated actions, compact context, limits, leases, traces |
| **18. Choosing models** | ✅ | E6 picks a model per role by accuracy, cost and latency |
| 18. Agentic security | ✅ | Least privilege per tool context, allow-listed domains, approval for writes, secrets handling, CI/CD hardening, Clerk roles |
| 18. Multimodality | ✅ | Vision reading of the meter diagrams (raster and vector) |
| 18. Alternative frameworks (PydanticAI, CrewAI, …) | 📝 | A short comparison in ADR 001 |
| Decision models (beyond the course) | ✅ | Decision layer (Noul/Choice/Score) for guards and gating; Jev Router in E6; both compared with LLMs (E8/E6) |
| **Deployment** (review topic) | ✅ | Docker, GitHub Actions CI/CD with an eval gate, GHCR, Helm, kind in CI, k3s on Oracle, Vercel, Supabase, backups and a restore drill |

## 20. Complete feature list by phase

Each phase ends in something that runs. Phases are ordered by dependency. **Phase 6 is the submittable release.** Phase 8 is optional, and the deferred list holds features cut in review, kept for later.

### Phase 0: Foundation and pipeline

0. Ticket workflow setup (ADR 005): public Projects board with the status field, labels, issue and PR templates, a README linking the board (the Turing repo is a code-only mirror), branch protection with required checks.
1. Repo setup: remotes already configured (`origin` = personal, `turing` = mirror); first push to `origin` and `turing`; branch protection on `main`; repo description and topics for the showcase.
2. AGENTS.md + CLAUDE.md. The ADRs in `docs/adr/` are kept current, and new decisions get a new ADR.
3. Backend skeleton: uv, FastAPI, `/health` and `/api/version`, config via environment, ruff/mypy/pytest; API and worker entrypoints.
4. Frontend skeleton: Vite + React + TypeScript + shadcn/ui, Clerk login and an admin role; **verify Clerk with Vercel preview domains**.
5. Database: SQLAlchemy models + Alembic migrations; Docker Postgres locally and in CI; Supabase project connected.
6. Secret hygiene: gitleaks as a pre-commit hook and in CI, `.env.example`, `.gitignore` for PDFs and caches.
7. CI: lint, typecheck, tests (backend and frontend), dependency and image scans; no secrets on fork PRs.
8. Containers: one multi-arch backend image on GHCR; Docker Compose for local development.
9. Helm chart (API + worker); install on kind in CI with a smoke test.
10. CD: protected `production` environment; SSH deploy to k3s (API not exposed), then Vercel production; post-deploy smoke test and rollback.
11. CORS + Clerk domains for production and preview; version-mismatch warning.
12. Nightly backup CronJob to Oracle Object Storage; one documented restore drill in the runbook.
13. Research issue: the version, format and licence terms of the BDEW Codeliste; LBS reference data loaded as facts with a citation.

### Phase 1: Harness core

14. Provider layer: the `ModelClient` wrapper over LangChain chat models (OpenRouter, Gemini, Anthropic, Meta API; decision 52); tool binding from Pydantic models; structured output; per-role config; zero-data-retention routing; token and cost recording; record/replay mode; pinned versions; a contract test per provider.
15. Tool registry with **per-context allow-lists** (item-loop tools vs run-level operations), Pydantic argument models and structured error returns.
16. Model-driven tool-calling loop per item.
17. Durable work queue with item and run states (section 8.2).
18. Checkpoints at turn boundaries and resume with a compact context; a tool-result cache for deterministic tools.
19. Idempotency keys for `save_draft` and `commit_record`.
20. Run executor: a single worker with a Postgres lease, heartbeat and graceful shutdown on SIGTERM.
21. Limits on steps, wall time, cost (EUR) and retries per tool, each with a distinct stop reason.
22. Retries: backoff for timeouts and 429s; one corrective re-prompt for malformed output.
23. Tracing to Langfuse plus a run log in Postgres.
24. Baseline mode via config: no checkpoints, no cache, no durable queue, in-memory approvals.
25. Failure-injection hooks (timeout, 429, malformed output, kill at turn k, kill during a pending approval).
26. A CLI to start, resume and inspect runs.

### Phase 2: Extraction, Berlin, code path

27. Run-level `fetch_document`: allow-listed URLs, hashing, caching in Supabase Storage.
28. Run-level `segment_document`: Berlin, one concept per page.
29. `extract_text`: title, applications, footnotes, stated LBS.
30. `extract_tables`: pdfplumber for the meter-technology and LBS tables.
31. `render_region`: PyMuPDF, cached by content key.
32. Draft record assembly and `save_draft` (which enqueues the approval).
33. Gold tooling: dev/test split fixed; gold drafted by a **different model**; blind-labelling mode; export/import for verification. **The user starts verifying here.**
34. **Go/no-go check:** vision reading on 5 Berlin concepts; go, or narrow the scope to Berlin only.

### Phase 3: Vision, SachsenNetze, validation and approvals

35. `read_diagram`: the vision model returns meters, directions, upstream links and components as a schema.
36. Re-render at higher DPI when validation fails (an agentic retry).
37. SachsenNetze segmentation: two concepts per landscape page.
38. `validate_draft`: schema, labels in the diagram vs the text, stated LBS vs the table, topology vs the LBS structure.
39. LBS inference for operators that don't state codes, with a rationale and provenance `inferred`.
40. Review queue API + UI: the draft beside the rendered source region; approve, edit or reject with a reason; inferred LBS highlighted.
41. Worker commits on the approval event, idempotently; approval state durable across restarts.
42. Run report: counts, cost, retries, validation failures.
43. Catalogue export/import as JSON (backup and gold).

### Phase 4: Evaluation

44. Eval runner (one CLI command) writing versioned reports; test-split reporting.
45. E1 extraction accuracy.
46. E2 LBS inference (Berlin with printed codes masked).
47. E4 harness vs baseline: the no-fault arm (overhead) and the fault arm, on replay plus one live run each.
48. E5 safeguard suite.
49. E6 model comparison on a subset, incl. Jev Router.
50. CI eval gate: a fixed test-split subset, replay by default, a stored baseline and tolerance.

### Phase 5: Site advisor

51. SiteFacts extraction from free text (structured output) with `unknown[]`.
52. Facts confirmation card plus follow-up questions only for result-changing gaps.
53. Rule table (AI-drafted, user-verified): site facts → candidate LBS → concept attributes.
54. Deterministic matching and ranking over approved records.
55. Explainer: cites only approved records and pages (checked in code); "ask the VNB" items; an honest "no match" or "ambiguous" result.
56. E3 advisor evaluation, with the LLM judge for explanation quality.

### Phase 6: Submittable release (UI, docs, showcase)

57. Runs page: list, start, resume, status, cost/steps.
58. Run trace view: a timeline of model and tool calls, linking to Langfuse.
59. Catalogue and operator comparison by LBS ("Berlin 4.4 ≈ SachsenNetze 3-5").
60. Eval report page (E1–E6 at this point; E7/E8 added in Phase 7).
61. Public read-only demo: catalogue, comparison and precomputed advisor examples; no login and no LLM calls; rate-limited.
62. README: purpose paragraph, architecture, how to run, results, limitations, prior-art line, data and privacy notes, showcase link.
63. Security and privacy notes for the review topics; runbook (deploy, rollback, restore drill); a demo script; presentation material (problem, solution, data, evaluation, challenges, next steps).
64. Showcase upload (optional criterion).

### Phase 7: Grounded explanations (RAG) and decision layer

65. **Decision-layer spike:** prove the `~typesafe/jev-latest` call path via OpenRouter (or document the alternative); until then the LLM fallback stays the default.
66. `DecisionClient` (langchain-typesafe, pinned) with the LLM structured-output fallback.
67. Decisions wired in: scope guard, follow-up gating, injection guard, page triage, review priority.
68. E8 decision-layer evaluation; thresholds tuned on dev and pinned.
69. Corpus loader for the narrow corpus (EnWG §14a, MsbG, BK6-22-300 with Anlage 1, BK8-22/010-A, operator texts); licence class per document.
70. Chunking per paragraph or section with source references; embeddings (one multilingual model) into pgvector; German full-text index.
71. Hybrid retriever (keyword + vector, reciprocal rank fusion); retrieved text treated as untrusted.
72. Explainer integration: legal reasons quoted with sources.
73. "Ask why" on a recommendation, grounded only in retrieved passages and approved records.
74. E7 retrieval and grounding evaluation (precision@k, recall@k, RAGAs).
75. Re-run E3 and E5; update the eval report page, README and showcase.

### Phase 8: Optional extras

76. A read-only MCP server for the approved catalogue.
77. A LangGraph port of the extraction run as a third arm in E4.
78. A third operator (e.g. a VBEW-based catalogue, loaded at runtime).

### Deferred (cut in the independent review; kept for later)

79. Broader RAG corpus: EEG passages, BDEW guides (e.g. "Identifikatoren in der Marktkommunikation") and edi@energy documents, fetched at runtime and never committed.
80. Embedding-model comparison (multilingual local model vs Gemini embeddings) in E7.
81. A reranker in the retrieval pipeline.
82. An automated monthly restore test in CI (in addition to the restore drill).
