# Tool comparison protocol (Phase 5)

Isolated OpenAPI target shared by AIT, RESTler, and EvoMaster. Compare only
pre-declared observable outcomes. RESTler/EvoMaster target server faults; AIT
targets client-policy conformance.

## Pinned versions / digests

Replace placeholders **before** any claimed experimental run:

| Component | Pin |
|---|---|
| Comparison target base image | `python:3.12-slim@sha256:DIGEST_PLACEHOLDER_PIN_BEFORE_RUN` |
| RESTler | `mcr.microsoft.com/restlerfuzzer/restler:DIGEST_PLACEHOLDER` |
| EvoMaster | `webrandonyang/evomaster:DIGEST_PLACEHOLDER` |
| Wall-clock budget | 600 seconds (10 minutes) |
| Seed | `20260727` |

Until digests are pinned and images are present locally, `run_restler.sh` /
`run_evomaster.sh` exit with `status=NOT_RUN`. That is expected.

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
uv run python comparison/parse_results.py
```

Scripts fail clearly if Docker is missing. Outputs land under
`results/raw/tool-comparison/<tool>/<run-id>/`.

## Parse statuses

`DETECTED` | `NOT_DETECTED` | `NOT_APPLICABLE` | `ERROR` | `NOT_RUN`

`NOT_APPLICABLE` must never be counted as a false negative.

## Parser fixtures

Files under `tests/comparison/fixtures/` are **parser fixtures only** — not
experimental runs.
