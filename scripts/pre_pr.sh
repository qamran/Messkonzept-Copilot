#!/usr/bin/env bash
# MKC-168.1: the pre-PR gate. Runs exactly CI's `backend` and `docs` commands
# (.github/workflows/ci.yml; scripts/check_pre_pr.py keeps the two in step), then checks
# the branch's commits (scripts/commit_report.py). A PR is opened only when this exits 0;
# paste its output into the PR body as it is.
#
# Only the environment may differ from CI, never the commands:
# - the database: DATABASE_URL as set locally (Compose db on 127.0.0.1:5433), CI uses 5432
# - python3: where `python3` does not run (the Windows Store stub), $PYTHON or `python` runs
#
# Usage: bash scripts/pre_pr.sh [BASE]   (BASE for the commit check, default origin/main)
# Set PRE_PR_SKIP_COMMITS=1 to skip the commit check (the gate's own tests only).
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
BASE="${1:-origin/main}"
failed=()

if ! python3 -c 'import sys' >/dev/null 2>&1; then
  python3() { "${PYTHON:-python}" "$@"; }
fi

step() {
  # step <name> <function>: run in a subshell, record a failure, carry on.
  # Not inside `if`: bash ignores `set -e` in an if condition, even in a subshell.
  local name="$1" rc
  echo "== $name"
  ("$2")
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "-- ok: $name"
  else
    echo "-- FAILED: $name"
    failed+=("$name")
  fi
}

# ---- CI job `backend` (working-directory: backend) ----
backend_sync() {
  cd "$ROOT/backend" || return 1
  uv sync --locked
}
backend_ruff() {
  cd "$ROOT/backend" || return 1
  uv run ruff check .
}
backend_format() {
  cd "$ROOT/backend" || return 1
  uv run ruff format --check .
}
backend_mypy() {
  cd "$ROOT/backend" || return 1
  uv run mypy
}
backend_pytest() {
  cd "$ROOT/backend" || return 1
  uv run pytest -v
}

# ---- CI job `docs` (repo root) ----
docs_markdownlint() {
  cd "$ROOT" || return 1
  git ls-files -z '*.md' | xargs -0 npx --yes markdownlint-cli2@0.18.1
}
docs_check_scripts() {
  cd "$ROOT" || return 1
  fail=0
  for script in scripts/check_*.py; do
    echo "== $script"
    python3 "$script" || fail=1
  done
  exit "$fail"
}
docs_deploy_tests() {
  cd "$ROOT" || return 1
  set -e  # as CI's `bash -e` step shell: the first failure ends the step
  bash scripts/test_mkc_deploy.sh
  bash scripts/test_cd_deploy.sh
}

commits() {
  cd "$ROOT" || return 1
  python3 scripts/commit_report.py "$BASE"
}

step "backend: uv sync --locked" backend_sync
step "backend: ruff check" backend_ruff
step "backend: ruff format --check" backend_format
step "backend: mypy" backend_mypy
step "backend: pytest" backend_pytest
step "docs: markdownlint" docs_markdownlint
step "docs: check scripts" docs_check_scripts
step "docs: deploy script tests" docs_deploy_tests
if [ "${PRE_PR_SKIP_COMMITS:-0}" != "1" ]; then
  step "commits: subject, Refs trailer, size" commits
fi

echo
if [ "${#failed[@]}" -eq 0 ]; then
  echo "pre-PR gate: all steps passed"
  exit 0
fi
echo "pre-PR gate FAILED: ${failed[*]}"
exit 1
