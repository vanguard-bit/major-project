#!/usr/bin/env bash
# EvoMaster black-box comparison harness. Leaves NOT_RUN when image unavailable.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${ROOT}/.." && pwd)"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="${REPO}/results/raw/tool-comparison/evomaster/${RUN_ID}"
BUDGET_SECONDS="${BUDGET_SECONDS:-600}"
SEED="${SEED:-20260727}"
# Pin before claiming a real run — placeholder digest is intentional.
EVOMASTER_IMAGE="${EVOMASTER_IMAGE:-webrandonyang/evomaster:DIGEST_PLACEHOLDER}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is required but was not found on PATH." >&2
  exit 2
fi

mkdir -p "${OUT}"
{
  echo "tool=evomaster"
  echo "run_id=${RUN_ID}"
  echo "seed=${SEED}"
  echo "budget_seconds=${BUDGET_SECONDS}"
  echo "image=${EVOMASTER_IMAGE}"
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${OUT}/run_meta.txt"

if [[ "${EVOMASTER_IMAGE}" == *DIGEST_PLACEHOLDER* ]]; then
  echo "ERROR: EvoMaster image digest is not pinned (DIGEST_PLACEHOLDER)." >&2
  echo "status=NOT_RUN reason=image_digest_unpinned" | tee "${OUT}/status.txt"
  exit 3
fi

if ! docker image inspect "${EVOMASTER_IMAGE}" >/dev/null 2>&1; then
  echo "ERROR: EvoMaster image not available locally: ${EVOMASTER_IMAGE}" >&2
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

set +e
docker run --rm --network host \
  -v "${ROOT}:/specs:ro" \
  -v "${OUT}:/output" \
  "${EVOMASTER_IMAGE}" \
  bash -lc "
    java -jar /evomaster.jar \
      --blackBox true \
      --bbSwaggerUrl http://127.0.0.1:8080/openapi.json \
      --maxTime ${BUDGET_SECONDS}s \
      --seed ${SEED} \
      --outputFolder /output/tests \
      --outputFormat JAVA_JUNIT_5 \
      > /output/stdout.txt 2>/output/stderr.txt
  "
exit_code=$?
set -e
echo "exit_code=${exit_code}" >> "${OUT}/run_meta.txt"
if [[ "${exit_code}" -eq 0 ]]; then
  echo "status=COMPLETED" > "${OUT}/status.txt"
else
  echo "status=ERROR exit_code=${exit_code}" | tee "${OUT}/status.txt"
fi
sha256sum "${OUT}"/* > "${OUT}/SHA256SUMS" 2>/dev/null || shasum -a 256 "${OUT}"/* > "${OUT}/SHA256SUMS"
echo "EvoMaster artifacts written to ${OUT}"
exit "${exit_code}"
