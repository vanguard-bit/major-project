# Phase 5: Scientific Validation and Tool Comparison Implementation Plan

> **For agentic workers:** Execute only this file after Phases 2 and 4 pass. Use TDD for code. Docker-based tools are manual-gated and must remain `NOT RUN` when unavailable.

**Goal:** Strengthen the evaluation beyond deterministic happy paths by adding balanced robustness/evasion cases, uncertainty estimates, repeated runs, and a reproducible comparison protocol for RESTler and EvoMaster.

**Architecture:** Extend the labeled corpus with transformations that model noise and evasions. Compute uncertainty from scenario-level counts. Run external tools against the same isolated OpenAPI target, preserve their native reports, and compare only pre-declared observable outcomes.

**Tech Stack:** Existing experiment package, pytest, SciPy-free Wilson interval implementation, Docker, RESTler, EvoMaster.

## Scientific Rules

- Freeze hypotheses and metrics in `configs/evaluation_protocol.yaml` before running experiments.
- Do not tune AIT thresholds or labels after viewing outcomes without recording a new protocol version.
- Scenario is the unit of classification. Repeated deterministic runs measure reproducibility, not sample size.
- Do not claim AIT is “better” from incomparable objectives. RESTler/EvoMaster target server faults; AIT targets client-policy conformance.
- A capability matrix may be qualitative. Any quantitative row must have actual executions and preserved native output.

## File Map

- Create `configs/evaluation_protocol.yaml`.
- Create `configs/scenarios/robustness/*.yaml`.
- Create `configs/scenarios/evasion/*.yaml`.
- Create `ait/experiments/robustness.py`.
- Create `ait/experiments/statistics.py`.
- Create `ait/experiments/reproducibility.py`.
- Create `tests/experiments/test_robustness.py`.
- Create `tests/experiments/test_statistics.py`.
- Create `tests/experiments/test_reproducibility.py`.
- Create `comparison/openapi.yaml`: isolated comparison target specification.
- Create `comparison/target_app.py`: server with declared normal and intentionally faulty endpoints.
- Create `comparison/policy.yaml`: AIT expected-endpoint/field policy.
- Create `comparison/docker-compose.yml`.
- Create `comparison/run_restler.sh`.
- Create `comparison/run_evomaster.sh`.
- Create `comparison/run_ait.sh`.
- Create `comparison/parse_results.py`.
- Create `comparison/README.md`.
- Create `tests/comparison/test_target_app.py`.
- Create `tests/comparison/test_parse_results.py`.

## Task 1: Freeze the Evaluation Protocol

Write `configs/evaluation_protocol.yaml` before corpus execution:

```yaml
schema_version: "1.0.0"
seed: 20260727
unit_of_analysis: scenario
primary_categories:
  - hidden_endpoint
  - sensitive_field_access
  - behavioral_divergence
primary_metrics:
  - per_category_precision
  - per_category_recall
  - per_category_f1
  - micro_precision
  - micro_recall
  - micro_f1
uncertainty:
  method: wilson
  confidence_level: 0.95
repetitions:
  deterministic_offline: 5
failure_policy: count_detector_crash_as_miss
```

Add exact scenario inclusion globs and pre-declared hypotheses:

- H1: hidden endpoint labels are detected under benign log noise;
- H2: sensitive field labels are detected when exposure is partial but field names remain known;
- H3: endpoint order and harmless query variation do not create divergence;
- H4: aliased sensitive fields remain a known false negative;
- H5: delayed/out-of-band/shared-token cases remain outside the detector model.

Hash the protocol into every Phase 5 artifact.

## Task 2: Robustness Corpus

Create independently labeled scenarios for at least:

- 0, 8, 32, and 128 benign health-poll exchanges;
- query parameter order permutations;
- duplicate retries;
- HTTP 429 followed by success;
- partial sensitive-field exposure;
- nested sensitive fields;
- same endpoint set in different order;
- one ambiguous undeclared profile path;
- response bodies with empty dictionaries/lists/null;
- path normalization edge cases.

Each transformation must preserve a `parent_scenario_id` and state whether labels should remain invariant. Implement transformation functions rather than manually copying large exchange lists.

## Task 3: Evasion/Negative Corpus

Add explicit expected misses:

- FN1 out-of-band exfiltration: no observable violating exchange;
- FN2 shared-token misuse: violating exchange attributed to another run ID;
- FN3 delayed activation: violating exchange outside capture window;
- FN4 response-field alias: secret value under an unconfigured alias.

Expected misses are not detector bugs. Record `observable_by_model: false`. Exclude these from primary in-scope recall and report them separately as boundary cases. Add one malformed-input case that must fail validation rather than enter metrics.

## Task 4: Statistics

Implement:

```python
class ProportionInterval(BaseModel):
    successes: int
    trials: int
    estimate: float | None
    lower: float | None
    upper: float | None
    confidence_level: float

def wilson_interval(successes: int, trials: int,
                    confidence_level: float = 0.95) -> ProportionInterval: ...
```

Use `statistics.NormalDist().inv_cdf` so SciPy is unnecessary. Test against known 95% interval values within `1e-6`; reject negative counts, successes greater than trials, and invalid confidence levels. Undefined zero-trial intervals serialize as null.

Report intervals for precision and recall denominators. Do not calculate a fake Wilson interval directly on F1; report F1 as a point estimate and, if needed, a scenario bootstrap added under a separate protocol version.

## Task 5: Reproducibility Runs

Run all offline scenarios five times with seed `20260727`. Compare normalized artifact payloads after removing provenance timestamps and elapsed times.

Derived fields:

- number of repeated runs;
- count with identical finding category sets;
- count with identical risk scores;
- detector crashes;
- mismatch details.

Acceptance requires 5/5 identical deterministic outputs and zero crashes.

## Task 6: Shared Comparison Target

Build a small FastAPI target from `comparison/openapi.yaml` containing:

- normal documented endpoints;
- one undocumented endpoint reachable by a scripted AIT client;
- one documented endpoint returning a configured sensitive field;
- one input that causes a controlled server-side 500;
- one OpenAPI response-schema violation.

Ground-truth classes:

```text
CLIENT_POLICY_HIDDEN_ENDPOINT
CLIENT_POLICY_SENSITIVE_FIELD
SERVER_INTERNAL_ERROR
OPENAPI_RESPONSE_VIOLATION
```

The target must be isolated in Docker with synthetic data and no outbound network access.

## Task 7: External Tool Protocol

Pin exact Docker image digests or released versions in `comparison/README.md`. The scripts must:

- fail if Docker is absent;
- start the isolated target;
- wait for health;
- run the tool with fixed seed/time budget of 10 minutes;
- capture stdout, stderr, exit code, version, configuration, and native report;
- stop containers;
- hash outputs into `results/raw/tool-comparison/<tool>/<run-id>/`.

RESTler:

- compile grammar from `comparison/openapi.yaml`;
- run test/fuzz mode for the fixed budget;
- preserve bug buckets and coverage reports.

EvoMaster:

- run black-box mode against the same OpenAPI URL;
- use the same wall-clock budget;
- preserve generated tests and statistics.

AIT:

- execute its scripted baseline/mutated client against the target;
- preserve exchanges and findings.

Do not expect RESTler/EvoMaster to report AIT categories. Compare each tool against the ground-truth classes it is designed to observe.

## Task 8: Parse Without Overclaiming

`comparison/parse_results.py` must emit:

| Tool | Client-policy hidden endpoint | Sensitive field | Server 500 | OpenAPI violation | Run status |
|---|---:|---:|---:|---:|---|

Values are `DETECTED`, `NOT_DETECTED`, `NOT_APPLICABLE`, `ERROR`, or `NOT_RUN`. `NOT_APPLICABLE` must never be counted as a false negative. Parsing tests use committed minimal native-output fixtures, clearly marked as parser fixtures rather than experimental results.

## Task 9: Verification

Offline:

```bash
make check
uv run python -m ait.experiments.robustness
uv run python -m ait.experiments.reproducibility --repetitions 5
```

External, only when Docker and tool images are available:

```bash
comparison/run_ait.sh
comparison/run_restler.sh
comparison/run_evomaster.sh
uv run python comparison/parse_results.py
```

## Acceptance Criteria

- Protocol is fixed and hashed before result generation.
- Primary metrics separate in-scope scenarios from declared model-boundary cases.
- Wilson intervals include raw denominators.
- Five deterministic repetitions agree exactly.
- External tools run against the same target and fixed budget.
- Missing/error/not-applicable states remain distinct.
- Native external-tool output is retained.
- Paper comparison language reflects differing tool objectives.
