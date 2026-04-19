# Paper-Ready Results

## Results Table

| # | Platform | Integration Scenario | Declared Scope | Violation Type | Risk Score | Severity | Detected? |
|---|---|---|---|---|---:|---|---|
| 1 | Slack | Bot token over-access | channels:read | Behavioral divergence; Hidden endpoint access | 80 | High | ✅ Yes |
| 2 | GitHub | PAT broad scope | public_repo | Hidden endpoint access; Sensitive field access | 65 | Critical | ✅ Yes |
| 3 | Google | Readonly token write attempt | gmail.readonly | Hidden endpoint access; Sensitive field access | 45 | Critical | ✅ Yes |
| 4 | Notion | Read-only integration mutation | Read Content | Behavioral divergence; Hidden endpoint access | 55 | High | ✅ Yes |
| 5 | Trello | Read token card creation | read | Behavioral divergence; Hidden endpoint access | 40 | High | ✅ Yes |
| 6 | Slack | Compliant bot | chat:write | None | 0 | — | ✅ (No FP) |
| 7 | GitHub | Compliant app | read:user | None | 0 | — | ✅ (No FP) |

## Detection Metrics

| Category | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Hidden endpoint access | 5 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| Sensitive field access | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| Behavioral divergence | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |

## Abstract Snippet

Evaluation across 7 controlled scenarios on 5 platform-themed mock integrations detected 5 violating scenarios with 100% precision and no false positives.

## Evaluation Snippet

Across 7 controlled scenarios, AIT identified 5 violating scenarios and produced no false positives on 2 compliant scenarios. Risk scores ranged from 0 to 80 (mean: 40.71). Per-category precision, recall, and F1 were computed directly from the measured runs in `results/detection_metrics.csv`.
