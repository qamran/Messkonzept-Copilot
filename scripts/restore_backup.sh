#!/usr/bin/env bash
# Restore a backup made by mkc-backup into a throwaway Postgres and print row counts
# (MKC-11.4). The Compose smoke test runs it on every CI run; the restore drill runs it on a
# real production backup (runbook "Backups and restore drill").
#
#   bash scripts/restore_backup.sh <mkc-….sql.gz>
#
# Starts pgvector/pgvector:pg17 (the same image as compose.yaml) in a container, creates the
# vector extension, loads the dump with ON_ERROR_STOP, and prints "table|count" for every
# table in public (scripts/row_counts.sql) on stdout. Progress and timing go to stderr.
# The dump is plain SQL of schema public; its `CREATE SCHEMA public;` line is skipped
# because a fresh database already has that schema.
# The container is removed at the end; KEEP=1 keeps it for a look around.
# Env: MKC_RESTORE_CONTAINER (default mkc-restore-drill).
set -euo pipefail

dump="${1:-}"
[ -f "$dump" ] || { echo "usage: $0 <backup .sql.gz>" >&2; exit 2; }
cd "$(dirname "$0")/.."

name="${MKC_RESTORE_CONTAINER:-mkc-restore-drill}"
image="pgvector/pgvector:pg17"
psql=(docker exec -i "$name" psql -U mkc -d restore -v ON_ERROR_STOP=1 -q)

cleanup() {
  if [ "${KEEP:-0}" != "1" ]; then docker rm -f "$name" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

note() { printf '%s\n' "$*" >&2; }

if docker container inspect "$name" >/dev/null 2>&1; then
  note "a container named $name already exists; remove it or set MKC_RESTORE_CONTAINER"
  exit 1
fi

note "starting $image as $name"
docker run -d --name "$name" -e POSTGRES_USER=mkc -e POSTGRES_PASSWORD=mkc \
  -e POSTGRES_DB=restore "$image" >/dev/null
# TCP check: during its first start the image runs a temporary server on the socket only.
for _ in $(seq 1 60); do
  docker exec "$name" pg_isready -h 127.0.0.1 -U mkc -d restore >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$name" pg_isready -h 127.0.0.1 -U mkc -d restore >/dev/null \
  || { note "Postgres did not start"; exit 1; }

start=$(date +%s)
"${psql[@]}" -c "CREATE EXTENSION IF NOT EXISTS vector"
gzip -dc "$dump" | sed '/^CREATE SCHEMA public;$/d' | "${psql[@]}" >/dev/null
note "restored $(wc -c < "$dump") bytes in $(( $(date +%s) - start )) s"

"${psql[@]}" -tA -c "$(cat scripts/row_counts.sql)"
