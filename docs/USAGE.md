# AIT Usage Guide

## Quick Start

### 1. Install

```bash
pip install -e .
# or
pip install -r requirements.txt
```

### 2. Start the services

```bash
# Terminal 1 – Mock SaaS (target API)
uvicorn ait.mock_saas:app --port 8001

# Terminal 2 – Demo Integration (third-party app under test)
uvicorn ait.demo_integration:app --port 8002

# Terminal 3 – AIT Coordinator API
uvicorn ait.api:app --port 8000
```

### 3. Run an assessment

```bash
ait run-start demo-integration
```

Or via the API:

```bash
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"target_name": "demo-integration"}'
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `ait target-add <config.json>` | Register a new target configuration |
| `ait run-start <target-name>` | Start an assessment run |
| `ait run-status <run-id>` | Check the status of a run |
| `ait report-export <run-id> <output>` | Export a report (json/html/pdf/csv) |

### Export formats

```bash
# JSON report
ait report-export abc123 report.json --format json

# HTML report
ait report-export abc123 report.html --format html

# Interactive dashboard
ait report-export abc123 dashboard.html --format dashboard

# PDF executive summary
ait report-export abc123 report.pdf --format pdf

# CSV findings export
ait report-export abc123 findings.csv --format csv

# Compliance CSV
ait report-export abc123 compliance.csv --format compliance_csv
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/targets` | List registered targets |
| POST | `/targets` | Register a new target |
| POST | `/runs` | Start a new assessment run |
| GET | `/runs` | List all runs (filter by `?target_name=`) |
| GET | `/runs/{run_id}` | Get full run record |
| GET | `/runs/{run_id}/findings` | Get security findings only |
| GET | `/runs/{run_id}/compliance` | Get compliance reports |
| GET | `/runs/{run_id}/report?format=json` | Get report (json/html/dashboard/pdf/csv/compliance_csv) |

---

## Storage Configuration

By default, AIT persists data to `ait.db` (SQLite).

```bash
# Use a specific SQLite file
export AIT_DATABASE_URL=sqlite:///./my_assessments.db

# Use PostgreSQL for production
export AIT_DATABASE_URL=postgresql://ait_user:password@db-host:5432/ait

# Use in-memory store (no persistence, useful for tests)
export AIT_USE_MEMORY_STORE=1
```

---

## Custom Plugins

Create a custom detector by subclassing `BaseDetectorPlugin`:

```python
# my_plugins/custom_detector.py
from ait.models import CapturedExchange, Finding, FindingCategory, Severity, TargetConfig
from ait.plugins.base import BaseDetectorPlugin


class CustomDetector(BaseDetectorPlugin):
    name = "custom_detector"
    version = "1.0.0"
    description = "Detects my custom security issue."

    def detect(
        self,
        target: TargetConfig,
        exchanges: list[CapturedExchange],
    ) -> list[Finding]:
        findings = []
        for exchange in exchanges:
            if exchange.path.startswith("/api/v1/admin"):
                findings.append(
                    Finding(
                        severity=Severity.CRITICAL,
                        category=FindingCategory.POLICY_VIOLATION,
                        endpoint=exchange.path,
                        title="Admin endpoint accessed",
                        evidence=f"Access to {exchange.path} detected",
                        expected_behavior="Admin endpoints must not be accessed by integrations.",
                        observed_behavior=f"Called {exchange.method} {exchange.path}",
                        remediation_note="Remove admin endpoint access from the integration.",
                    )
                )
        return findings
```

### Register the plugin

```python
from ait.plugins.registry import default_registry
from my_plugins.custom_detector import CustomDetector

default_registry.register(CustomDetector)
```

### Auto-discover from a directory

```python
from pathlib import Path
from ait.plugins.registry import default_registry

default_registry.load_from_directory(Path("my_plugins/"))
```

---

## Compliance Checks

AIT automatically runs compliance checks after each assessment. The following standards are supported:

| Standard | Controls Checked |
|----------|-----------------|
| SOC 2 | CC6.1 (Access Controls), CC6.6 (Security Measures), CC7.2 (Monitoring), CC8.1 (Change Management) |
| GDPR | Art.5(1)(c) (Data Minimisation), Art.25 (Privacy by Design), Art.32 (Security) |
| HIPAA | §164.312(a)(1) (Access Control), §164.312(b) (Audit), §164.312(e)(1) (Transmission) |
| PCI DSS | Req.3 (Stored Data), Req.6 (Secure Systems), Req.7 (Access Restriction), Req.10 (Logging) |

Access compliance results via:

```bash
curl http://127.0.0.1:8000/runs/{run_id}/compliance
```

---

## Target Configuration

Create a `target.json` file:

```json
{
  "name": "my-saas-integration",
  "environment": "staging",
  "base_url": "https://api.myapp.com/",
  "integration_sync_url": "https://integration.myapp.com/sync",
  "audit_base_url": "https://api.myapp.com/",
  "auth_type": "oauth_client_credentials",
  "token_config": {
    "token_url": "https://auth.myapp.com/oauth/token",
    "client_id": "ait-test-client",
    "client_secret": "ait-test-secret",
    "scope": "read:customers"
  },
  "expected_endpoints": [
    "/api/v1/customers",
    "/api/v1/customers/{id}"
  ],
  "expected_scopes": ["read:customers"],
  "sensitive_markers": ["email", "phone", "tax_id"],
  "description": "Production CRM integration assessment"
}
```

Register it:

```bash
ait target-add target.json
```
