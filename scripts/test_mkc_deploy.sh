#!/usr/bin/env bash
# MKC-10.3: tests for the deploy user's forced command deploy/vm/mkc-deploy.
#
# Runs the script with stub helm and curl (no cluster, no network) and checks that it
# accepts only "deploy <40-hex sha>", "rollback" and "status", and what it passes to Helm.
# Usage: bash scripts/test_mkc_deploy.sh   (exit 0 = all passed)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/deploy/vm/mkc-deploy"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
SHA="0123456789abcdef0123456789abcdef01234567"
fails=0

# Stub helm: logs its arguments; "history" prints STUB_REVISIONS entries as JSON.
cat > "$WORK/helm" <<'STUB'
#!/usr/bin/env bash
echo "helm $*" >> "$STUB_LOG"
if [ "$1" = "history" ]; then
  out="["; for i in $(seq 1 "${STUB_REVISIONS:-0}"); do
    [ "$i" -gt 1 ] && out+=","; out+="{\"revision\":$i}"; done
  echo "$out]"
fi
exit "${STUB_HELM_EXIT:-0}"
STUB
# Stub curl: logs its arguments and writes a GitHub-style tarball with the chart to -o.
cat > "$WORK/curl" <<'STUB'
#!/usr/bin/env bash
echo "curl $*" >> "$STUB_LOG"
out=""; while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out="$2"; shift; done
src="$(mktemp -d)"; mkdir -p "$src/Messkonzept-Copilot-x/deploy/helm"
cp -r "$STUB_CHART" "$src/Messkonzept-Copilot-x/deploy/helm/mkc"
tar -czf "$out" -C "$src" Messkonzept-Copilot-x; rm -rf "$src"
STUB
chmod +x "$WORK/helm" "$WORK/curl"
echo "image: {}" > "$WORK/values.yaml"

run() {  # run <ssh command> [revisions]; sets $code and $log
  : > "$WORK/log"
  SSH_ORIGINAL_COMMAND="$1" STUB_REVISIONS="${2:-0}" STUB_LOG="$WORK/log" \
    STUB_CHART="$ROOT/deploy/helm/mkc" MKC_DEPLOY_HELM="$WORK/helm" \
    MKC_DEPLOY_CURL="$WORK/curl" MKC_DEPLOY_VALUES="$WORK/values.yaml" \
    HOME="$WORK" bash "$SCRIPT" > "$WORK/out" 2>&1
  code=$?
  log="$(cat "$WORK/log")"
}
pass() { echo "ok   $1"; }
fail() { echo "FAIL $1"; sed 's/^/     | /' "$WORK/out"; fails=$((fails + 1)); }

[ -f "$SCRIPT" ] || { echo "FAIL deploy/vm/mkc-deploy missing"; exit 1; }

# Everything that is not exactly one of the three commands is refused, and nothing runs.
refused=(
  "" "bash" "sh -c id" "helm list -A" "deploy" "deploy abc" "deploy ${SHA:0:39}"
  "deploy ${SHA}0" "deploy ${SHA^^}" "deploy $SHA extra" "deploy $SHA;id" "deploy \$(id)"
  "deploy  $SHA" " deploy $SHA" "deploy $SHA "$'\n'"id" $'deploy '"$SHA"$'\nid'
  "rollback now" "rollback;id" "status; id" "status --all" "scp -t /tmp" "DEPLOY $SHA"
)
for cmd in "${refused[@]}"; do
  run "$cmd"
  if [ "$code" -eq 2 ] && [ -z "$log" ]; then pass "refused: $(printf %q "$cmd")"
  else fail "refused: $(printf %q "$cmd") (exit $code, calls: $log)"; fi
done

run "deploy $SHA"
want="helm upgrade --install mkc "
if [ "$code" -eq 0 ] \
  && grep -q "^curl .*https://codeload.github.com/qamran/Messkonzept-Copilot/tar.gz/$SHA" <<<"$log" \
  && grep -q "^$want.*/deploy/helm/mkc --namespace mkc -f $WORK/values.yaml --set image.tag=$SHA --rollback-on-failure --wait=watcher --timeout 600s$" <<<"$log"
then pass "deploy <sha>: chart from GitHub at the sha, fixed values, timeout 600s"
else fail "deploy <sha> (exit $code, calls: $log)"; fi

: > "$WORK/log"
SSH_ORIGINAL_COMMAND="deploy $SHA" STUB_LOG="$WORK/log" STUB_CHART="$ROOT/deploy/helm/mkc" \
  STUB_HELM_EXIT=1 MKC_DEPLOY_HELM="$WORK/helm" MKC_DEPLOY_CURL="$WORK/curl" \
  MKC_DEPLOY_VALUES="$WORK/values.yaml" HOME="$WORK" bash "$SCRIPT" > "$WORK/out" 2>&1
code=$?
if [ "$code" -ne 0 ]; then pass "deploy fails when helm fails (exit $code)"
else fail "deploy must fail when helm fails"; fi

run "rollback" 1
if [ "$code" -eq 3 ] && ! grep -q "^helm rollback" <<<"$log"; then
  pass "rollback with one revision: refused, no helm rollback (exit 3)"
else fail "rollback with one revision (exit $code, calls: $log)"; fi

run "rollback" 2
if [ "$code" -eq 0 ] \
  && grep -q "^helm rollback mkc --namespace mkc --wait=watcher --timeout 600s$" <<<"$log"
then pass "rollback with two revisions: helm rollback to the previous one"
else fail "rollback with two revisions (exit $code, calls: $log)"; fi

run "status" 2
if [ "$code" -eq 0 ] && grep -q "^helm history mkc --namespace mkc" <<<"$log"; then
  pass "status: helm history"
else fail "status (exit $code, calls: $log)"; fi

echo
if [ "$fails" -gt 0 ]; then echo "$fails test(s) failed"; exit 1; fi
echo "all mkc-deploy tests passed"
