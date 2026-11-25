#!/usr/bin/env bash
# Compose smoke test (MKC-8.2): build and start the whole stack, then check it.
#
# - /health answers 200 and /api/version reports the commit passed as build argument
# - the worker container is still running after a few seconds
# - the frontend serves index.html
#
# Runs as its own Compose project on other host ports, so it never touches the
# local `docker compose up` stack or its database volume. Removes everything at the end.
#
# Usage: bash scripts/compose_smoke.sh   (exit code 0 = ok)
# Env: MKC_COMMIT (default smoke-<time>), KEEP=1 keeps the stack running.
set -euo pipefail

cd "$(dirname "$0")/.."

export MKC_COMMIT="${MKC_COMMIT:-smoke-$(date +%s)}"
export MKC_DB_PORT=15433 MKC_API_PORT=18000 MKC_WEB_PORT=15173
compose=(docker compose --project-name mkc-smoke --file compose.yaml)
api="http://127.0.0.1:${MKC_API_PORT}"
web="http://127.0.0.1:${MKC_WEB_PORT}"

fail() {
  echo "FAIL: $*" >&2
  "${compose[@]}" ps -a >&2 || true
  "${compose[@]}" logs --no-color --tail 50 >&2 || true
  exit 1
}

cleanup() {
  if [ "${KEEP:-0}" != "1" ]; then
    "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

[ -f compose.yaml ] || fail "compose.yaml missing"

echo "== build and start (MKC_COMMIT=${MKC_COMMIT})"
"${compose[@]}" up --detach --build --wait --wait-timeout 180 || fail "stack did not become healthy"

echo "== api /health"
code=$(curl -s -o /dev/null -w '%{http_code}' "${api}/health") || fail "api not reachable"
[ "$code" = "200" ] || fail "/health answered ${code}"

echo "== api /api/version"
version=$(curl -sf "${api}/api/version") || fail "/api/version failed"
echo "   ${version}"
case "$version" in
  *"\"commit\":\"${MKC_COMMIT}\""*) ;;
  *) fail "/api/version does not report commit ${MKC_COMMIT}" ;;
esac

echo "== worker still running"
sleep 5
worker=$("${compose[@]}" ps --quiet worker)
[ -n "$worker" ] || fail "no worker container"
state=$(docker inspect --format '{{.State.Status}} restarts={{.RestartCount}}' "$worker")
echo "   ${state}"
[ "$state" = "running restarts=0" ] || fail "worker is '${state}'"

echo "== frontend index.html"
page=$(curl -sf "${web}/") || fail "frontend not reachable"
case "$page" in
  *'<div id="root">'*) ;;
  *) fail "frontend did not serve index.html" ;;
esac
code=$(curl -s -o /dev/null -w '%{http_code}' "${web}/admin") || fail "frontend not reachable"
[ "$code" = "200" ] || fail "client route /admin answered ${code}"

echo "OK: compose smoke test passed"
