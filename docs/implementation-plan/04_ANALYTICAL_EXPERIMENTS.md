# Phase 4: Analytical Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development. Execute only this file after Phases 1 and 2 pass.

**Goal:** Generate genuine risk-sensitivity, performance-benchmark, and reconstructed-incident replay results from committed code and fixtures.

**Architecture:** Each experiment is an independent module with a pure computation core and a thin CLI/artifact layer. All raw inputs and per-repetition measurements are retained. Aggregates are recomputable and contain no paper formatting.

**Tech Stack:** Python standard library (`timeit`, `statistics`, `hashlib`), Pydantic 2, pytest, existing experiment/artifact modules.

## File Map

- Create `ait/experiments/risk_sensitivity.py`.
- Create `ait/experiments/benchmark_analysis.py`.
- Create `ait/experiments/replay_incidents.py`.
- Create `ait/experiments/run_offline.py`.
- Create `configs/incidents/circleci_2023.yaml`.
- Create `configs/incidents/okta_2022.yaml`.
- Create `configs/incidents/github_2022.yaml`.
- Create `configs/incidents/SOURCES.md`.
- Create `tests/experiments/test_risk_sensitivity.py`.
- Create `tests/experiments/test_benchmark_analysis.py`.
- Create `tests/experiments/test_replay_incidents.py`.

## Task 1: Make Risk Weights Explicit

Before sensitivity analysis, replace magic constants in `ait/analysis.py` with:

```python
class RiskWeights(BaseModel):
    hidden_endpoint: float = 25.0
    sensitive_field: float = 20.0
    divergence: float = 15.0
    cap: float = 100.0

DEFAULT_RISK_WEIGHTS = RiskWeights()

def calculate_risk_score(
    hidden_endpoint_count: int,
    sensitive_field_count: int,
    divergence_count: int,
    weights: RiskWeights = DEFAULT_RISK_WEIGHTS,
) -> float: ...
```

`analyze_run` receives an optional `weights` parameter and delegates to this function. Preserve current default behavior. Decide one numeric contract and test it: internal score is `float`; report serialization rounds to two decimals; paper rendering may show an integer only when mathematically integral.

- [ ] Test zero, cap, fractional perturbed weights, and negative input rejection.
- [ ] Run all existing tests to prove default behavior is unchanged.

## Task 2: Risk Sensitivity Experiment

Public interface:

```python
class SensitivityRow(BaseModel):
    scenario_id: str
    varied_weight: Literal["hidden_endpoint", "sensitive_field", "divergence"]
    multiplier: float
    score: float
    band: Literal["low", "medium", "high", "critical"]

def classify_risk(score: float) -> str: ...
def run_sensitivity(outcomes: Sequence[ScenarioOutcome],
                    multipliers: Sequence[float]) -> list[SensitivityRow]: ...
```

Use exact band boundaries defined once in code and tested. If retaining the paper’s bands, encode and document:

```text
Low: 0–25
Medium: >25–50
High: >50–75
Critical: >75–100
```

Run multipliers `[0.7, 1.0, 1.3]` one weight at a time while holding others fixed. Operate on actual Phase 2 scenario outcomes, not hand-entered counts.

Artifacts:

- raw: one row per scenario/weight/multiplier;
- derived: band transitions and min/max score per scenario.

Tests must reproduce manually verified arithmetic for one fixture but must not hardcode the paper table.

## Task 3: Analysis Micro-Benchmark

Public interface:

```python
class BenchmarkConfig(BaseModel):
    widths: list[int] = [10, 50, 100, 500, 1000]
    warmups: int = 10
    repetitions: int = 100
    seed: int = 20260727

class BenchmarkSummary(BaseModel):
    width: int
    repetitions: int
    median_ms: float
    p95_ms: float
    mad_ms: float
    min_ms: float
    max_ms: float
    risk_scores: list[float]

def build_synthetic_case(width: int, seed: int) -> tuple[TargetConfig, list[CapturedExchange]]: ...
def run_benchmark(config: BenchmarkConfig) -> list[BenchmarkSummary]: ...
```

Requirements:

- each case contains exactly one labeled hidden endpoint and `width - 1` allowlisted endpoints;
- construct inputs outside the timed region;
- use `time.perf_counter_ns`;
- run warmups but do not include them in statistics;
- preserve every measured duration in raw artifacts;
- verify risk score is identical across repetitions;
- record CPU, OS, Python version, process architecture, and whether CPU affinity was set;
- do not compare measurements from different hosts as if controlled.

Test the benchmark with `widths=[10]`, `warmups=1`, `repetitions=3`; assert shape and positive durations, never exact timing.

CLI:

```bash
uv run python -m ait.experiments.benchmark_analysis \
  --widths 10,50,100,500,1000 --warmups 10 --repetitions 100
```

## Task 4: Reconstructed Incident Replay Schema

Each fixture must include:

```yaml
schema_version: "1.0.0"
id: circleci-2023-reconstruction
incident_name: CircleCI 2023
reconstruction: true
source_urls:
  - https://...
source_accessed_utc: "YYYY-MM-DDTHH:MM:SSZ"
documented_behavior:
  - concise statement tied to a cited source
mapping_assumptions:
  - explicit transformation from public statement to synthetic exchange
target:
  # complete TargetConfig
exchanges:
  # synthetic CapturedExchange-compatible entries
expected_labels:
  # independent labels justified by mapping assumptions
```

`SOURCES.md` must explain which exact source passage supports each reconstructed behavior. Use primary vendor postmortems where available. Do not invent precise paths or fields when disclosures do not provide them; use clearly synthetic paths such as `/reconstruction/excess-scope/resource`.

## Task 5: Replay Execution and Evaluation

Implement strict loading and:

```python
class ReplayOutcome(BaseModel):
    incident_id: str
    reconstruction: Literal[True]
    expected_categories: set[FindingCategory]
    observed_categories: set[FindingCategory]
    exact_match: bool
    report: RunReport

def run_replay(path: Path) -> ReplayOutcome: ...
```

Write one raw artifact per reconstruction and a derived match table. The CLI exits non-zero on label mismatch.

The paper must use wording equivalent to: “AIT was applied to researcher-constructed traces derived from public descriptions.” It must not call these “real incident logs.”

## Task 6: Unified Offline Command

Implement:

```bash
uv run python -m ait.experiments.run_offline --output-root results
```

Execution order:

1. scenario suite;
2. risk sensitivity;
3. incident replay;
4. benchmark.

Stop on the first failed experiment. Write a final offline manifest only after all four complete. Manifest entries include artifact paths and SHA-256 hashes.

## Task 7: Verification

```bash
make check
uv run python -m ait.experiments.run_offline --output-root results
uv run python -m ait.artifacts results
```

Independently recompute at least one sensitivity row and benchmark percentile in a test.

## Acceptance Criteria

- Risk weights are explicit and injectable.
- Sensitivity rows come from Phase 2 outcomes.
- Benchmark raw repetitions and machine metadata are preserved.
- Benchmark table reports median, p95, and MAD, not a single unqualified timing.
- Incident traces are clearly reconstructed and source-mapped.
- All experiment CLIs fail on invalid input or detector/label mismatch.
- One offline manifest hashes every included artifact.
