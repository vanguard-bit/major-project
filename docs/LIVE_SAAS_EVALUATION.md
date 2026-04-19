# Live SaaS Evaluation Guide

This guide covers the real-platform evaluation path added on top of the existing mock pipeline.

## What It Does

The live pipeline:

- loads one or more scenario YAML files from `live_test_cases/`
- reads bearer tokens from environment variables
- executes the defined baseline and mutated requests directly against the provider API
- converts each HTTP exchange into `CapturedExchange` records
- reuses the existing analysis engine to compute findings and a risk score
- adds explicit `policy_violation` findings when a request expected to be denied succeeds, or a request expected to succeed fails

The entry point is:

```bash
python3 generate_live_saas_results.py
```

## Scenario File Structure

Each live scenario YAML contains:

- `target`: normal AIT metadata such as `base_url`, `expected_endpoints`, `expected_scopes`, and `sensitive_markers`
- `auth_env_var`: the environment variable used to look up the token
- `auth_scheme`: usually `Bearer`
- `requests`: the exact API requests to issue

Each request supports:

- `phase`: `baseline` or `mutated`
- `method`
- `path`
- `params`
- `headers`
- `json_body`
- `expected_behavior`: `allowed` or `denied`
- `expected_http`: acceptable HTTP status codes for that request

## Running Against Real Platforms

1. Add credentials to your shell or local `.env`.

```bash
export GITHUB_TOKEN='...'
export NOTION_TOKEN='...'
```

2. Add or edit scenario files in `live_test_cases/`.

Available examples:

- `live_test_cases/github_live.yaml`
- `live_test_cases/notion_live.yaml`
- `live_test_cases/github_live_example.yaml.example`

3. Run the evaluator:

```bash
python3 generate_live_saas_results.py
```

4. Review the generated outputs in `results/live_saas/`.

## Generated Artifacts

- `results_table.csv`: scenario-level summary suitable for paper tables
- `summary.json`: execution counts and skipped-scenario metadata
- `skipped.json`: reasons for any scenario that did not run
- `raw_run_artifacts.json`: full raw live captures for local analysis

`raw_run_artifacts.json` may contain real account metadata returned by the provider APIs. Treat it as sensitive and avoid committing it unless you have explicitly reviewed and sanitized it.

## Current Supported Auth Shape

The live runner currently supports bearer-style tokens. That covers:

- GitHub PATs and bearer-compatible OAuth tokens
- Notion integration tokens
- Slack bot tokens
- Google access tokens

Platforms with non-bearer auth conventions, such as query-param tokens, need a small adapter before they can be evaluated cleanly.

## Operational Guidance

- Use only accounts or tenants you control.
- Stay within platform documentation and rate limits.
- Keep scenarios explicit and low impact.
- Treat a positive result carefully: a successful request often means the supplied token was broader than the declared policy, not necessarily that the platform is broken.
