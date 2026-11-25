#!/usr/bin/env bash
# MKC-10.4: tests for scripts/cd_deploy.sh (the CD job's deploy, smoke test and rollback).
#
# Stub ssh and curl on the PATH: no VM, no network. Checks the order of the SSH requests,
# the smoke test against /health and /api/version, and the rollback on a failed smoke test.
# Usage: bash scripts/test_cd_deploy.sh   (exit 0 = all passed)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/cd_deploy.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SHA="0123456789abcdef0123456789abcdef01234567"
OLD="fedcba9876543210fedcba9876543210fedcba98"
fails=0

mkdir "$WORK/bin"
# Stub ssh: logs the remote request (last argument); exit code from STUB_SSH_<request>.
cat > "$WORK/bin/ssh" <<'STUB'
#!/usr/bin/env bash
echo "ssh $*" >> "$STUB_LOG"
request="${!#}"
case "$request" in
  deploy\ *) exit "${STUB_DEPLOY_EXIT:-0}" ;;
  rollback) exit "${STUB_ROLLBACK_EXIT:-0}" ;;
  *) exit 0 ;;
esac
STUB
# Stub curl: /health ok unless STUB_HEALTH_EXIT; /api/version reports STUB_API_COMMIT.
cat > "$WORK/bin/curl" <<'STUB'
#!/usr/bin/env bash
echo "curl $*" >> "$STUB_LOG"
url="${!#}"
case "$url" in
  */health) [ "${STUB_HEALTH_EXIT:-0}" -eq 0 ] && echo '{"status":"ok"}'; exit "${STUB_HEALTH_EXIT:-0}" ;;
  */api/version) echo "{\"version\":\"0.1.0\",\"commit\":\"$STUB_API_COMMIT\"}" ;;
  *) exit 22 ;;
esac
STUB
chmod +x "$WORK/bin/ssh" "$WORK/bin/curl"
touch "$WORK/key" "$WORK/known_hosts"

run() {  # run <sha> [VAR=value ...]; sets $code and $log
  local sha="$1"; shift
  : > "$WORK/log"
  env PATH="$WORK/bin:$PATH" STUB_LOG="$WORK/log" STUB_API_COMMIT="$SHA" \
    MKC_DEPLOY_KEY_FILE="$WORK/key" MKC_KNOWN_HOSTS_FILE="$WORK/known_hosts" \
    MKC_SMOKE_ATTEMPTS=3 MKC_SMOKE_INTERVAL=0 "$@" bash "$SCRIPT" "$sha" > "$WORK/out" 2>&1
  code=$?
  log="$(cat "$WORK/log")"
}
requests() { grep '^ssh ' <<<"$log" | awk '{print $NF == "rollback" ? "rollback" : $(NF-1)" "$NF}' | tr '\n' '|'; }
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1"; sed 's/^/     | /' "$WORK/out"; fails=$((fails + 1)); }

[ -f "$SCRIPT" ] || { echo "FAIL scripts/cd_deploy.sh missing"; exit 1; }

for bad in "" "abc" "${SHA:0:39}" "${SHA^^}" "$SHA;id"; do
  run "$bad"
  if [ "$code" -eq 2 ] && ! grep -q '^ssh ' <<<"$log"; then pass "bad commit refused: '$bad'"
  else fail "bad commit '$bad' (exit $code, calls: $log)"; fi
done

run "$SHA"
if [ "$code" -eq 0 ] && [ "$(requests)" = "deploy $SHA|" ] \
  && grep -q -- "-o StrictHostKeyChecking=yes" <<<"$log" \
  && grep -q -- "-o UserKnownHostsFile=$WORK/known_hosts" <<<"$log" \
  && grep -q "mkc-deploy@" <<<"$log" \
  && grep -q "^curl .*https://92-6-240-17.sslip.io/api/version$" <<<"$log"
then pass "good deploy: one deploy request, pinned host key, smoke test green"
else fail "good deploy (exit $code, requests: $(requests))"; fi

if ! grep -q -- " -k \| --insecure" <<<"$log"; then pass "smoke test never skips TLS checks"
else fail "smoke test uses -k/--insecure"; fi

run "$SHA" STUB_API_COMMIT="$OLD"
if [ "$code" -eq 1 ] && [ "$(requests)" = "deploy $SHA|rollback|" ]; then
  pass "API reports another commit: rollback, exit 1"
else fail "commit mismatch (exit $code, requests: $(requests))"; fi

run "$SHA" STUB_HEALTH_EXIT=22
if [ "$code" -eq 1 ] && [ "$(requests)" = "deploy $SHA|rollback|" ]; then
  pass "/health fails: rollback, exit 1"
else fail "/health fails (exit $code, requests: $(requests))"; fi

run "$SHA" MKC_SMOKE_EXPECT_COMMIT=wrong-commit
if [ "$code" -eq 1 ] && [ "$(requests)" = "deploy $SHA|rollback|" ]; then
  pass "forced failure (MKC_SMOKE_EXPECT_COMMIT): rollback, exit 1"
else fail "forced failure (exit $code, requests: $(requests))"; fi

run "$SHA" STUB_DEPLOY_EXIT=1
if [ "$code" -eq 1 ] && [ "$(requests)" = "deploy $SHA|" ]; then
  pass "helm upgrade fails: no extra rollback (Helm rolled back itself), exit 1"
else fail "deploy fails (exit $code, requests: $(requests))"; fi

run "$SHA" STUB_API_COMMIT="$OLD" STUB_ROLLBACK_EXIT=3
if [ "$code" -eq 1 ] && grep -q "no earlier revision" "$WORK/out"; then
  pass "first install fails the smoke test: says there is nothing to roll back to"
else fail "rollback without an earlier revision (exit $code)"; fi

echo
if [ "$fails" -gt 0 ]; then echo "$fails test(s) failed"; exit 1; fi
echo "all cd_deploy tests passed"
