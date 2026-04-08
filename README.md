# Adversarial Integration Tester

Adversarial Integration Tester is a CLI-first prototype for validating whether a SaaS integration accesses only the data and endpoints it is expected to use.

This repository contains:

- a coordinator API that registers targets and executes assessments
- a mock SaaS service that exposes both expected and hidden endpoints
- a demo integration that behaves differently under a mutated run
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
python3 -m pytest tests/test_analysis.py tests/test_end_to_end.py
```
