# Phase 2: Offline Scenario Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development. Execute only this file after Phase 1 passes.

**Goal:** Replace hand-written mock results with an executable, labeled scenario corpus that computes confusion matrices, precision, recall, and F1 from real AIT output.

**Architecture:** YAML files describe independent ground truth and phase-specific HTTP exchanges. A scripted client issues those exchanges through HTTPX `MockTransport`; the transport returns configured synthetic responses while the executor captures what was actually requested and received. A pure evaluator compares emitted finding categories to labels. Aggregation writes raw per-scenario artifacts and one derived metrics artifact.

**Tech Stack:** Existing AIT modules, Pydantic 2, HTTPX ASGITransport, PyYAML, pytest.

## Global Constraints

- Labels are authored in YAML and must never be derived from `analyze_run`.
- Each positive category requires at least one negative scenario in the corpus.
- The harness must run offline and deterministically.
- Do not assert that platform-inspired mocks exercise real Slack, GitHub, Google, Notion, or Trello APIs.

## File Map

- Modify `pyproject.toml`: add `PyYAML>=6.0,<7`.
- Create `ait/experiments/__init__.py`.
- Create `ait/experiments/schema.py`: scenario and evaluation models.
- Create `ait/experiments/scenario_loader.py`: strict YAML loading.
- Create `ait/experiments/mock_executor.py`: scenario-to-exchange execution.
- Create `ait/experiments/metrics.py`: confusion matrix and aggregate metrics.
- Create `ait/experiments/run_scenarios.py`: CLI and artifact writing.
- Create `configs/scenarios/schema.example.yaml`: documented schema example, excluded from metrics.
- Create `configs/scenarios/crm/*.yaml`: S1, S2, S3 plus compliant controls.
- Create `configs/scenarios/platform/*.yaml`: seven paper scenarios plus category controls.
- Create `tests/experiments/test_scenario_loader.py`.
- Create `tests/experiments/test_mock_executor.py`.
- Create `tests/experiments/test_metrics.py`.
- Create `tests/experiments/test_run_scenarios.py`.

## Public Interfaces

```python
# ait/experiments/schema.py
class ExchangeSpec(BaseModel):
    phase: Literal["baseline", "mutated"]
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    status_code: int = 200
    request_body: dict[str, Any] | list[Any] | str | None = None
    response_body: dict[str, Any] | list[Any] | str | None = None

class ExpectedLabel(BaseModel):
    category: FindingCategory
    endpoint: str | None = None

class ScenarioDefinition(BaseModel):
    schema_version: Literal["1.0.0"]
    id: str
    suite: Literal["crm", "platform"]
    platform_style: str
    description: str
    target: TargetConfig
    exchanges: list[ExchangeSpec]
    expected_labels: list[ExpectedLabel]

class ScenarioOutcome(BaseModel):
    scenario_id: str
    expected_categories: set[FindingCategory]
    observed_categories: set[FindingCategory]
    report: RunReport

def load_scenario(path: Path) -> ScenarioDefinition: ...
async def execute_scenario(scenario: ScenarioDefinition) -> ScenarioOutcome: ...
```

```python
# ait/experiments/metrics.py
class CategoryMetrics(BaseModel):
    category: FindingCategory
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None
    recall: float | None
    f1: float | None

def evaluate_categories(outcomes: Sequence[ScenarioOutcome]) -> list[CategoryMetrics]: ...
def micro_average(metrics: Sequence[CategoryMetrics]) -> CategoryMetrics: ...
```

Undefined precision/recall/F1 must serialize as `null`, not `0` or `1`. Category presence is evaluated once per scenario; duplicate findings in one scenario do not increase TP/FP counts.

## YAML Contract

Every corpus file must follow this shape:

```yaml
schema_version: "1.0.0"
id: crm-s3-combined
suite: crm
platform_style: generic-crm
description: Mutated-only billing access with two sensitive fields.
target:
  name: crm-s3-combined
  base_url: http://mock.invalid/
  integration_sync_url: http://integration.invalid/sync
  audit_base_url: http://mock.invalid/
  expected_endpoints:
    - /api/v1/customers
  sensitive_markers:
    - billing_email
    - tax_id
exchanges:
  - phase: baseline
    method: GET
    path: /api/v1/customers
    response_body:
      - customer_id: cust-001
  - phase: mutated
    method: GET
    path: /api/v1/customers
    response_body:
      - customer_id: cust-001
  - phase: mutated
    method: GET
    path: /api/v1/customers/cust-001/billing
    response_body:
      billing_email: run-marker@example.test
      tax_id: TAX-RUN-MARKER
expected_labels:
  - category: hidden_endpoint
    endpoint: /api/v1/customers/cust-001/billing
  - category: sensitive_field_access
    endpoint: /api/v1/customers/cust-001/billing
  - category: behavioral_divergence
```

## Task 1: Strict Scenario Loading

- [ ] Add PyYAML and refresh `uv.lock`.
- [ ] Test rejection of unknown YAML keys, duplicate scenario IDs, empty exchanges, paths without leading `/`, duplicate exchange records, and unsupported schema versions.
- [ ] Configure all scenario Pydantic models with `extra="forbid"`.
- [ ] Normalize query strings by sorting query pairs while retaining path parameters as observed.
- [ ] Run `uv run pytest tests/experiments/test_scenario_loader.py -v`; expected: pass.

## Task 2: Generalized Offline Execution

- [ ] Write failing tests proving nested response fields are extracted recursively using dotted names, for example `billing.tax_id`.
- [ ] Add a pure helper to `ait.analysis` or a focused new module:

```python
def extract_field_paths(value: Any, prefix: str = "") -> set[str]: ...
```

- [ ] Sensitive matching must support both exact leaf names (`tax_id`) and full dotted paths (`billing.tax_id`).
- [ ] Implement a stateful `httpx.MockTransport` handler that consumes exchange specs in order, rejects method/path mismatches, and returns each configured status/body.
- [ ] `execute_scenario` must use an `httpx.AsyncClient` with that transport to issue every configured request, create one `CapturedExchange` from each actual request/response pair, compute extracted fields from the response, set marker presence from configured sensitive markers, invoke `analyze_run`, and return `ScenarioOutcome`.
- [ ] Use a fixed run ID derived from scenario ID, not random UUIDs.
- [ ] Run executor tests; expected: exact exchange count, phases, endpoint findings, fields, divergence, and risk score.

## Task 3: Independent Metric Computation

- [ ] Write table-driven tests for TP, FP, FN, TN, duplicate observed findings, empty expected sets, and undefined denominators.
- [ ] Implement category-level binary classification across all scenarios.
- [ ] Compute values using:

```text
precision = TP / (TP + FP), undefined if denominator is zero
recall    = TP / (TP + FN), undefined if denominator is zero
F1        = 2PR / (P + R), undefined if P or R is undefined or P+R is zero
```

- [ ] Do not round inside the metric module. Rendering decides display precision.
- [ ] Run `uv run pytest tests/experiments/test_metrics.py -v`.

## Task 4: Author the CRM Corpus

Create at least these files:

- `crm-s1-hidden-both-phases.yaml`: hidden endpoint positive only.
- `crm-s2-sensitive-allowed-path.yaml`: sensitive-field positive only on an allowlisted endpoint.
- `crm-s3-combined.yaml`: hidden + sensitive + divergence.
- `crm-c1-compliant.yaml`: no expected findings.
- `crm-c2-benign-extra-response-field.yaml`: unlisted but non-sensitive response field, no finding.
- `crm-c3-same-endpoints-different-order.yaml`: endpoint order differs, no divergence.

For S1, ensure the hidden endpoint appears in both phases so divergence is false. For S2, ensure every observed path is allowlisted. Validate every file through `load_scenario`.

## Task 5: Author the Platform-Inspired Corpus

Create the seven named scenarios:

1. Slack-style bot token over-access.
2. GitHub-style broad-token repository access.
3. Google-style read-only policy with write attempt.
4. Notion-style read-only integration mutation.
5. Trello-style read-token card creation.
6. Slack-style compliant bot.
7. GitHub-style compliant app.

Add at least three controls so each detector category has a meaningful negative. Use fictional `.invalid` hosts and synthetic payloads. Scenario descriptions must say “style” or “inspired”; never imply vendor execution.

Do not copy risk values from the paper. Let `analyze_run` compute them, then update the paper only in Phase 6.

## Task 6: CLI and Artifacts

Implement:

```bash
uv run python -m ait.experiments.run_scenarios \
  --suite all \
  --scenario-root configs/scenarios \
  --output-root results
```

Behavior:

- discover YAML files in lexical order;
- reject duplicate IDs across files;
- write one raw artifact per scenario to `results/raw/scenarios/<id>.json`;
- write `results/derived/scenario_metrics.json`;
- print scenario ID, expected categories, observed categories, and PASS/FAIL;
- exit `1` if any expected/observed category set differs;
- never use paper values as expected output.

Test the CLI against temporary fixtures and temporary output directories.

## Task 7: Final Verification

Run:

```bash
make check
uv run python -m ait.experiments.run_scenarios --suite all
uv run python -m ait.artifacts results
uv run python -m ait.experiments.run_scenarios --suite all
```

Compare derived payloads from both scenario runs while excluding provenance timestamps. Expected: identical.

## Acceptance Criteria

- All corpus labels are explicit and independently authored.
- At least 13 scenarios run offline (6 CRM and 7 platform-inspired); added controls may increase this count.
- Metrics contain integer TP/FP/FN/TN counts and computed values.
- The CLI fails when detector output disagrees with ground truth.
- Raw artifacts are sufficient to recompute all derived metrics.
- No live-provider or external-validity claim is introduced.

## Handoff to Later Phases

Phases 4–6 may import `ScenarioDefinition`, `ScenarioOutcome`, `load_scenario`, `execute_scenario`, `evaluate_categories`, and `micro_average`. Their names and semantics are frozen after this phase.
