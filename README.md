# Adversarial Integration Tester

Adversarial Integration Tester is a CLI-first prototype for validating whether a SaaS
integration accesses only the data and endpoints it is expected to use.

This repository contains:

- a coordinator API that registers targets and executes assessments
- a mock SaaS service that exposes both expected and hidden endpoints
- a demo integration that behaves differently under a mutated run
- a CLI for launching runs and exporting reports
- an artifact boundary for reproducible research outputs under `results/`

The primary product and implementation documentation lives in
[docs/PRODUCT_ARCHITECTURE.md](docs/PRODUCT_ARCHITECTURE.md).
The phase-by-phase research implementation plan lives in
[docs/implementation-plan/00_MASTER.md](docs/implementation-plan/00_MASTER.md).

## Quick Start

Requires Python 3.12+ and [uv](https://github.com/astral-sh/uv).

```bash
make setup
make check
```

`make setup` synchronizes runtime and development dependencies from `uv.lock`.
`make check` runs Ruff and the pytest suite.

### Demo services

```bash
uv run uvicorn ait.mock_saas:app --port 8001 --reload
uv run uvicorn ait.demo_integration:app --port 8002 --reload
uv run uvicorn ait.api:app --port 8000 --reload
uv run ait run-start demo-integration
```

## Tests

```bash
make test
```

Or:

```bash
uv run pytest
```

## Research Artifacts

Experiment outputs are written under `results/`:

- `results/raw/` — immutable observations
- `results/derived/` — reproducible aggregates
- `results/generated/` — paper LaTeX fragments

Generated artifacts must record the invoking command and schema version. Secrets and
unredacted live payloads must never be committed. Validate existing JSON artifacts with:

```bash
make validate-artifacts
```

## Live SaaS probes (sandbox only)

The live runner (`python -m ait.live_runner`) issues **instrumented, allowlisted**
read-only probes against GitHub or Notion. It is not a transparent integration monitor.

**Safety defaults**

- Methods are `GET`/`HEAD` only unless both `--allow-mutation` and `environment: sandbox`.
- Redirects are rejected (not followed). Hosts must exactly match the plan allowlist.
- At most 20 requests/run, 1 MiB response, 10s timeout; retries only for 429/502/503/504.
- Tokens come **only** from environment variables (`AIT_GITHUB_TOKEN`, `AIT_NOTION_TOKEN`).
  Never pass tokens on the CLI. Missing credentials exit with code `2` and write no artifact.
- Default artifacts store field **names**, digests, and allowlisted headers — not response bodies
  or `Authorization` / `Set-Cookie` headers.
- `--store-bodies` is **disabled** (refused at runtime). It is reserved for a future
  synthetic-only sandbox gate and must not be used with live provider responses.

**Setup**

1. Create least-privilege sandbox credentials (dedicated account/app; no production tokens).
2. Export the token in your shell (or a gitignored `.env` loaded by your shell only):

```bash
export AIT_GITHUB_TOKEN=...   # never commit
export AIT_NOTION_TOKEN=...   # never commit
```

3. Dry-run first (no credentials required; prints resolved URLs only):

```bash
uv run python -m ait.live_runner run --plan configs/live/github_smoke.yaml --dry-run
uv run python -m ait.live_runner run --plan configs/live/notion_readonly.yaml --dry-run
```

4. Run a read-only plan only after reviewing every URL:

```bash
uv run python -m ait.live_runner run \
  --plan configs/live/github_readonly.yaml \
  --output-root results
```

Inspect `results/raw/live/` for accidental PII or tokens before any paper bundle.
Private live dumps belong under `results/raw/live-private/` (gitignored).
Do not invent or substitute mock results when credentials are unavailable.
