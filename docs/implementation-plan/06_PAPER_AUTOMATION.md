# Phase 6: Paper Automation and Claim Audit Implementation Plan

> **For agentic workers:** Execute only this file after offline Phases 1, 2, 4, and 5 pass. Phase 3 and external-tool results may be blocked, but unsupported rows must not appear as completed evidence.

**Goal:** Make both paper variants consume the same generated results and prevent unsupported empirical claims from entering a release PDF.

**Architecture:** A selected-artifact manifest identifies exact evidence by path and hash. Pure renderers transform derived JSON into small LaTeX fragments. A claim registry maps every empirical claim to artifacts. A release command validates freshness, renders tables, audits claims, and compiles both documents.

**Tech Stack:** Python 3.12, Pydantic 2, Jinja2 with strict undefined variables, latexmk/pdflatex, existing artifact modules.

## File Map

- Modify `pyproject.toml`: add `Jinja2>=3.1,<4`.
- Create `configs/paper_artifacts.yaml`: explicit selected artifacts and hashes.
- Create `configs/claims.yaml`: claim-to-evidence registry.
- Create `ait/paper/__init__.py`.
- Create `ait/paper/models.py`: manifest and claim models.
- Create `ait/paper/render_tables.py`.
- Create `ait/paper/audit_claims.py`.
- Create `ait/paper/check_stale.py`.
- Create `ait/paper/templates/*.tex.j2`.
- Create `tests/paper/test_render_tables.py`.
- Create `tests/paper/test_audit_claims.py`.
- Create `tests/paper/test_check_stale.py`.
- Modify `main.tex` and `report.tex`: replace numerical tables with `\input`.
- Modify `Makefile`: add experiment, render, audit, PDF, and release targets.
- Create `docs/REPRODUCIBILITY.md`.
- Create `results/generated/README.md`.

## Task 1: Explicit Artifact Selection

`configs/paper_artifacts.yaml` must use exact paths and SHA-256 values:

```yaml
schema_version: "1.0.0"
offline_manifest:
  path: results/derived/offline_manifest.json
  sha256: "<actual hash>"
scenario_metrics:
  path: results/derived/scenario_metrics.json
  sha256: "<actual hash>"
live_runs:
  github_readonly: null
  github_smoke: null
  notion_readonly: null
tool_comparison: null
```

Null means unavailable and must render as `NOT RUN` or omit the empirical row, according to the template. The renderer must never auto-select the newest or best run.

Tests:

- hash mismatch fails;
- missing file fails;
- null optional artifact is accepted but unavailable;
- wrong schema version fails.

## Task 2: Claim Registry

Every empirical claim receives an ID:

```yaml
schema_version: "1.0.0"
claims:
  - id: mock-overall-f1
    text_pattern: "Overall.*F1"
    documents: [main.tex, report.tex]
    evidence:
      artifact: scenario_metrics
      json_pointer: /payload/micro/f1
    required: true
  - id: live-github-policy-mismatch
    text_pattern: "GitHub.*policy"
    documents: [main.tex, report.tex]
    evidence:
      artifact: github_smoke
      json_pointer: /payload/report/findings
    required: false
```

The audit must:

- verify every registry pattern occurs in declared documents;
- verify required evidence exists and the JSON pointer resolves;
- reject numeric empirical sentences marked by `% CLAIM:<id>` when the ID is absent;
- reject claims whose artifact is null;
- allow design, background, and limitation prose without evidence IDs.

Add `% CLAIM:<id>` immediately above each empirical paragraph or table inclusion.

## Task 3: Deterministic Table Rendering

Implement:

```python
def render_all(manifest_path: Path, output_dir: Path) -> list[Path]: ...
```

Use Jinja `StrictUndefined`, fixed sorting, explicit escaping, and these fragments:

- `mock_detection_results.tex`;
- `platform_scenario_results.tex`;
- `live_results.tex` only when selected live artifacts exist;
- `replay_results.tex`;
- `risk_sensitivity.tex`;
- `benchmark_results.tex`;
- `robustness_results.tex`;
- `tool_comparison.tex`;
- `artifact_provenance.tex`.

Every generated fragment begins:

```tex
% GENERATED FILE — DO NOT EDIT
% Source manifest: configs/paper_artifacts.yaml
% Generator: ait.paper.render_tables
```

Formatting rules:

- counts as integers;
- P/R/F1 and interval bounds to three decimals;
- risk scores to two decimals, removing trailing `.00` only for display;
- timings to three decimals with median, p95, and MAD;
- unavailable optional rows display `NOT RUN`, never `0`, `No FP`, or `No finding`.

Golden-file tests use tiny test artifacts under `tests/fixtures/paper/`, not production results.

## Task 4: Replace Hand-Written Tables

In both `main.tex` and `report.tex`:

- remove hardcoded experiment rows;
- retain section interpretation but update values/claims to match generated evidence;
- insert `\input{results/generated/<fragment>.tex}`;
- describe perfect controlled scores, if still observed, as implementation validation rather than broad effectiveness;
- call platform cases “platform-inspired mock scenarios”;
- call incident cases “researcher-constructed traces from public disclosures”;
- call Phase 3 an “instrumented live probe”;
- report metric denominators and uncertainty;
- report benchmark hardware and repetition protocol;
- remove references to `ait/live_runner.py` only if Phase 3 implementation is absent;
- never say RESTler/EvoMaster were run if selected artifacts are null.

Do not preserve old numbers for narrative continuity. The generated artifacts are authoritative.

## Task 5: Staleness Detection

Implement a checker that hashes:

- scenario YAML;
- incident YAML and `SOURCES.md`;
- evaluation protocol;
- risk-weight source file;
- experiment source modules;
- selected raw and derived artifacts.

Store input hashes in the offline manifest. `check_stale` exits non-zero if current inputs differ from recorded hashes.

Tests must change one fixture byte and prove stale detection fails.

## Task 6: Reproducibility Documentation

`docs/REPRODUCIBILITY.md` must contain:

1. tested OS/Python/uv/LaTeX/Docker versions;
2. clean setup;
3. offline one-command reproduction;
4. live credentials and safety constraints;
5. external-tool setup and fixed budgets;
6. artifact directory meanings;
7. exact paper compilation commands;
8. expected runtime and disk use;
9. how to verify hashes;
10. known unavailable artifacts;
11. ethical handling of synthetic and sandbox data.

No secret values or private sandbox identifiers.

## Task 7: Release Make Targets

Add:

```make
.PHONY: experiments-offline experiments-live render-paper audit-claims \
	check-stale paper-main paper-report research-artifact

experiments-offline:
	uv run python -m ait.experiments.run_offline --output-root results

experiments-live:
	@echo "Run explicit plans from docs/REPRODUCIBILITY.md; no automatic credentialed calls."

render-paper:
	uv run python -m ait.paper.render_tables \
	  --manifest configs/paper_artifacts.yaml \
	  --output results/generated

audit-claims:
	uv run python -m ait.paper.audit_claims

check-stale:
	uv run python -m ait.paper.check_stale

paper-main:
	latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

paper-report:
	latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex

research-artifact:
	$(MAKE) check
	$(MAKE) experiments-offline
	$(MAKE) check-stale
	$(MAKE) render-paper
	$(MAKE) audit-claims
	$(MAKE) paper-main
	$(MAKE) paper-report
```

If `latexmk` is unavailable, setup documentation must name the exact package; do not silently skip PDF compilation.

## Task 8: Final Claim Audit

Search both papers for every numeral in evaluation sections and classify it as:

- generated result;
- protocol constant;
- cited external fact;
- equation/example;
- unsupported.

Move generated results into fragments. Add citations for external facts. Label examples as examples. Remove unsupported numbers.

Explicitly inspect these legacy claims:

- overall P/R/F1 of 1.00;
- seven platform risk scores;
- GitHub risk 30 and Notion risk 0;
- smoke-probe endpoint count;
- CircleCI/Okta/GitHub replay matches;
- ±30% sensitivity rows;
- 0.05/0.22/0.72 ms benchmark values.

None may survive merely because they were in the previous draft.

## Task 9: Release Verification

Run from a clean generated-output state:

```bash
make clean-generated
make research-artifact
uv run python -m ait.artifacts results
git diff --exit-code results/generated  # only when generated fragments are committed
```

Then manually inspect:

- both PDFs contain the same values for shared experiments;
- captions state mock/live/reconstructed status accurately;
- unavailable live/tool rows are not presented as successful results;
- tables include denominators or link to provenance;
- no credentials, user IDs, private repository names, or response values appear.

## Acceptance Criteria

- Both papers compile from shared generated fragments.
- Required offline claims resolve to hashed artifacts.
- Optional unavailable claims are omitted or marked `NOT RUN`.
- Stale inputs fail the release command.
- Every old hand-written result has been regenerated, relabeled as an example, or removed.
- `docs/REPRODUCIBILITY.md` lets an independent reviewer rerun the artifact.
- `make research-artifact` is the single offline release gate.

## Final Handoff to Large-Model Review

Provide the reviewer:

- `docs/implementation-plan/00_MASTER.md`;
- phase completion reports;
- `configs/evaluation_protocol.yaml`;
- `configs/paper_artifacts.yaml`;
- `configs/claims.yaml`;
- offline and optional live/tool manifests;
- both compiled PDFs;
- exact output of `make research-artifact`;
- unresolved blockers and unsupported claims.

Ask the reviewer to audit scientific validity, threat-model consistency, source quality, statistical interpretation, and claim strength—not only code style.
