#!/usr/bin/env bash
# kind smoke test for the Helm chart (MKC-9.3). Runs locally (Docker Desktop) and in CI.
#
#   bash scripts/kind_smoke.sh
#
# Builds the backend image, creates a throwaway kind cluster, loads the image, installs
# deploy/helm/mkc with ci-values.yaml and checks:
#   - /health is 200 and /api/version returns the expected commit (through the Service)
#   - the worker pod is Ready and has not restarted
#   - deleting the worker pod sends SIGTERM and the worker logs a clean stop
# The cluster is deleted at the end, also on failure (after printing diagnostics).
# It uses its own KUBECONFIG, so ~/.kube/config and the current context are never touched.
#
# Environment:
#   MKC_COMMIT        commit baked into the image and expected from /api/version
#   MKC_EXPECT_COMMIT commit /api/version must return (default MKC_COMMIT; set it to
#                     something else to see the test fail)
#   KIND_CLUSTER      cluster name (default mkc-smoke); an existing cluster is never reused
#   KIND, HELM, KUBECTL  the binaries (default: from PATH)
#   KIND_SMOKE_PORT   local port for the port-forward (default 18080)
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER="${KIND_CLUSTER:-mkc-smoke}"
COMMIT="${MKC_COMMIT:-kind-$(date +%s)}"
EXPECT_COMMIT="${MKC_EXPECT_COMMIT:-$COMMIT}"
# kind v0.33.0's default node image, pinned by digest (Kubernetes 1.37, like k3s stable).
NODE_IMAGE="kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
KIND="${KIND:-kind}"
HELM="${HELM:-helm}"
KUBECTL="${KUBECTL:-kubectl}"
PORT="${KIND_SMOKE_PORT:-18080}"
CHART=deploy/helm/mkc
IMAGE=mkc-backend:kind
RELEASE=mkc
WORKER_SELECTOR="app.kubernetes.io/instance=${RELEASE},app.kubernetes.io/component=worker"

# Git Bash on Windows: keep arguments as written, and give the Windows binaries a path
# they understand (C:/...), so the kubeconfig lands in the temp dir and nowhere else.
export MSYS_NO_PATHCONV=1
WORK="$(mktemp -d)"
if command -v cygpath >/dev/null 2>&1; then WORK="$(cygpath -m "$WORK")"; fi
export KUBECONFIG="$WORK/kubeconfig"
PF_PID=""
CREATED=""

log() { printf '== %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

diagnostics() {
  log "diagnostics"
  "$KUBECTL" get all,ingress,secret,configmap -o wide || true
  "$KUBECTL" describe pods -l "app.kubernetes.io/instance=${RELEASE}" || true
  "$KUBECTL" get events --sort-by=.lastTimestamp || true
  "$KUBECTL" logs -l "app.kubernetes.io/instance=${RELEASE}" --all-containers --prefix --tail=100 || true
}

cleanup() {
  local status=$?
  set +e
  if [ "$status" -ne 0 ] && [ -n "$CREATED" ]; then diagnostics; fi
  if [ -n "$PF_PID" ]; then kill "$PF_PID" 2>/dev/null; fi
  if [ -n "$CREATED" ]; then
    log "deleting cluster $CLUSTER"
    # Docker Desktop sometimes fails the first container removal; try again.
    for attempt in 1 2 3; do
      "$KIND" delete cluster --name "$CLUSTER" --kubeconfig "$KUBECONFIG" && break
      echo "delete attempt $attempt failed; retrying"
      sleep 5
    done
  fi
  rm -rf "$WORK"
  if [ "$status" -eq 0 ]; then log "kind smoke test passed"; else log "kind smoke test FAILED"; fi
  exit "$status"
}
trap cleanup EXIT

if "$KIND" get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  fail "a kind cluster named $CLUSTER already exists; delete it or set KIND_CLUSTER"
fi

log "building $IMAGE (MKC_COMMIT=$COMMIT)"
docker build --quiet --build-arg "MKC_COMMIT=$COMMIT" -t "$IMAGE" backend

log "creating kind cluster $CLUSTER"
CREATED=1
"$KIND" create cluster --name "$CLUSTER" --image "$NODE_IMAGE" --kubeconfig "$KUBECONFIG" --wait 180s

log "loading $IMAGE into the cluster"
# An image archive works with both Docker image stores (classic and containerd).
docker save "$IMAGE" -o "$WORK/image.tar"
"$KIND" load image-archive "$WORK/image.tar" --name "$CLUSTER"

log "helm install"
"$HELM" install "$RELEASE" "$CHART" -f "$CHART/ci-values.yaml" --wait --timeout 5m
"$KUBECTL" rollout status deployment/mkc-api --timeout=120s
"$KUBECTL" rollout status deployment/mkc-worker --timeout=120s
"$KUBECTL" get ingress mkc-api -o jsonpath='{.metadata.annotations.cert-manager\.io/cluster-issuer} {.spec.tls[0].secretName}{"\n"}'

log "API through the Service (port-forward on 127.0.0.1:$PORT)"
"$KUBECTL" port-forward service/mkc-api "$PORT:80" >"$WORK/port-forward.log" 2>&1 &
PF_PID=$!
health=""
for _ in $(seq 1 30); do
  health="$(curl -fsS "http://127.0.0.1:$PORT/health" 2>/dev/null)" && break
  sleep 1
done
[ "$health" = '{"status":"ok"}' ] || fail "/health returned '$health'"
echo "/health: $health"
version="$(curl -fsS "http://127.0.0.1:$PORT/api/version")"
echo "/api/version: $version"
case "$version" in
  *"\"commit\":\"$EXPECT_COMMIT\""*) ;;
  *) fail "/api/version does not report commit $EXPECT_COMMIT" ;;
esac

worker_state() {
  "$KUBECTL" get pods -l "$WORKER_SELECTOR" \
    -o jsonpath='{range .items[*]}{.metadata.name} ready={.status.containerStatuses[0].ready} restarts={.status.containerStatuses[0].restartCount}{"\n"}{end}'
}

log "worker Ready, no restarts (checked twice, 20 s apart)"
for round in 1 2; do
  state="$(worker_state)"
  echo "$state"
  [ "$(printf '%s\n' "$state" | grep -c .)" -eq 1 ] || fail "expected exactly one worker pod"
  case "$state" in
    *"ready=true restarts=0") ;;
    *) fail "worker not Ready or restarted: $state" ;;
  esac
  if [ "$round" -eq 1 ]; then sleep 20; fi
done

log "graceful stop: delete the worker pod, expect SIGTERM and a clean stop"
pod="$(worker_state | cut -d' ' -f1)"
"$KUBECTL" logs -f "$pod" >"$WORK/worker.log" 2>&1 &
logs_pid=$!
start=$(date +%s)
"$KUBECTL" delete pod "$pod" --wait=true --timeout=330s
echo "pod deleted after $(( $(date +%s) - start )) s (grace period 300 s)"
wait "$logs_pid" || true
cat "$WORK/worker.log"
grep -q "signal SIGTERM received, stopping" "$WORK/worker.log" || fail "worker did not log the SIGTERM"
grep -q "worker stopped" "$WORK/worker.log" || fail "worker did not log a clean stop"

log "the Deployment starts a new worker"
"$KUBECTL" rollout status deployment/mkc-worker --timeout=120s
"$KUBECTL" wait --for=condition=Ready pod -l "$WORKER_SELECTOR" --timeout=120s
worker_state
