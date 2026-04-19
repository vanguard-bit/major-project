# Adversarial Integration Tester

Adversarial Integration Tester is a CLI-first prototype for validating whether a SaaS integration accesses only the data and endpoints it is expected to use.

This repository contains:

- a coordinator API that registers targets and executes assessments
- a mock SaaS service that exposes both expected and hidden endpoints
- a demo integration that behaves differently under a mutated run
- a live-SaaS runner for explicit sandbox API scenarios
- a CLI for launching runs and exporting reports

The primary product and implementation documentation lives in [docs/PRODUCT_ARCHITECTURE.md](/home/loki/projects/major_project/docs/PRODUCT_ARCHITECTURE.md).

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn ait.mock_saas:app --port 8001 --reload
uvicorn ait.demo_integration:app --port 8002 --reload
uvicorn ait.api:app --port 8000 --reload
ait run-start demo-integration
```

## Tests

```bash
python3 -m pytest tests/test_analysis.py tests/test_end_to_end.py tests/test_paper_results.py tests/test_live_results.py
```

## Evaluation Pipelines

### Controlled Mock Evaluation

Run the paper-style controlled scenarios and regenerate the mock-environment artifacts:

```bash
python3 generate_paper_results.py
```

Outputs are written under `results/`.

### Live SaaS Evaluation

The live runner is for low-volume testing against accounts and workspaces you control. It executes explicit request sequences from YAML files in `live_test_cases/` and writes measured outputs to `results/live_saas/`.

1. Put credentials in shell env vars or a local `.env` file.

```bash
export GITHUB_TOKEN='...'
export NOTION_TOKEN='...'
```

2. Create or edit a scenario file in `live_test_cases/`.
   Use `live_test_cases/github_live_example.yaml.example` as the starting point.

3. Run the live evaluator:

```bash
python3 generate_live_saas_results.py
```

4. Inspect the outputs:

- `results/live_saas/results_table.csv`
- `results/live_saas/summary.json`
- `results/live_saas/skipped.json`

### Live SaaS Safety Notes

- Use only sandboxes, developer tenants, or workspaces you own and are authorized to test.
- Prefer test data over real user data.
- Do not commit tokens or other credentials.
- Keep request volume low and within provider rate limits and developer terms.
