# Real Integration Study (Experiment A)

**Status: not run.** Tooling is implemented and unit-tested (`tests/test_integration_trace.py`).
No integration written by others has been observed, so the paper says "not run" (`main.tex` §`sec:realint`, `report.tex` §`sec:realint`).
This file is the procedure. Fill in the record (end of file) only from a real run.

## What is and is not Experiment A

| | Experiment A: integration observation | Experiment B: credential capability probe |
|---|---|---|
| Who sends requests | The integration under test | AIT (`ait/live_runner.py`) |
| What it shows | What the integration actually did in one workflow | What the token *could* reach |
| Tool | `ait/integration_trace.py` | `ait/live_runner.py` |
| Paper section | `sec:realint` | `sec:livesaas` |

Never report B results as A. A self-written integration is a **reference integration**, never "third-party". Set `authored_by_team: true` in the policy and the tool will print a reminder.

## Human-owned prerequisites (the agent cannot do these)

1. **Pick one integration.** Recommended from `FINDINGS.md`: Probot Settings (`repository-settings/app`, GitHub App, open source). Record the exact repository URL, commit or tag, and licence.
2. **Check the provider ToS and the integration's licence** for automated testing in a sandbox. Write the check (date, URL, who checked) in the record below.
3. **Create a sandbox**: a throwaway GitHub org/repo (or Slack/Notion workspace) with **synthetic data only**. No real users, no customer data, no personal data.
4. **Create minimum-scope credentials** and keep them in environment variables or the integration's own `.env`. Never paste them into prompts, docs, the paper, commits, or logs.
5. **Plant canaries (optional):** synthetic strings of at least 8 characters (e.g. `AITCANARY-7f3a91`) placed in sandbox data that the integration should *not* send elsewhere. List them in the policy's `canaries:`.

## Procedure

### 1. Write the policy before capture

```powershell
Copy-Item configs/integration/TEMPLATE.policy.yaml configs/integration/<name>.policy.yaml
# edit: integration identity, allowed_hosts, expected_endpoints, denied_endpoints,
#       sensitive_markers, canaries.  Derive endpoints from the integration's docs and
#       declared permissions/manifest (e.g. app.yml), NOT from the trace.
git add configs/integration/<name>.policy.yaml
git commit -m "Integration policy for <name> (pre-capture)"
```

The commit timestamp proves the policy predates the observation. If the policy must change after capture, record why in the record below. Do not silently edit it.

Template syntax: `"[METHOD ]/path"`, where `{name}` matches one path segment and `{name*}` matches the rest of the path. Hosts in `ignore_hosts` (e.g. a webhook relay such as `smee.io`) are reported as `out_of_scope`.

### 2. Capture traffic using the least intrusive authorized method

Pick the first option that works, and record which one you used as `--source`:

1. **The integration's own request log** (preferred; no interception). Many SDKs log each request (e.g. Octokit / Probot `LOG_LEVEL=trace`). Convert it to JSON lines, one object per request:
   `{"ts": "2026-11-01T10:00:00Z", "method": "GET", "url": "https://api.github.com/repos/o/r", "status": 200, "request_body": null, "response_body": {...}}`
   (`ts`, `request_body` and `response_body` are optional.)
2. **An authorized local proxy** such as mitmproxy, with the integration process configured to trust the proxy CA *on your own machine*. Save a HAR:
   `mitmdump --set hardump=traces/<name>-baseline.har`
   Then run the integration with `HTTPS_PROXY=http://127.0.0.1:8080`, and give the integration's runtime the mitmproxy CA through the integration's standard CA option (e.g. `NODE_EXTRA_CA_CERTS`).

**Never** disable TLS verification (`NODE_TLS_REJECT_UNAUTHORIZED=0`, `verify=False`, …), bypass certificate pinning, or weaken any provider security control. If the integration pins certificates or refuses the proxy, stop and use option 1, or record the integration as infeasible.

`traces/` is gitignored. Raw traces contain tokens and sandbox data and must **never be committed**.

### 3. Run one fixed workflow

Define the workflow before running it, e.g. "install the app on the sandbox repo, push a `.github/settings.yml` change, wait for the sync". Record it as `--workflow-id`. Optionally, run a second, state-varied workflow (e.g. the same push with a config the integration treats differently) as the `--mutated` trace.

### 4. Sanitize and evaluate

```powershell
uv run python -m ait.integration_trace `
  --policy configs/integration/<name>.policy.yaml `
  --baseline traces/<name>-baseline.har `
  --mutated traces/<name>-mutated.har `
  --workflow-id "<workflow description id>" `
  --source "mitmproxy hardump" `
  --output results/raw/integration/<name>/<workflow-id>.json
```

The output keeps only method, host, path rewritten to the matching policy template, query parameter **names**, status, outcome, and canary-hit indices and locations. It never keeps values, headers or bodies. It records the policy's sha256 and the raw trace's sha256, so the raw file can be matched later without being committed. The tool **refuses to write** output containing a secret-like pattern (GitHub/Slack/Notion/Google/AWS tokens, `Bearer`, private keys, JWTs) or any canary value.

### 5. Human redaction review (required before committing)

Open the output JSON and check it by eye for anything identifying: org/repo names in hosts, user names in paths that did not match a template, and email addresses. Unmatched paths keep their literal segments. Replace identifying segments with placeholders and note the edit in the record. Only then run `git add` on the output.

## Outcome categories

| Outcome | Rule in `ait/integration_trace.py` |
|---|---|
| `confirmed_policy_violation` | Endpoint matches `denied_endpoints`, **or** a canary appears in a request path/body sent to a non-allowed endpoint |
| `permitted_behavior` | Endpoint matches `expected_endpoints` on an allowed host |
| `uncertain_policy` | Undeclared endpoint or host. Reported, **not assumed malicious**: the policy may simply be incomplete |
| `incomplete_observation` | Request could not be parsed (no method/URL) |
| `out_of_scope` | Host in `ignore_hosts` |

The same sanitized trace is also scored by AIT (DM1–DM3) and the two-part baseline (`ait/baseline.py`). Both results go in the output under `ait` and `baseline`. Report the per-request outcome counts and both detectors' findings. Do not convert `uncertain_policy` into violations to make the numbers look better.

## Fallback rule (decide by Day 3)

If no integration can be observed within the sprint (no ToS-compatible candidate, pinning, no sandbox, no time), leave this study as **not run**. The paper keeps its current wording: "a prototype with a controlled evaluation", with external validity as limitation L1. Do not substitute capability probes or a reference integration as "real integration" evidence.

## Record (fill in only from a real run)

| Field | Value |
|---|---|
| Integration name / repo / commit / licence | |
| Authored by team? | |
| ToS + licence check (date, URL, checker) | |
| Sandbox description (synthetic data only) | |
| Credential scopes used | |
| Policy commit (pre-capture) | |
| Capture method (`--source`) | |
| Workflow id(s) | |
| Raw trace sha256 (from output) | |
| Output file(s) | |
| Outcome counts | |
| AIT findings / baseline findings | |
| Redaction edits | |
| Deviations from this procedure | |
