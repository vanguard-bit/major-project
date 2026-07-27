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
