# Adversarial Integration Tester: Product Architecture and Implementation Guide

## 1. Product Overview

Adversarial Integration Tester, or AIT, is a security testing system for verifying what a third-party SaaS integration actually does at runtime. The prototype in this repository focuses on one core risk: an integration may hold a valid token and appear legitimate, but still access more endpoints or more fields than operators expect.

The current implementation demonstrates that risk with a controlled environment:

- a mock SaaS application exposes normal CRM-style endpoints and one hidden billing endpoint
- a demo integration behaves correctly in one phase and overreaches in another
- the coordinator runs both phases, captures evidence, and produces a report

This repository is not a generic production platform yet. It is a structured proof of concept with enough separation between components to evolve into a more serious internal security tool.

## 2. Product Goals

The prototype is designed to prove these product capabilities:

- register a target integration with expected endpoints, scopes, and sensitive fields
- acquire or inject credentials and run the integration automatically
- seed traceable marker values into sensitive data
- observe which endpoints and fields are actually touched during execution
- compare a baseline run with a mutated run to expose state-dependent behavior
- generate findings with evidence, severity, and a simple risk score

The prototype does not yet attempt to solve:

- broad SaaS vendor support
- browser-driven OAuth authorization
- distributed job execution
- strong secrets management
- durable persistence and historical reporting

## 3. System Architecture

The codebase is organized as a modular monolith with three runtime services and one operator CLI.

It now also includes a direct live-SaaS evaluation path for explicit sandbox scenarios. That path bypasses the mock SaaS and integration services and issues the configured requests directly to real provider APIs.

### 3.1 Components

`AIT Coordinator`

- implemented in [ait/api.py](/home/loki/projects/major_project/ait/api.py)
- exposes APIs for target registration, run execution, run lookup, findings lookup, and report export
- preloads one demo target at startup
- delegates the execution workflow to the runner

`Execution Runner`

- implemented in [ait/runner.py](/home/loki/projects/major_project/ait/runner.py)
- resolves auth material for a target
- seeds sensitive markers into the mock SaaS dataset
- launches the integration twice, once as `baseline` and once as `mutated`
- retrieves the captured audit trail from the mock SaaS
- invokes the analysis engine and returns a complete run record

`Live SaaS Runner`

- implemented in [ait/live_runner.py](/home/loki/projects/test/major_project/ait/live_runner.py)
- reads bearer tokens from environment variables
- executes operator-defined baseline and mutated requests directly against real SaaS APIs
- converts HTTP responses into `CapturedExchange` records without mock-side instrumentation
- adds policy findings when a request expected to be denied succeeds, or a request expected to succeed fails

`Analysis Engine`

- implemented in [ait/analysis.py](/home/loki/projects/major_project/ait/analysis.py)
- compares observed endpoints against expected endpoints
- detects mutated-only behavior
- detects responses that contain configured sensitive fields or marker values
- constructs findings and computes a simple aggregate risk score

`Reporting Layer`

- implemented in [ait/reporting.py](/home/loki/projects/major_project/ait/reporting.py)
- returns structured JSON via the API
- renders an HTML report for human review

`Mock SaaS`

- implemented in [ait/mock_saas.py](/home/loki/projects/major_project/ait/mock_saas.py)
- exposes customer listing, customer detail, notes, and hidden billing APIs
- issues an OAuth-style access token for the demo target
- stores run-specific audit logs keyed by `run_id`
- provides admin endpoints for dataset seeding and audit retrieval

`Demo Integration`

- implemented in [ait/demo_integration.py](/home/loki/projects/major_project/ait/demo_integration.py)
- simulates a third-party service that syncs customer data
- accesses only expected endpoints during the baseline run
- accesses the hidden billing endpoint during the mutated run

`CLI`

- implemented in [ait/cli.py](/home/loki/projects/major_project/ait/cli.py)
- provides a scriptable operator interface for target registration, run creation, run inspection, and report export

### 3.2 Logical Data Flow

The end-to-end interaction for a single assessment is:

1. An operator selects a target by name.
2. The coordinator loads the target configuration from the store.
3. The runner resolves a token using either a static token or OAuth client credentials.
4. The runner calls the mock SaaS seed endpoint to inject run-specific sensitive markers.
5. The runner invokes the integration in `baseline` mode.
6. The integration calls the mock SaaS with `X-Run-Id` and `X-Phase` headers.
7. The mock SaaS records every API call under the current run.
8. The runner invokes the integration again in `mutated` mode.
9. The integration reaches one additional hidden endpoint during the mutated run.
10. The runner retrieves the complete audit log and passes it to the analysis engine.
11. The analysis engine creates findings and a report.
12. The coordinator exposes the results through APIs and the CLI can export them.

## 4. Repository Structure

```text
ait/
  __init__.py
  api.py
  analysis.py
  cli.py
  demo_integration.py
  mock_saas.py
  models.py
  reporting.py
  runner.py
  store.py
configs/
  demo_target.json
docs/
  LIVE_SAAS_EVALUATION.md
  PRODUCT_ARCHITECTURE.md
tests/
  test_analysis.py
  test_end_to_end.py
pyproject.toml
README.md
```

## 5. Data Models and Interfaces

The primary contracts live in [ait/models.py](/home/loki/projects/major_project/ait/models.py).

### 5.1 TargetConfig

Represents a testable integration target.

Key fields:

- `name`: logical identifier for the target
- `base_url`: SaaS base URL
- `integration_sync_url`: endpoint that triggers the integration workflow
- `audit_base_url`: endpoint used to seed data and fetch audit logs
- `auth_type`: `static_token` or `oauth_client_credentials`
- `token_config`: token value or OAuth client settings
- `expected_endpoints`: allowlisted paths the integration is expected to call
- `expected_scopes`: scopes the operator believes should be sufficient
- `sensitive_markers`: field names treated as sensitive evidence markers

### 5.2 TestRunConfig

Represents run-time options for an assessment.

The prototype includes fields such as:

- `crawl_depth`
- `mutation_budget`
- `taint_fields`
- `replay_count`
- `timeout_seconds`
- `rate_limit_per_minute`
- `safety_mode`

Most of these are currently placeholders for future expansion. They exist to define the product surface early.

### 5.3 CapturedExchange

Represents one observed API interaction, including:

- phase
- method
- path
- status code
- request body
- response body
- extracted fields
- whether sensitive marker data was present

### 5.4 Finding and RunReport

`Finding` expresses a single issue with:

- severity
- category
- endpoint
- evidence
- expected behavior
- observed behavior
- remediation guidance

`RunReport` aggregates the result of an entire run:

- endpoints reached
- hidden endpoints
- sensitive fields accessed
- divergence summary
- risk score
- all findings

## 6. Feature Implementation

### 6.1 Target Registration

Implemented in the coordinator API and CLI.

Behavior:

- a target can be preloaded during startup or created explicitly through `POST /targets`
- the CLI can submit a target config from JSON using `ait target-add`
- target definitions are currently stored in memory through [ait/store.py](/home/loki/projects/major_project/ait/store.py)

Current limitation:

- targets are not persisted across coordinator restarts
- live scenario definitions are file-driven and separate from the in-memory coordinator target registry

### 6.2 Authentication Handling

Implemented in [ait/runner.py](/home/loki/projects/major_project/ait/runner.py).

Supported modes:

- static bearer token
- OAuth client credentials

Current behavior:

- for static token targets, the runner reuses the configured token directly
- for OAuth targets, the runner posts client credentials to the token endpoint and extracts `access_token`

Current limitation:

- the prototype does not manage refresh tokens, browser login flows, or secret rotation

### 6.3 Taint Seeding

Implemented through the mock SaaS admin seed API in [ait/mock_saas.py](/home/loki/projects/major_project/ait/mock_saas.py).

Behavior:

- before each run, the coordinator asks the mock SaaS to rewrite sensitive values with run-specific marker data
- `billing_email` and `tax_id` become unique to that run
- any later retrieval of those values becomes strong evidence that the integration accessed sensitive data

Why this matters:

- hidden access is easier to prove when the response contains values that were deliberately planted for that run

### 6.4 Baseline vs Mutated Execution

Implemented jointly in [ait/runner.py](/home/loki/projects/major_project/ait/runner.py) and [ait/demo_integration.py](/home/loki/projects/major_project/ait/demo_integration.py).

Behavior:

- the runner executes the integration twice
- the baseline phase fetches only expected customer and notes data
- the mutated phase fetches the same data and then accesses the hidden billing endpoint

Why this matters:

- some unauthorized behavior only appears after a different state or sequence of calls
- the mutated run models the product requirement for behavioral divergence analysis

### 6.5 Audit Evidence Collection

Implemented in [ait/mock_saas.py](/home/loki/projects/major_project/ait/mock_saas.py).

Behavior:

- every mock SaaS endpoint reads `X-Run-Id` and `X-Phase`
- each endpoint appends a normalized audit record to the in-memory log
- the audit endpoint returns all exchanges for a run to the coordinator

What is captured:

- endpoint path
- HTTP method
- response body
- extracted top-level fields
- whether a sensitive marker was present

### 6.6 Hidden Endpoint Detection

Implemented in [ait/analysis.py](/home/loki/projects/major_project/ait/analysis.py).

Detection logic:

- collect all reached endpoints from the audit log
- compare them against `expected_endpoints`
- any observed path outside the allowlist becomes a `hidden_endpoint` finding

Current behavior in the demo:

- `/api/v1/customers/cust-001/billing` is detected as hidden access

### 6.7 Sensitive Field Detection

Implemented in [ait/analysis.py](/home/loki/projects/major_project/ait/analysis.py).

Detection logic:

- inspect each exchange for extracted fields matching configured sensitive markers
- also check the explicit `contains_sensitive_marker` flag from the audit layer
- emit a `sensitive_field_access` finding when marker values are observed

Current behavior in the demo:

- access to `billing_email` and `tax_id` results in high-severity findings

### 6.8 Behavioral Divergence Analysis

Implemented in [ait/analysis.py](/home/loki/projects/major_project/ait/analysis.py).

Detection logic:

- group observed endpoints by phase
- compute baseline-only and mutated-only paths
- if the mutated run reached additional endpoints, emit a `behavioral_divergence` finding

Current behavior in the demo:

- the billing endpoint appears only in the mutated run and is surfaced accordingly

### 6.9 Report Generation

Implemented in [ait/reporting.py](/home/loki/projects/major_project/ait/reporting.py) and exposed through [ait/api.py](/home/loki/projects/major_project/ait/api.py).

Available formats:

- JSON for machine-readable processing
- HTML for manual review and presentation

The report currently includes:

- run metadata
- hidden endpoints
- sensitive fields accessed
- divergence summary
- risk score
- full finding list

## 7. Runtime APIs and CLI

### 7.1 Coordinator API Endpoints

Defined in [ait/api.py](/home/loki/projects/major_project/ait/api.py).

- `GET /health`
  - health check for the coordinator
- `GET /targets`
  - returns registered targets
- `POST /targets`
  - registers a new target
- `POST /runs`
  - starts an assessment for a target
- `GET /runs/{run_id}`
  - returns the run record
- `GET /runs/{run_id}/findings`
  - returns the findings only
- `GET /runs/{run_id}/report?format=json|html`
  - returns the report in JSON or HTML form

### 7.2 CLI Commands

Defined in [ait/cli.py](/home/loki/projects/major_project/ait/cli.py).

- `ait target-add <config_path>`
- `ait run-start <target_name>`
- `ait run-status <run_id>`
- `ait report-export <run_id> <output_path> [--format json|html]`

The CLI is intentionally thin. It delegates all stateful work to the coordinator API.

## 8. Running the System

### 8.1 Prerequisites

- Python 3.12 or newer
- `pip`
- three terminals or a process manager

### 8.2 Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 8.3 Starting the Services

Start each service in its own terminal from the repository root.

Terminal 1:

```bash
uvicorn ait.mock_saas:app --port 8001 --reload
```

Terminal 2:

```bash
uvicorn ait.demo_integration:app --port 8002 --reload
```

Terminal 3:

```bash
uvicorn ait.api:app --port 8000 --reload
```

### 8.4 Running the Demo Assessment

The coordinator preloads the demo target during startup, so the simplest run is:

```bash
ait run-start demo-integration
```

The command returns a run record that includes a generated `run_id`.

Check the run:

```bash
ait run-status <run_id>
```

Export reports:

```bash
ait report-export <run_id> report.json
ait report-export <run_id> report.html --format html
```

### 8.5 Registering a Target Explicitly

The sample target configuration is stored in [configs/demo_target.json](/home/loki/projects/major_project/configs/demo_target.json).

To register it manually:

```bash
ait target-add configs/demo_target.json
```

## 9. Testing and Verification

### 9.1 Automated Tests

Two tests currently provide meaningful verification.

`Analysis Unit Test`

- file: [tests/test_analysis.py](/home/loki/projects/major_project/tests/test_analysis.py)
- purpose: validates hidden endpoint and sensitive-field detection from synthetic exchanges

`In-Process End-to-End Test`

- file: [tests/test_end_to_end.py](/home/loki/projects/major_project/tests/test_end_to_end.py)
- purpose: verifies the full assessment workflow without relying on real sockets
- approach: patches `httpx.AsyncClient` with an ASGI transport-backed router so the coordinator, integration, and mock SaaS interact entirely in process

### 9.2 Running the Test Suite

Run the implemented tests with:

```bash
python3 -m pytest tests/test_analysis.py tests/test_end_to_end.py
```

Optional syntax sanity check:

```bash
python3 -m compileall ait tests
```

### 9.3 What the Tests Prove

The tests currently verify:

- the analysis engine flags hidden endpoints
- the analysis engine flags sensitive fields
- the full run pipeline can resolve OAuth credentials
- seed data is written before execution
- baseline and mutated phases both run
- the mutated phase produces additional findings

The tests do not yet verify:

- concurrency behavior
- failure handling for token acquisition
- malformed target configs
- persistence behavior
- rate limiting or safety budgets

## 10. Current Constraints and Next Engineering Steps

### 10.1 Current Constraints

The current prototype intentionally keeps some parts simple:

- storage is in-memory only
- there is no job queue
- the mutation engine is represented by a deterministic `baseline` and `mutated` phase model
- endpoint discovery does not yet crawl real OpenAPI specs dynamically
- findings use a simple weighted score instead of a more formal policy engine

### 10.2 Recommended Next Steps

If this evolves into a stronger internal tool, the next implementation steps should be:

1. Replace [ait/store.py](/home/loki/projects/major_project/ait/store.py) with PostgreSQL-backed persistence.
2. Move run execution into isolated worker processes or containers.
3. Separate endpoint discovery from the demo integration and implement a real OpenAPI-driven crawler.
4. Add stricter field-level extraction and payload normalization in the audit layer.
5. Formalize policy evaluation so expected scopes, allowed endpoints, and allowed fields are independently enforced.
6. Add Docker Compose for reproducible local startup.
7. Add failure-path tests for auth, unreachable targets, and malformed responses.

## 11. Summary

This repository now has a coherent product skeleton rather than an isolated demo script. The coordinator, runner, audit capture, analysis engine, report exporter, CLI, and tests are already wired together around one concrete hidden-access scenario. The most important gap is not architectural clarity anymore; it is hardening and generalization.
