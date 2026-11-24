# MKC-4: backend skeleton (plan)

**Ticket:** MKC-4 (#4), sub-issues MKC-4.1 (#73) and MKC-4.2 (#74). **Spec:** design doc feature 3; backlog entry MKC-4.

**Goal:** a typed FastAPI service with API and worker entrypoints that later tickets extend.

## Layout

```
backend/
  pyproject.toml        uv project "mkc", Python 3.12, src layout (hatchling)
  .python-version       3.12
  uv.lock
  src/mkc/
    __init__.py
    py.typed
    config.py           Settings (pydantic-settings, env prefix MKC_)
    api/app.py          create_app() -> FastAPI
    worker/main.py      run() -> None; `python -m mkc.worker.main`; script mkc-worker
  tests/
    api/test_health.py
    worker/test_worker.py
```

- **Runtime deps:** fastapi, pydantic-settings, uvicorn (to serve `create_app` with `--factory`).
- **Dev deps:** pytest, httpx (FastAPI TestClient), ruff, mypy.
- **Tool config in `pyproject.toml`:** ruff (lint + format, line length 100), mypy `strict = true` on `src/` with the pydantic plugin, pytest `testpaths = ["tests"]`.

## Settings

`mkc.config.Settings(BaseSettings)`, env prefix `MKC_`:
- `commit: str = "dev"` (from `MKC_COMMIT`, set by CI/CD at build time)
- `worker_poll_seconds: float = 1.0`

`get_settings()` builds a fresh `Settings`. The version comes from the installed package metadata (`importlib.metadata.version("mkc")`).

## MKC-4.1 steps (test-first)

1. `pyproject.toml` + `uv sync`: the empty package installs.
2. `tests/api/test_health.py`: `test_health_ok` (`GET /health` → 200, `{"status": "ok"}`), `test_version_reports_commit` (`MKC_COMMIT` set via `monkeypatch` → reported; unset → `"dev"`; version equals package metadata). Run: red (import error).
3. `config.py`, `api/app.py`: green. `ruff check`, `ruff format --check`, `mypy` pass.

## MKC-4.2 steps (test-first)

1. `tests/worker/test_worker.py`:
   - `test_run_stops_on_sigterm`: in the main thread, a timer thread calls `signal.raise_signal(SIGTERM)` after 0.2 s; `run()` must return within 5 s. Works on Windows and POSIX, because `raise_signal` runs the installed handler in-process.
   - `test_worker_process_exits_cleanly_on_sigterm`: start `python -m mkc.worker.main` as a subprocess, wait for its "worker started" line, send SIGTERM, expect exit code 0 within 10 s. Skipped on Windows, where `os.kill(pid, SIGTERM)` terminates the process without running a handler; CI on Linux runs it (MKC-6).
   - Run: red.
2. `worker/main.py`: `run()` installs SIGTERM and SIGINT handlers that set a `threading.Event`, logs "worker started", loops `while not stop.wait(poll)` (the harness queue goes here later), restores the old handlers, logs "worker stopped" and returns. Green; ruff and mypy pass.

## Done when

- `cd backend && uv sync && uv run pytest` passes; `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` pass.
- HANDOFF.md and the status doc updated; PR reviewed and merged; `main` pushed to `turing`.
