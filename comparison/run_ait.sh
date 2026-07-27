#!/usr/bin/env bash
# Run AIT scripted client against the isolated comparison target.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${ROOT}/.." && pwd)"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="${REPO}/results/raw/tool-comparison/ait/${RUN_ID}"
BUDGET_SECONDS="${BUDGET_SECONDS:-600}"
SEED="${SEED:-20260727}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is required but was not found on PATH." >&2
  exit 2
fi

mkdir -p "${OUT}"
cd "${ROOT}"

cleanup() {
  docker compose -f "${ROOT}/docker-compose.yml" down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

{
  echo "tool=ait"
  echo "run_id=${RUN_ID}"
  echo "seed=${SEED}"
  echo "budget_seconds=${BUDGET_SECONDS}"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${OUT}/run_meta.txt"

docker compose -f "${ROOT}/docker-compose.yml" up -d comparison-target
echo "Waiting for comparison target health..."
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:8080/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS "http://127.0.0.1:8080/health" > "${OUT}/health.json"

# Scripted baseline + mutated client hitting documented + hidden + sensitive paths.
python3 - <<'PY' > "${OUT}/exchanges.json"
import json
import urllib.request

base = "http://127.0.0.1:8080"
paths = [
    ("baseline", "/health"),
    ("baseline", "/api/v1/items"),
    ("baseline", "/api/v1/items/item-1"),
    ("mutated", "/health"),
    ("mutated", "/api/v1/items"),
    ("mutated", "/api/v1/items/item-1"),
    ("mutated", "/api/v1/hidden/export"),
]
exchanges = []
for phase, path in paths:
    with urllib.request.urlopen(base + path) as resp:
        body = resp.read().decode()
        exchanges.append(
            {
                "phase": phase,
                "method": "GET",
                "path": path,
                "status_code": resp.status,
                "response_body": json.loads(body),
            }
        )
print(json.dumps({"exchanges": exchanges}, indent=2, sort_keys=True))
PY

cd "${REPO}"
uv run python - <<PY > "${OUT}/findings.json" 2>"${OUT}/stderr.txt" || true
import json
from pathlib import Path
import yaml
from ait.analysis import analyze_run
from ait.models import CapturedExchange, TargetConfig

policy = yaml.safe_load(Path("comparison/policy.yaml").read_text())
# Map policy YAML into TargetConfig fields.
target = TargetConfig(
    name=policy["name"],
    environment=policy.get("environment", "comparison"),
    base_url=policy["base_url"],
    integration_sync_url=policy["integration_sync_url"],
    audit_base_url=policy["audit_base_url"],
    expected_endpoints=policy.get("expected_endpoints", []),
    sensitive_markers=policy.get("sensitive_markers", []),
    description=policy.get("description", ""),
)
raw = json.loads(Path("${OUT}/exchanges.json").read_text())
captured = [
    CapturedExchange(
        run_id="${RUN_ID}",
        phase=item["phase"],
        method=item["method"],
        path=item["path"],
        status_code=item["status_code"],
        response_body=item["response_body"],
        extracted_fields=[],
        contains_sensitive_marker=False,
    )
    for item in raw["exchanges"]
]
# Populate sensitive flags via analysis helpers.
from ait.analysis import extract_field_paths, field_matches_sensitive_marker
markers = set(target.sensitive_markers)
for exchange in captured:
    fields = sorted(extract_field_paths(exchange.response_body))
    exchange.extracted_fields = fields
    exchange.contains_sensitive_marker = any(
        field_matches_sensitive_marker(f, markers) for f in fields
    )
report = analyze_run("${RUN_ID}", target, captured)
Path("${OUT}/findings.json").write_text(report.model_dump_json(indent=2))
print(report.model_dump_json(indent=2))
PY

sha256sum "${OUT}"/* > "${OUT}/SHA256SUMS" 2>/dev/null || shasum -a 256 "${OUT}"/* > "${OUT}/SHA256SUMS"
echo "AIT comparison artifacts written to ${OUT}"
