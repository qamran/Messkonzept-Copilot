# MKC-5: database layer (plan)

**Ticket:** MKC-5 (#5). **Sub-issues:** MKC-5.1 (#76), MKC-5.2 (#77), MKC-5.3 (#78), MKC-5.4 (#79). **Spec:** design doc feature 5; backlog entry MKC-5.

**Goal:** migrations and a session layer that work the same locally, in CI and on Supabase.

## Choices

- **Postgres 17 with pgvector:** image `pgvector/pgvector:pg17`. Supabase's hosted platform defaults to Postgres 17 (Supabase changelog, checked 24.11.2026).
- **Driver:** psycopg 3 (`psycopg[binary]`), with SQLAlchemy 2 and Alembic.
- **Port:** compose binds `127.0.0.1:5433`, because a native Postgres service already uses 5432 on the dev machine. The default `DATABASE_URL` points to `127.0.0.1:5433`, not `localhost`: on the dev machine `localhost` tries IPv6 first and the connection stalls, because compose binds IPv4 only.
- **Dev-only credentials:** `mkc` / `mkc` / database `mkc`. They're only valid for the local container, which listens only on 127.0.0.1. They are not secrets.

## Layout

```
docker-compose.yml          service db (repo root, so `docker compose up db` works as written)
backend/
  alembic.ini               script_location = %(here)s/migrations
  migrations/
    env.py                  URL from Settings; engine passed directly (no configparser interpolation)
    script.py.mako
    versions/0001_enable_pgvector.py
  src/mkc/db/
    __init__.py
    base.py                 Base(DeclarativeBase)
    session.py              get_engine(), get_session()
    check.py                `python -m mkc.db.check` (MKC-5.4)
  tests/
    test_config.py
    db/conftest.py          throwaway database per test session
    db/test_session.py
    db/test_migrations.py
    db/test_check.py
```

## Settings

`Settings.database_url`:
- read from `DATABASE_URL` (also `MKC_DATABASE_URL`)
- default `postgresql+psycopg://mkc:mkc@localhost:5433/mkc`
- `postgres://` and `postgresql://` are rewritten to `postgresql+psycopg://`. A bare scheme would make SQLAlchemy look for psycopg2. Supabase hands out `postgresql://` URLs.

## Session layer

- `get_engine()` builds the engine lazily (cached per URL), so the API and the worker import without a database.
- `get_session()` is a context manager: it yields a `Session`, commits on success, rolls back on error and always closes.

## Tests against Postgres

- `tests/db/conftest.py` connects to the database in `DATABASE_URL` and creates a throwaway database `mkc_test_<random>`. Tests run in it, and it is dropped at the end. `downgrade base` never touches dev data or Supabase.
- If Postgres can't be reached, the DB tests **fail**. Set `MKC_SKIP_DB_TESTS=1` to skip them on purpose. MKC-6 adds a pgvector service container to CI.

## Steps (test-first)

1. **MKC-5.1:** harden the worker test (cancel both timers in `finally`; a `timed_out` event set by the watchdog). Show red with a `run()` that ignores SIGTERM and one that fails early.
2. **MKC-5.2:**
   - `docker-compose.yml`, then `docker compose up -d db` and check that `vector` is available.
   - `tests/test_config.py` (red) → `Settings.database_url`.
   - `tests/db/test_session.py` (red) → `mkc.db.base`, `mkc.db.session`.
3. **MKC-5.3:** `tests/db/test_migrations.py::test_upgrade_downgrade_roundtrip` (red) → `alembic.ini`, `migrations/`, revision `0001`.
4. **MKC-5.4:**
   - `tests/db/test_check.py` (red) → `mkc.db.check`.
   - The live run against Supabase: `cd backend && uv run --env-file .env python -m mkc.db.check` (done 25.11.2026; result in the status doc).

## Done when

- `docker compose up db` provides Postgres 17 with pgvector.
- `cd backend && uv run pytest` passes with the DB tests running, not skipped. `ruff check`, `ruff format --check` and `mypy` pass.
- `uv run alembic upgrade head` and `downgrade base` work against the compose database.
- The PR closes #76, #77 and #78. #5 and #79 stay open until the Supabase check is done.
