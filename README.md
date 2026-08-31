# Adversarial Integration Tester

Adversarial Integration Tester validates whether a SaaS integration accesses only
the data and endpoints it is expected to use.

**Faculty demo (install + Demo → Live walkthrough):** see
[FACULTY_DEMO.md](FACULTY_DEMO.md).

This repository contains:

- a coordinator API that registers targets and executes assessments
- a mock SaaS service that exposes both expected and hidden endpoints
- a demo integration that behaves differently under a mutated run
- a CLI for launching runs and exporting reports
- a Vite SPA for the faculty Demo / Live flow
- an artifact boundary for reproducible research outputs under `results/`

The primary product and implementation documentation lives in
[docs/PRODUCT_ARCHITECTURE.md](docs/PRODUCT_ARCHITECTURE.md).
The phase-by-phase research implementation plan lives in
[docs/implementation-plan/00_MASTER.md](docs/implementation-plan/00_MASTER.md).

## Quick Start

Requires Python 3.12+, [uv](https://github.com/astral-sh/uv), and Node.js 20+ for the SPA.
Make is **not** required (`make setup` is only an optional alias for `uv sync --dev`).

### Clone → install → run the faculty demo

```bash
git clone <this-repo-url>
cd major_project
git checkout main

uv sync --dev
cd frontend && npm install && cd ..
```

Optional: put sandbox tokens in a gitignored repo-root `.env`
(`AIT_GITHUB_TOKEN`, `AIT_GOOGLE_TOKEN`, `AIT_NOTION_TOKEN`), or paste them in the
Live UI later. Live plan YAML under `configs/live/` is tracked in git.

Full stack (mock SaaS :8001, demo integration :8002, API :8000 with
`AIT_DEMO_LIVE_PROBES=1`, Vite :5173):

- **macOS / Linux:** `cd frontend && npm run dev`
  (`scripts/npm-dev-stack.sh` sources repo-root `.env` if present)
- **Windows:** four separate PowerShell windows — see
  [FACULTY_DEMO.md](FACULTY_DEMO.md#windows-four-terminals--run-one-command-each)

Open [http://127.0.0.1:5173](http://127.0.0.1:5173), then:
**Demo → Start demo assessment → results → Live → pick a cell → paste key → results**.
Full walkthrough: [FACULTY_DEMO.md](FACULTY_DEMO.md).

```bash
uv run ruff check ait tests && uv run pytest
```

Or, if Make is installed: `make check`.

### CLI-only demo services

Does not enable Live paste-token probes (`AIT_DEMO_LIVE_PROBES`). For the SPA
Live flow, use `npm run dev` (or the Windows four-terminal setup) instead.

```bash
uv run uvicorn ait.mock_saas:app --host 127.0.0.1 --port 8001 --reload
uv run uvicorn ait.demo_integration:app --host 127.0.0.1 --port 8002 --reload
uv run uvicorn ait.api:app --host 127.0.0.1 --port 8000 --reload
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
read-only probes against GitHub, Google, or Notion. It is not a transparent
integration monitor.

The faculty SPA Live page can also run these plans with a pasted token when the
coordinator is started with `AIT_DEMO_LIVE_PROBES=1` (as `npm run dev` does).
CLI runs still take tokens **only** from the environment — never from argv.

**Safety defaults**

- Methods are `GET`/`HEAD` only unless both `--allow-mutation` and `environment: sandbox`.
- Redirects are rejected (not followed). Hosts must exactly match the plan allowlist.
- At most 20 requests/run, 1 MiB response, 10s timeout; retries only for 429/502/503/504.
- CLI tokens come **only** from environment variables
  (`AIT_GITHUB_TOKEN`, `AIT_GOOGLE_TOKEN`, `AIT_NOTION_TOKEN`).
  Never pass tokens on the CLI. Missing credentials exit with code `2` and write no artifact.
- Default artifacts store field **names**, digests, and allowlisted headers — not response bodies
  or `Authorization` / `Set-Cookie` headers.
- `--store-bodies` is **disabled** (refused at runtime). It is reserved for a future
  synthetic-only sandbox gate and must not be used with live provider responses.

**Setup**

1. Create least-privilege sandbox credentials (dedicated account/app; no production tokens).
2. Put tokens in a gitignored repo-root `.env` (auto-sourced by `npm run dev`) or export them
   in your shell:

```bash
export AIT_GITHUB_TOKEN=...   # never commit
export AIT_GOOGLE_TOKEN=...   # never commit
export AIT_NOTION_TOKEN=...   # never commit
```

3. Dry-run first (no credentials required; prints resolved URLs only):

```bash
uv run python -m ait.live_runner run --plan configs/live/github_smoke.yaml --dry-run
uv run python -m ait.live_runner run --plan configs/live/google_readonly.yaml --dry-run
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
