# Tool comparison protocol (Phase 5)

Isolated OpenAPI target shared by AIT, RESTler, and EvoMaster. Compare only
pre-declared observable outcomes. RESTler/EvoMaster target server faults; AIT
targets client-policy conformance.

## Isolation and images

- `docker-compose.yml` uses an **internal** bridge network and a **locally
  prebuilt** `ait-comparison-target:local` image (no runtime `apt`/`pip`).
- Full offline RESTler/EvoMaster toolchain images are heavy; pin digests before
  claiming a run. Until digests are pinned and images exist locally, harness
  scripts exit with `status=NOT_RUN`.
- Build the comparison target:

```bash
docker build -t ait-comparison-target:local \
  -f comparison/Dockerfile.comparison-target comparison/
```

## Pinned versions / digests

Replace placeholders **before** any claimed experimental run:

| Component | Pin |
|---|---|
| Comparison target | `ait-comparison-target:local` (built from `Dockerfile.comparison-target`) |
| RESTler | `mcr.microsoft.com/restlerfuzzer/restler@sha256:…` (set `RESTLER_IMAGE`) |
| EvoMaster | `webrandonyang/evomaster@sha256:…` (set `EVOMASTER_IMAGE`) |
| Wall-clock budget | 600 seconds (10 minutes) |
| Seed | `20260727` |

## Ground-truth classes

| Class | Endpoint / behavior |
|---|---|
| `CLIENT_POLICY_HIDDEN_ENDPOINT` | `GET /api/v1/hidden/export` |
| `CLIENT_POLICY_SENSITIVE_FIELD` | `GET /api/v1/items/{id}` returns `billing_email` |
| `SERVER_INTERNAL_ERROR` | `GET /api/v1/items/{id}/explode` → 500 |
| `OPENAPI_RESPONSE_VIOLATION` | schema-violation returns non-schema `name` |

## Commands

```bash
comparison/run_ait.sh
comparison/run_restler.sh
comparison/run_evomaster.sh
# Explicit run paths required — never auto-picks "latest":
uv run python comparison/parse_results.py \
  --run ait=results/raw/tool-comparison/ait/<RUN_ID> \
  --run restler=results/raw/tool-comparison/restler/<RUN_ID> \
  --run evomaster=results/raw/tool-comparison/evomaster/<RUN_ID>
```

Scripts fail clearly if Docker is missing. Nonzero/timeout tool exits write
`status=ERROR` (not `COMPLETED`). Outputs land under
`results/raw/tool-comparison/<tool>/<run-id>/`.

## Parse statuses

`DETECTED` | `NOT_DETECTED` | `NOT_APPLICABLE` | `ERROR` | `NOT_RUN`

`NOT_APPLICABLE` must never be counted as a false negative.

## Parser fixtures

Files under `tests/comparison/fixtures/` are **parser fixtures only** — not
experimental runs.
