# AIT Architecture

## Overview

Adversarial Integration Tester (AIT) is a CLI-first security testing framework that detects hidden data access in SaaS integrations by comparing API call behaviour across baseline and mutated execution phases.

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AIT System Architecture                             │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────────┤
│   CLI        │  Coordinator │  Analysis    │  Compliance  │  Reporting     │
│  (cli.py)    │  API (api.py)│  Engine      │  Framework   │  Engine        │
│              │              │ (analysis/)  │ (compliance/)│ (reporting/)   │
└──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────┘
       │              │              │              │                │
       ▼              ▼              ▼              ▼                ▼
   Typer CLI    FastAPI app    Detectors:       Checkers:       Renderers:
   Commands     REST API       - Core           - SOC 2         - HTML
                               - Scope          - GDPR          - Dashboard
                               - Anomaly        - HIPAA         - PDF
                               - Rate Limit     - PCI DSS       - CSV
                │
                ▼
         Storage Layer
          (storage/)
         SQLAlchemy ORM
         SQLite / PostgreSQL
                │
                ▼
         Plugin System
          (plugins/)
         Custom Detectors
```

---

## Packages

### `ait/analysis/`
The analysis engine compares baseline and mutated API call traces to detect security issues.

| Module | Description |
|--------|-------------|
| `__init__.py` | Core `analyze_run()` orchestrator |
| `scope_validator.py` | Validates OAuth scopes against actual endpoint access |
| `anomaly_detector.py` | ML-based detection using Isolation Forest (scikit-learn) |
| `rate_limit_detector.py` | Detects excessive API call frequencies |

### `ait/storage/`
Persistence layer backed by SQLAlchemy, supporting SQLite (default) and PostgreSQL.

| Module | Description |
|--------|-------------|
| `__init__.py` | `SQLAlchemyStore` – drop-in replacement for `InMemoryStore` |
| `database.py` | Engine creation, session factory |
| `orm.py` | SQLAlchemy ORM table models |
| `repository.py` | Repository pattern: `TargetRepository`, `RunRepository` |

**Configuration:**
```bash
# Use SQLite (default)
export AIT_DATABASE_URL=sqlite:///ait.db

# Use PostgreSQL
export AIT_DATABASE_URL=postgresql://user:pass@localhost:5432/ait

# Force in-memory (tests)
export AIT_USE_MEMORY_STORE=1
```

### `ait/compliance/`
Automated compliance validation against security standards.

| Module | Description |
|--------|-------------|
| `__init__.py` | `run_all_compliance_checks()` entry point |
| `checker.py` | SOC 2, GDPR, HIPAA, PCI DSS checkers |

### `ait/reporting/`
Professional report generation in multiple formats.

| Module | Description |
|--------|-------------|
| `__init__.py` | HTML report + interactive dashboard |
| `pdf_report.py` | PDF generation with executive summary (reportlab) |
| `csv_export.py` | CSV export for findings and compliance data |

### `ait/plugins/`
Extensible framework for custom security detectors.

| Module | Description |
|--------|-------------|
| `__init__.py` | Public API exports |
| `base.py` | `BaseDetectorPlugin` abstract class |
| `registry.py` | `PluginRegistry` with auto-discovery |

---

## Data Flow

```
run_assessment()
     │
     ├─ _resolve_token()    → OAuth token acquisition
     ├─ _post_seed()        → Initialize audit logging on Mock SaaS
     ├─ _invoke_integration("baseline")  → Baseline API calls
     ├─ _invoke_integration("mutated")   → Mutated API calls
     ├─ _fetch_audit_log()  → Collect all captured exchanges
     │
     ├─ analyze_run()
     │    ├─ Core detectors (hidden endpoints, sensitive fields, divergence)
     │    ├─ detect_scope_violations()
     │    ├─ detect_anomalies()          (Isolation Forest)
     │    └─ detect_rate_limit_violations()
     │
     ├─ run_all_compliance_checks()
     │    ├─ check_soc2()
     │    ├─ check_gdpr()
     │    ├─ check_hipaa()
     │    └─ check_pci_dss()
     │
     └─ default_registry.run_all()   → Custom plugin results
```

---

## Risk Scoring

The risk score (0–100) is calculated as:

```
risk_score = min(100,
    len(hidden_endpoints) * 25 +
    len(sensitive_fields) * 20 +
    len(divergence_summary) * 15
)
```

Scores ≥ 50 are flagged as elevated risk in compliance checks.
