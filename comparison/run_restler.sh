#!/usr/bin/env bash
# RESTler comparison harness. Leaves NOT_RUN semantics when image/tool unavailable.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${ROOT}/.." && pwd)"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="${REPO}/results/raw/tool-comparison/restler/${RUN_ID}"
BUDGET_SECONDS="${BUDGET_SECONDS:-600}"
SEED="${SEED:-20260727}"
# Pin before claiming a real run — placeholder digest is intentional.
RESTLER_IMAGE="${RESTLER_IMAGE:-mcr.microsoft.com/restlerfuzzer/restler:DIGEST_PLACEHOLDER}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is required but was not found on PATH." >&2
  echo "status=NOT_RUN reason=docker_missing" > "${OUT:-/tmp}/status.txt" 2>/dev/null || true
  exit 2
fi

mkdir -p "${OUT}"
{
  echo "tool=restler"
  echo "run_id=${RUN_ID}"
  echo "seed=${SEED}"
  echo "budget_seconds=${BUDGET_SECONDS}"
  echo "image=${RESTLER_IMAGE}"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${OUT}/run_meta.txt"

if [[ "${RESTLER_IMAGE}" == *DIGEST_PLACEHOLDER* ]]; then
  echo "ERROR: RESTler image digest is not pinned (DIGEST_PLACEHOLDER)." >&2
  echo "status=NOT_RUN reason=image_digest_unpinned" | tee "${OUT}/status.txt"
  exit 3
fi

if ! docker image inspect "${RESTLER_IMAGE}" >/dev/null 2>&1; then
  echo "ERROR: RESTler image not available locally: ${RESTLER_IMAGE}" >&2
  echo "status=NOT_RUN reason=image_missing" | tee "${OUT}/status.txt"
  exit 3
fi

cleanup() {
  docker compose -f "${ROOT}/docker-compose.yml" down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose -f "${ROOT}/docker-compose.yml" up -d comparison-target
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:8080/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Compile grammar from OpenAPI, then fuzz for fixed wall-clock budget.
set +e
docker run --rm --network host \
  -v "${ROOT}:/specs:ro" \
  -v "${OUT}:/output" \
  "${RESTLER_IMAGE}" \
  bash -lc "
    set -e
    mkdir -p /output/compile /output/test
    restler compile --api_spec /specs/openapi.yaml --output /output/compile 2>/output/compile_stderr.txt
    timeout ${BUDGET_SECONDS} restler test --grammar_file /output/compile/grammar.py \
      --dictionary_file /output/compile/dict.json \
      --target_ip 127.0.0.1 --target_port 8080 \
      --time_budget \$(echo ${BUDGET_SECONDS}/3600 | bc -l) \
      --output /output/test > /output/stdout.txt 2>/output/stderr.txt
  "
exit_code=$?
set -e
echo "exit_code=${exit_code}" >> "${OUT}/run_meta.txt"
echo "status=COMPLETED" > "${OUT}/status.txt"
sha256sum "${OUT}"/* > "${OUT}/SHA256SUMS" 2>/dev/null || shasum -a 256 "${OUT}"/* > "${OUT}/SHA256SUMS"
echo "RESTler artifacts written to ${OUT}"
exit "${exit_code}"
