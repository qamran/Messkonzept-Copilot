#!/usr/bin/env bash
# Compose smoke test (MKC-8.2): build and start the whole stack, then check it.
#
# - /health answers 200 and /api/version reports the commit passed as build argument
# - the worker container is still running after a few seconds
# - the frontend serves index.html
# - MKC-11.4: mkc-backup uploads a dump to a stub receiver (scripts/backup_receiver.py);
#   scripts/restore_backup.sh restores it into a fresh Postgres; every table's row count
#   matches the source, and backup_runs says ok
#
# Runs as its own Compose project on other host ports with its own image tag
# (mkc-backend:smoke, mkc-frontend:smoke), so it leaves the local `docker compose up`
# stack, its images and its database volume alone. Removes its containers and volume at the end.
#
# Usage: bash scripts/compose_smoke.sh   (exit code 0 = ok)
# Env: MKC_COMMIT (default smoke-<time>), KEEP=1 keeps the stack running.
set -euo pipefail

cd "$(dirname "$0")/.."

export MKC_COMMIT="${MKC_COMMIT:-smoke-$(date +%s)}"
export MKC_DB_PORT=15433 MKC_API_PORT=18000 MKC_WEB_PORT=15173
export MKC_IMAGE_TAG=smoke
compose=(docker compose --project-name mkc-smoke --file compose.yaml)
api="http://127.0.0.1:${MKC_API_PORT}"
web="http://127.0.0.1:${MKC_WEB_PORT}"

fail() {
  echo "FAIL: $*" >&2
  "${compose[@]}" ps -a >&2 || true
  "${compose[@]}" logs --no-color --tail 50 >&2 || true
  exit 1
}

receiver=mkc-smoke-receiver
export MKC_RECEIVER_PORT="${MKC_RECEIVER_PORT:-18099}"

cleanup() {
  docker rm -f "$receiver" >/dev/null 2>&1 || true
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

echo "== backup and restore (MKC-11.4)"
# migrate, add rows, back up to a stub receiver, restore into a fresh Postgres, compare
"${compose[@]}" exec -T api alembic upgrade head || fail "alembic upgrade head failed"
"${compose[@]}" exec -T db psql -U mkc -d mkc -v ON_ERROR_STOP=1 -q \
  -c "CREATE TABLE smoke_rows AS SELECT generate_series(1, 500) AS id" \
  || fail "could not create the test rows"
docker run -d --name "$receiver" --network mkc-smoke_default \
  -p "127.0.0.1:${MKC_RECEIVER_PORT}:8080" mkc-backend:smoke \
  python -c "$(cat scripts/backup_receiver.py)" 8080 >/dev/null || fail "receiver did not start"
"${compose[@]}" run --rm --no-deps \
  -e MKC_BACKUP_UPLOAD_URL="http://${receiver}:8080/p/smoke-token/n/ns/b/mkc-backups/o/" \
  -e MKC_BACKUP_ALLOW_HTTP=1 worker mkc-backup || fail "mkc-backup failed"
dump="$(mktemp)"
curl -sf -o "$dump" "http://127.0.0.1:${MKC_RECEIVER_PORT}/latest" || fail "no upload arrived"
echo "   received $(wc -c < "$dump") bytes"
source_counts="$("${compose[@]}" exec -T db psql -U mkc -d mkc -tA -c "$(cat scripts/row_counts.sql)")"
restored_counts="$(MKC_RESTORE_CONTAINER=mkc-smoke-restore bash scripts/restore_backup.sh "$dump")" \
  || fail "restore failed"
rm -f "$dump"
echo "   source:   $(echo "$source_counts" | tr '\n' ' ')"
echo "   restored: $(echo "$restored_counts" | tr '\n' ' ')"
[ "$source_counts" = "$restored_counts" ] || fail "row counts differ after the restore"
case "$restored_counts" in
  *"smoke_rows|500"*) ;;
  *) fail "the restored database lacks the 500 test rows" ;;
esac
state="$("${compose[@]}" exec -T db psql -U mkc -d mkc -tA \
  -c "SELECT state FROM backup_runs ORDER BY id DESC LIMIT 1")"
[ "$state" = "ok" ] || fail "backup_runs says '${state}', expected ok"

echo "OK: compose smoke test passed"
