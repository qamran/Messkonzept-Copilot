#!/usr/bin/env bash
# MKC-10.4: deploy one commit to the k3s VM, smoke-test it, roll back on failure.
# Run by the CD job "backend" (cd.yml); also by hand for the rollback drill (runbook).
#
#   scripts/cd_deploy.sh <40-hex commit>
#
# Needs: MKC_DEPLOY_KEY_FILE (the deploy key) and MKC_KNOWN_HOSTS_FILE (the VM's pinned host
# key). The VM side is the forced command deploy/vm/mkc-deploy.
# Options: MKC_DEPLOY_HOST (92.6.240.17), MKC_API_URL (https://92-6-240-17.sslip.io),
# MKC_SMOKE_ATTEMPTS (30) and MKC_SMOKE_INTERVAL (10 s): the first certificate can take a
# minute. MKC_SMOKE_EXPECT_COMMIT forces a mismatch for the rollback drill.
# Exit codes: 0 deployed and healthy, 1 failed (rolled back where possible), 2 bad usage.
set -euo pipefail

sha="${1:-}"
if ! [[ "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: $0 <40-hex commit>" >&2
  exit 2
fi
key="${MKC_DEPLOY_KEY_FILE:?MKC_DEPLOY_KEY_FILE is not set}"
known_hosts="${MKC_KNOWN_HOSTS_FILE:?MKC_KNOWN_HOSTS_FILE is not set}"
host="${MKC_DEPLOY_HOST:-92.6.240.17}"
api="${MKC_API_URL:-https://92-6-240-17.sslip.io}"
expect="${MKC_SMOKE_EXPECT_COMMIT:-$sha}"
attempts="${MKC_SMOKE_ATTEMPTS:-30}"
interval="${MKC_SMOKE_INTERVAL:-10}"

vm() {
  ssh -i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$known_hosts" -o ConnectTimeout=20 "mkc-deploy@$host" "$1"
}

smoke() {
  local i version commit
  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS --proto '=https' --max-time 10 "$api/health" > /dev/null \
      && version="$(curl -fsS --proto '=https' --max-time 10 "$api/api/version")"; then
      commit="$(sed -n 's/.*"commit":"\([^"]*\)".*/\1/p' <<<"$version")"
      if [ "$commit" = "$expect" ]; then
        echo "smoke test passed: /health ok, /api/version commit $commit"
        return 0
      fi
      echo "attempt $i/$attempts: /api/version commit '$commit', expected '$expect'"
    else
      echo "attempt $i/$attempts: $api not healthy yet"
    fi
    [ "$i" -lt "$attempts" ] && sleep "$interval"
  done
  return 1
}

echo "deploying $sha to $host"
if ! vm "deploy $sha"; then
  # helm upgrade --rollback-on-failure has already put the previous release back.
  echo "deploy failed; Helm rolled the release back itself" >&2
  exit 1
fi

if smoke; then
  exit 0
fi

echo "smoke test failed; rolling back" >&2
rc=0
vm rollback || rc=$?
if [ "$rc" -eq 0 ]; then
  echo "rolled back to the previous revision" >&2
elif [ "$rc" -eq 3 ]; then
  echo "no earlier revision to roll back to (first install); the failed release stays" >&2
else
  echo "rollback failed (exit $rc); see the runbook 'Deploy and rollback'" >&2
fi
exit 1
