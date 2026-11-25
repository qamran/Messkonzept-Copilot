# Backend image (MKC-8): one image for the API (default command) and the worker (`mkc-worker`).
# Build from backend/:  docker build --build-arg MKC_COMMIT=$(git rev-parse HEAD) -t mkc-backend backend
# Base images are pinned by their multi-arch index digest (amd64 + arm64).

# --- builder: install the locked dependencies and the mkc package into /app/.venv
FROM python:3.12-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Then the package itself, installed (not editable): create_app reads version("mkc").
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# --- runtime: only the venv and the migrations, as a non-root user
FROM python:3.12-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b AS runtime

RUN groupadd --system --gid 10001 mkc \
    && useradd --system --uid 10001 --gid mkc --no-create-home --shell /usr/sbin/nologin mkc

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# For `alembic upgrade head` from the same image (later deploy tickets).
COPY alembic.ini ./
COPY migrations ./migrations

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER 10001:10001
EXPOSE 8000

# Last, so a new commit only changes this layer.
ARG MKC_COMMIT=dev
ENV MKC_COMMIT=${MKC_COMMIT}

# Exec form: SIGTERM goes straight to uvicorn (or to mkc-worker when overridden).
CMD ["uvicorn", "mkc.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
