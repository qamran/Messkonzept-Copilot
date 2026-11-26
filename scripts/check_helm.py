"""Check the Helm chart in deploy/helm/mkc/ against the MKC-9 rules.

Static text checks only (the docs job runs this with bare python3, without Helm).
`helm lint` and the install on kind run in the CI job `kind`.

- The chart files exist: Chart.yaml, values.yaml, ci-values.yaml and the templates
  for the API and worker Deployments, the Service, the Ingress and the Secret.
- API Deployment: replicas from values; startup, readiness and liveness probes; resources.
- Worker Deployment: `replicas: 1` written in the template; `strategy: Recreate`;
  `terminationGracePeriodSeconds` of at least 300 (the turn budget, decision 42);
  readiness and liveness probes that run `mkc-worker-health`; the heartbeat file set;
  resources.
- Both Deployments: non-root, read-only root filesystem, no privilege escalation,
  settings and secrets through `envFrom`.
- Ingress: `ingressClassName`, TLS with a secret name and the cert-manager annotation.
- Secret: built from `.Values.secrets`, skipped when `existingSecret` is set.
- values.yaml: no secret values (`secrets: {}`), no `latest` image tag, and resource
  requests and limits for the API and the worker.
- ci-values.yaml (the kind test): Ingress and TLS switched on, so the API server checks them.
- Migrations (MKC-11.1, decision 48): a hook Job runs `alembic upgrade head` before install
  and upgrade, with the same restricted security context as the pods, no retries and a
  deadline. With a chart-built Secret it reads a hook Secret of its own, because on a fresh
  install the chart's Secret doesn't exist yet when pre-install hooks run.

Usage: python scripts/check_helm.py  (exit code 0 = ok, 1 = problems)
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHART = Path("deploy/helm/mkc")
FILES = [
    "Chart.yaml",
    "values.yaml",
    "ci-values.yaml",
    "templates/_helpers.tpl",
    "templates/api-deployment.yaml",
    "templates/worker-deployment.yaml",
    "templates/service.yaml",
    "templates/ingress.yaml",
    "templates/secret.yaml",
    "templates/migrate-job.yaml",
    "templates/migrate-secret.yaml",
]
MIN_GRACE_SECONDS = 300

BOTH_DEPLOYMENTS = {
    r"runAsNonRoot:\s*true": "run as non-root (runAsNonRoot: true)",
    r"readOnlyRootFilesystem:\s*true": "use a read-only root filesystem",
    r"allowPrivilegeEscalation:\s*false": "forbid privilege escalation",
    r"envFrom:": "load settings and secrets with envFrom",
    r"secretRef:": "load the Secret with envFrom/secretRef",
    r"readinessProbe:": "have a readinessProbe",
    r"livenessProbe:": "have a livenessProbe",
    r"resources:": "set resources",
}
API = {
    r"replicas:\s*\{\{-?\s*\.Values\.api\.replicas\b": "take replicas from .Values.api.replicas",
    r"startupProbe:": "have a startupProbe",
    r"path:\s*/health\b": "probe /health",
}
WORKER = {
    r"^\s*replicas:\s*1\s*$": "have 'replicas: 1' written in the template (one worker, lease)",
    r"type:\s*Recreate\b": "use 'strategy: type: Recreate' (never two workers at once)",
    r"mkc-worker-health": "probe with mkc-worker-health",
    r"MKC_WORKER_HEARTBEAT_FILE": "set MKC_WORKER_HEARTBEAT_FILE",
    r"\"mkc-worker\"|- mkc-worker\s*$": "run the mkc-worker command",
}
INGRESS = {
    r"ingressClassName:": "set ingressClassName",
    r"cert-manager\.io/cluster-issuer": "carry the cert-manager.io/cluster-issuer annotation",
    r"^\s*tls:": "have a tls section",
    r"secretName:": "name the TLS secret",
}
SECRET = {
    r"kind:\s*Secret\b": "be a Secret",
    r"\.Values\.secrets\b": "be built from .Values.secrets",
    r"existingSecret": "be skipped when existingSecret is set",
}
RESTRICTED = {
    r"runAsNonRoot:\s*true": "run as non-root (runAsNonRoot: true)",
    r"readOnlyRootFilesystem:\s*true": "use a read-only root filesystem",
    r"allowPrivilegeEscalation:\s*false": "forbid privilege escalation",
    r"drop:\s*\[\s*\"?ALL\"?\s*\]": "drop all capabilities",
    r"type:\s*RuntimeDefault\b": "use the RuntimeDefault seccomp profile",
}
MIGRATE_JOB = {
    r"kind:\s*Job\b": "be a Job",
    r"\.Values\.migrations\.enabled\b": "be switched by .Values.migrations.enabled",
    r"helm\.sh/hook:\s*['\"]?pre-install,pre-upgrade['\"]?": "be a pre-install,pre-upgrade hook",
    r"helm\.sh/hook-delete-policy:\s*['\"]?before-hook-creation": (
        "use hook-delete-policy before-hook-creation"
    ),
    r"\"alembic\",\s*\"upgrade\",\s*\"head\"": "run alembic upgrade head",
    r"backoffLimit:\s*0\s*$": "not retry (backoffLimit: 0): a failed migration fails the release",
    r"activeDeadlineSeconds:\s*\d+": "set activeDeadlineSeconds",
    r"restartPolicy:\s*Never\b": "use restartPolicy: Never",
    r"secretRef:": "load the database secret with envFrom/secretRef",
    r"existingSecret": "use existingSecret when set, else the hook Secret",
}
MIGRATE_SECRET = {
    r"kind:\s*Secret\b": "be a Secret",
    r"helm\.sh/hook:\s*['\"]?pre-install,pre-upgrade['\"]?": "be a pre-install,pre-upgrade hook",
    r"helm\.sh/hook-weight:\s*['\"]?-\d+": "have a negative hook-weight (created before the Job)",
    r"\.Values\.secrets\b": "be built from .Values.secrets",
    r"existingSecret": "be skipped when existingSecret is set",
}


def _text(root: Path, name: str) -> str:
    lines = (root / CHART / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def _require(rel: str, text: str, rules: dict[str, str]) -> list[str]:
    return [f"{rel}: must {what}" for pattern, what in rules.items()
            if not re.search(pattern, text, re.MULTILINE)]


def _grace_problems(rel: str, text: str) -> list[str]:
    match = re.search(r"terminationGracePeriodSeconds:\s*(\d+)\s*$", text, re.MULTILINE)
    if not match:
        return [f"{rel}: must set a numeric terminationGracePeriodSeconds"]
    if int(match.group(1)) < MIN_GRACE_SECONDS:
        return [f"{rel}: terminationGracePeriodSeconds {match.group(1)} is below "
                f"{MIN_GRACE_SECONDS} (the turn budget, decision 42)"]
    return []


def _values_problems(rel: str, text: str) -> list[str]:
    found: list[str] = []
    if not re.search(r"^secrets:\s*\{\}\s*$", text, re.MULTILINE):
        found.append(f"{rel}: must hold no secret values ('secrets: {{}}')")
    if re.search(r"^\s*tag:\s*['\"]?latest['\"]?\s*$", text, re.MULTILINE):
        found.append(f"{rel}: image tag must not be 'latest'")
    for part in ("api", "worker"):
        body = _block(text, part)
        for key in ("requests", "limits"):
            if not re.search(rf"^    {key}:\s*$", body, re.MULTILINE):
                found.append(f"{rel}: {part}.resources.{key} must be set")
    if not re.search(r"^  enabled:\s*true\s*$", _block(text, "migrations"), re.MULTILINE):
        found.append(f"{rel}: migrations.enabled must default to true")
    return found


def _block(text: str, key: str) -> str:
    """The indented lines under a top-level key."""
    match = re.search(rf"^{re.escape(key)}:\s*\n((?:[ \t].*\n|\s*\n)*)", text + "\n", re.MULTILINE)
    return match.group(1) if match else ""


def _ci_values_problems(rel: str, text: str) -> list[str]:
    block = _block(text, "ingress")
    found: list[str] = []
    if not re.search(r"^  enabled:\s*true\s*$", block, re.MULTILINE):
        found.append(f"{rel}: must switch the Ingress on (ingress.enabled: true)")
    if not re.search(r"^  tls:\s*\n(?:    .*\n)*?    enabled:\s*true\s*$", block, re.MULTILINE):
        found.append(f"{rel}: must switch TLS on (ingress.tls.enabled: true)")
    return found


def problems(root: Path = ROOT) -> list[str]:
    missing = [f"{(CHART / name).as_posix()}: file missing" for name in FILES
               if not (root / CHART / name).is_file()]
    if missing:
        return missing
    found: list[str] = []
    for name, rules in [
        ("templates/api-deployment.yaml", {**BOTH_DEPLOYMENTS, **API}),
        ("templates/worker-deployment.yaml", {**BOTH_DEPLOYMENTS, **WORKER}),
        ("templates/ingress.yaml", INGRESS),
        ("templates/secret.yaml", SECRET),
        ("templates/migrate-job.yaml", {**RESTRICTED, **MIGRATE_JOB}),
        ("templates/migrate-secret.yaml", MIGRATE_SECRET),
    ]:
        found += _require((CHART / name).as_posix(), _text(root, name), rules)
    worker = "templates/worker-deployment.yaml"
    found += _grace_problems((CHART / worker).as_posix(), _text(root, worker))
    found += _values_problems((CHART / "values.yaml").as_posix(), _text(root, "values.yaml"))
    found += _ci_values_problems((CHART / "ci-values.yaml").as_posix(),
                                 _text(root, "ci-values.yaml"))
    return found


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
