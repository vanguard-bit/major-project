#!/usr/bin/env bash
# Start mock SaaS (:8001), demo integration (:8002), coordinator (:8000), and Vite (:5173).
# Invoked by frontend `npm run dev`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"

if [[ ! -d "$FRONTEND/node_modules" ]]; then
  echo "Run: cd frontend && npm install" >&2
  exit 1
fi

set -a
# Repo-root secrets (AIT_*_TOKEN); optional.
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.env"
fi
set +a
export AIT_DEMO_LIVE_PROBES=1

cd "$FRONTEND"
exec npx concurrently \
  --kill-others \
  --kill-signal SIGTERM \
  -n mock,integ,api,vite \
  -c cyan,green,yellow,magenta \
  "cd \"$ROOT\" && uv run uvicorn ait.mock_saas:app --host 127.0.0.1 --port 8001 --reload" \
  "cd \"$ROOT\" && uv run uvicorn ait.demo_integration:app --host 127.0.0.1 --port 8002 --reload" \
  "cd \"$ROOT\" && AIT_DEMO_LIVE_PROBES=1 uv run uvicorn ait.api:app --host 127.0.0.1 --port 8000 --reload" \
  "vite --host 127.0.0.1 --port 5173"
