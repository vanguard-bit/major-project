# AIT Research Artifact Master Implementation Plan

> **For agentic workers:** Execute exactly one phase file at a time. Do not infer missing requirements from the paper. If a required artifact cannot be produced, stop and report the blocker; never invent a result.

**Goal:** Turn the current AIT proof of concept into a reproducible research artifact whose code, raw observations, metrics, tables, and paper claims are traceable end to end.

**Architecture:** Experiments produce immutable JSON observations. Pure analysis functions convert observations into metrics. A deterministic renderer converts metrics into LaTeX fragments consumed by both papers. Live experiments are explicitly separated from offline experiments and are skipped, never simulated, when credentials or external tools are unavailable.

**Tech Stack:** Python 3.12, FastAPI, HTTPX, Pydantic 2, Typer, pytest, AnyIO, PyYAML, LaTeX/IEEEtran, optional Docker for RESTler and EvoMaster.

## Global Constraints

- Never hand-write or copy a numerical result into `main.tex` or `report.tex`.
- Never treat a skipped experiment as a pass.
- Never fabricate live observations, benchmark measurements, tool outputs, citations, or incident traces.
- Preserve raw experiment output under `results/raw/`; generated summaries go under `results/derived/`; generated LaTeX goes under `results/generated/`.
- All generated JSON must include schema version, UTC timestamp, git commit when available, Python version, platform, command, and experiment configuration.
- Tokens and secrets must come only from environment variables and must be redacted before writing artifacts or logs.
- Offline runs must be deterministic under seed `20260727`.
- Use exact endpoint matching after URI normalization; query ordering must not affect endpoint identity.
- All new behavior follows test-driven development: failing test, minimal implementation, passing test, then focused commit when the directory is under Git.
- Do not claim external validity from mock experiments.
- Do not describe reconstructed public-incident traces as original incident telemetry.
- Do not modify the risk formula silently. Any formula or weight change requires a schema-version increment and regenerated sensitivity results.

## Current Baseline

The repository currently contains:

- one deterministic CRM demo in `ait/mock_saas.py` and `ait/demo_integration.py`;
- one baseline/mutated runner in `ait/runner.py`;
- endpoint, sensitive-field, and endpoint-set divergence logic in `ait/analysis.py`;
- two tests, covering one S3-like hidden-billing scenario;
- two paper sources, `main.tex` and `report.tex`;
- paper claims for experiments that do not yet have generating code.

The environment currently fails test collection if project dependencies are not installed. There is no `ait/live_runner.py`, scenario corpus, experiment package, benchmark runner, incident fixture corpus, or generated-table pipeline.

## Canonical Data Flow

```text
scenario/live/tool configuration
            |
            v
      experiment runner
            |
            v
results/raw/<experiment>/<run>.json
            |
            v
 pure metric/aggregation modules
            |
            v
results/derived/<experiment>.json
            |
            v
 deterministic LaTeX renderer
            |
            v
results/generated/<table>.tex
            |
            v
 main.tex + report.tex via \input{}
```

## Phase Index and Dependencies

| Phase | File | Depends on | Primary deliverable |
|---|---|---|---|
| 1 | [`01_FOUNDATION.md`](01_FOUNDATION.md) | current repository | reproducible environment, artifact schema, green baseline |
| 2 | [`02_SCENARIO_HARNESS.md`](02_SCENARIO_HARNESS.md) | Phase 1 | executable CRM and platform-inspired scenario corpus with computed P/R/F1 |
| 3 | [`03_LIVE_RUNNER.md`](03_LIVE_RUNNER.md) | Phase 1 | safe GitHub/Notion live probes with redacted raw evidence |
| 4 | [`04_ANALYTICAL_EXPERIMENTS.md`](04_ANALYTICAL_EXPERIMENTS.md) | Phases 1–2 | sensitivity, benchmark, and reconstructed-incident replay artifacts |
| 5 | [`05_SCIENTIFIC_VALIDATION.md`](05_SCIENTIFIC_VALIDATION.md) | Phases 2–4 | robustness corpus, uncertainty estimates, and real tool-comparison protocol |
| 6 | [`06_PAPER_AUTOMATION.md`](06_PAPER_AUTOMATION.md) | Phases 1–5 | generated paper tables, provenance appendix, claim audit, compiled PDFs |

Phase 3 may run in parallel with Phases 2 and 4 after Phase 1. Phase 6 must be last. Live and external-tool rows remain visibly marked `NOT RUN` until their real commands complete.

## Worker Execution Contract

Give a lower-capability coding model only:

1. this master file;
2. one phase file;
3. the repository;
4. the following prompt:

```text
Execute only the assigned AIT phase. Follow its tasks in order and use TDD.
Do not edit paper claims unless the phase explicitly requires it.
Do not invent experimental data or turn skipped checks into passing results.
Run every verification command listed in the phase and report exact outcomes.
Stop when a required dependency, credential, external service, or design
assumption is unavailable. Return changed files, commands run, test results,
artifact paths, and unresolved blockers.
```

The worker must not proceed to the next phase. A stronger review model accepts or rejects the phase using the review gate below.

## Required Phase Handoff

Every phase completion report must contain:

```text
Phase:
Changed files:
New interfaces:
Commands run:
Tests passed:
Tests skipped (with reason):
Raw artifacts produced:
Derived artifacts produced:
Generated LaTeX produced:
Known limitations:
Claims now supported:
Claims still unsupported:
```

## Strong-Model Review Gate

Reject a phase if any answer is “no”:

- Do all listed acceptance commands run from a clean environment?
- Does every result row trace to a raw JSON artifact?
- Are labels independent of detector output?
- Are deterministic experiments repeatable byte-for-byte after excluding timestamps and machine metadata?
- Are secrets absent from repository files and generated artifacts?
- Are skipped live/tool experiments visibly skipped?
- Are precision, recall, F1, and confidence intervals computed from counts rather than constants?
- Do tests include both positive and negative cases?
- Do paper-facing values come from generated fragments only?
- Does the completion report identify unsupported claims honestly?

## Repository-Wide Acceptance Command

Phase 6 must make this command the canonical release gate:

```bash
make research-artifact
```

Expected behavior:

1. creates/synchronizes the environment;
2. runs formatting/static checks selected in Phase 1;
3. runs all offline tests;
4. runs all offline experiments;
5. validates artifact schemas and provenance;
6. renders derived JSON and LaTeX fragments;
7. audits paper claims against artifact availability;
8. compiles both PDFs;
9. exits non-zero if a required offline artifact is absent or stale;
10. reports live/external-tool experiments separately without converting absence to success.

## Definition of Research-Ready

The project is ready for a larger-model paper review only when:

- all offline table values are regenerated by one command;
- live rows are backed by redacted raw API observations produced with sandbox credentials;
- the comparison with RESTler/EvoMaster is backed by preserved command output, or the corresponding paper table is explicitly qualitative;
- at least one non-trivial negative or evasion case is represented;
- metric denominators and confidence intervals are reported;
- benchmark repetitions, warmups, host metadata, median, and dispersion are preserved;
- both paper variants compile from the same generated fragments;
- a claim-to-artifact manifest identifies evidence for each empirical sentence.
