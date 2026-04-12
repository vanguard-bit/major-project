# Evaluation Methodology & Parameters

This document details the parameters, metrics, and methodology used to generate the evaluation results for the AIT (Adversarial Integration Tester) research paper. The data in `results_table.csv` is derived from a controlled environment using high-fidelity mock implementations of major SaaS platforms.

## 1. Evaluation Environment
- **Prototype Version:** AIT v0.1.0
- **Mock SaaS Engine:** FastAPI-based service simulating Slack, GitHub, Google (Gmail), Notion, and Trello REST APIs.
- **Integration Layer:** A dedicated integration service that executes baseline and mutated API transaction sequences.
- **Network Latency:** Local loopback (approx. <2ms per request).

## 2. Assessment Parameters
For each integration scenario, the following standard configuration was applied:

| Parameter | Value | Description |
|-----------|-------|-------------|
| **Crawl Depth** | 2 | Depth of API discovery and traversal. |
| **Mutation Budget** | 10 | Number of adversarial state-mutation attempts per endpoint. |
| **Timeout** | 15s | Maximum wait time for API responses. |
| **Auth Type** | Bearer Token | Static OAuth2 access tokens were used to simplify mock authentication. |
| **Phases** | Baseline, Mutated | Each assessment consists of a "Baseline" run (normal operation) and a "Mutated" run (adversarial state changes). |

## 3. Risk Scoring Formula
The **Risk Score** (0–100) is a weighted metric designed to quantify the severity of a scope violation. It is calculated as:

$$RiskScore = \min(100, (N_{hidden} \times 25) + (N_{sensitive} \times 20) + (N_{divergence} \times 15))$$

Where:
- **$N_{hidden}$ (Hidden Endpoint Access):** Number of endpoints reached that were not in the declared `expected_endpoints` list.
- **$N_{sensitive}$ (Sensitive Field Access):** Number of unique sensitive fields (e.g., `repo_secret`, `auth_token`) detected in API responses.
- **$N_{divergence}$ (Behavioral Divergence):** Count of phase-specific divergence patterns (e.g., an endpoint accessible in "Mutated" phase but blocked in "Baseline").

## 4. Scenario Definitions

| Scenario | Declared Scope | Targeted Violation | Logic Induced |
|----------|----------------|-------------------|---------------|
| **Slack Bot** | `channels:read` | Hidden Access | Calls `/conversations.history` (undeclared). |
| **GitHub PAT** | `public_repo` | Sensitive Exposure | Returns `repo_secret` from a private repository mock. |
| **Google Gmail**| `gmail.readonly`| Unauthorized Write | Successfully executes a POST to `/gmail/send`. |
| **Notion** | `Read Content` | Behavioral Divergence| Update endpoint becomes accessible only after a read operation. |
| **Trello** | `read` | Scope Divergence | Mutation enables card creation on a read-only token. |

## 5. Metric Definitions
- **True Positive (TP):** A finding where a known vulnerability/over-permissioning pattern was correctly identified and scored > 0.
- **False Positive (FP):** A finding where a compliant, baseline-only integration was incorrectly flagged with a score > 0.
- **Precision:** $TP / (TP + FP)$. The current evaluation achieves 100% precision.

---
*Date of Generation: April 12, 2026*
*Platform: Linux x86_64*
