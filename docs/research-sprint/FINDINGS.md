# Research Sprint — Phase 0 Findings

Audited commit: `fe1a2bb` (clean worktree). Commands and exit codes: see `STATUS.md`.
Severity: **Critical** = paper states something the evidence contradicts; **High** = claim not supported by implementation/evidence; **Medium** = reproducibility/validity gap; **Low** = hygiene.

## Reproduced vs. not reproduced

| Result | Reproduced? | Notes |
|---|---|---|
| Unit/integration tests | Yes | 225/225 committed; 249/249 working tree |
| Offline scenario metrics (16 scenarios, micro TP=16 FP=0 FN=0 TN=48, F1=1.0) | Yes, payload-identical across 2 runs | Byte hashes differ from pins (F2) |
| Per-category metrics (hidden_endpoint TP=7/TN=9; sensitive TP=3/TN=13; divergence TP=6/TN=10; policy_violation TP=0/TN=16) | Yes | `policy_violation` has no positives, so P/R are undefined (`null`) |
| Incident replay 3/3 exact match | Yes (payload); 3 files differ only by `\` vs `/` in `source_path` | Researcher-constructed traces (F12) |
| Robustness 13/13 in-scope, evasion 4/4 missed as designed | Yes, deterministic | Label concern on one case (F9) |
| Reproducibility 5/5 identical category sets and risk scores | Yes | Re-running a deterministic function; shows determinism, not robustness |
| Risk sensitivity (144 rows) | Yes, payload-identical | Heuristic weights (F10) |
| Benchmark timings | Pipeline runs; numbers are machine-dependent | Not comparable to paper's Linux numbers |
| Pinned SHA-256 of offline artifacts | **No** — 8/8 differ | By design (F1, F2); not a data change |
| Live artifact pins | Yes — 5/5 match committed files | These are capability probes (F4) |
| `audit_claims` | Passes | Does not detect F3 |
| Tool comparison (RESTler/EvoMaster) | Not run | `status=NOT_RUN reason=image_digest_unpinned` |
| PDFs | Not built | `latexmk` needs Perl; build skipped by team decision |

## Findings

**F1 (Medium) — Pinned derived artifacts are not in the repository.**
`.gitignore` lines 24–25 ignore `results/derived/*.json` and `results/generated/*.tex`, but `configs/paper_artifacts.yaml` pins SHA-256 values for 7 derived files. On a fresh clone `check_stale` fails with `missing artifact file: results/derived/offline_manifest.json`. The pinned values can never be verified from the repo.

**F2 (Medium) — Byte-level hash reproduction is impossible by design.**
Every artifact embeds `provenance.generated_at_utc`, `git_commit`, `platform`, `python_version`. Re-running changes every hash even when the payload is identical. The documented process (`update_artifact_hashes`) simply re-pins whatever was produced, so "hashes match" only shows that the manifest was refreshed, not that the results reproduced. Payload-level comparison (provenance stripped) is the meaningful check: 34/38 tracked raw artifacts identical, 3 replay artifacts differ only by OS path separator, benchmark differs by timing.

**F3 (Critical) — Live results: prose says NOT RUN, generated table shows results.**
`main.tex` (abstract, §Live SaaS Evaluation, contributions) and `report.tex` state that live GitHub/Notion runs are "BLOCKED / NOT RUN" and "no live risk scores … are claimed". But `configs/paper_artifacts.yaml` selects 5 live artifacts, and `render_tables` produces `live_results.tex` with 5 rows, including "Hidden endpoint: /user/orgs, /user/repos — risk 50 — Detected: Yes" and Google "/v1/projects — risk 25". A compiled paper would contradict itself. `audit_claims` passes because it only checks that a fragment name appears and that the evidence pointer resolves; it never compares prose against data.

**F4 (Critical) — Live artifacts are credential-capability probes, not integration behaviour.**
`ait/live_runner.py` executes YAML request plans (`configs/live/*.yaml`) with the team's own token. In the `*-smoke` plans, AIT itself deliberately requests undeclared paths (e.g., `/user/repos`, `/user/orgs`, `/v1/projects`, `/v1/users`, `/v1/file_uploads`) and then reports them as "hidden endpoints". These rows measure what the token can reach, plus a self-inserted positive control. No third-party integration was observed. They must be labelled `capability probe` and never reported as detection of integration misbehaviour.

**F5 (High) — Offline evaluation is circular: the same YAML defines both traffic and labels.**
`ait/experiments/mock_executor.py` replays each scenario's `exchanges` through `httpx.MockTransport`; there is no integration under test in the offline corpus. The scenario author wrote both the trace and the expected labels with full knowledge of DM1–DM3, so F1 = 1.0 is achieved by construction. The paper partly acknowledges this ("exact by construction", "validates implementation"), but it still presents P/R/F1 tables as "detection performance" and lists a "multi-ecosystem evaluation". No independently authored or held-out cases exist.

**F6 (High) — "Taint-seeded data tracking" is field-name matching.**
`ait/analysis.py` (`field_matches_sensitive_marker`, L70–74) flags an exchange when a response **field name** (or its leaf) equals a configured marker. No value is searched. In the live runner, `response_body` is discarded and only field names are kept (`live_runner.py` ~L623). In `mock_saas.py`, `contains_sensitive_marker` is hard-coded to `"billing_email" in body or "tax_id" in body` (L43). Run-specific canary values are seeded (`runner.py` `POST /admin/seed`) but never matched. This is neither dynamic taint analysis nor canary-value detection. Accurate term: "sensitive-field-name policy check", with canary seeding used for run attribution in the mock path only.

**F7 (Medium) — Risk score counts baseline-only endpoints as divergence without emitting a finding.**
In `analyze_run`, `divergence_summary` includes both baseline-only and mutated-only endpoints (L118–132), and `risk_score` adds `w_D × len(divergence_summary)` (L195). However, a `BEHAVIORAL_DIVERGENCE` finding is emitted only for mutated-only endpoints (L149). A run can therefore get +15 risk with zero findings. Committed live runs `github-readonly-…072629…` and `notion-readonly-…073014…` show risk 15 with no hidden endpoints, while later reruns, the ones the manifest selected, show 0. This is consistent with the mechanism or with a code change between runs, but **unconfirmed**. Also, `len(divergence_summary)` is at most 2 while `|D|` in Eq. (risk) is a set size, so the paper's formula and the code disagree.

**F8 (High) — No fuzzing.**
There is no input generation or mutation. The "mutated" phase is a fixed `phase="mutated"` flag passed to the integration (`runner.py` L65; `demo_integration.py` L31 adds one billing call when mutated). `TestRunConfig.mutation_budget`, `taint_fields`, `crawl_depth`, `replay_count` (`ait/models.py` L52–57) are defined but unused by any research code path. Accurate term: differential (baseline vs. state-varied) policy-conformance testing.

**F9 (Medium) — Label semantics for one "compliant" robustness variant.**
`rob-crm-c1-compliant-ambiguous-profile` is derived from a compliant scenario but expects `hidden_endpoint` + `behavioral_divergence` for an "ambiguous undeclared /api/v1/profile path". Under the sprint's outcome categories this is plausibly `uncertain_policy`, not a confirmed violation. Do not edit the label. Record it and treat it under the new protocol.

**F10 (Medium) — Risk weights and CVSS language.**
Weights (25, 20, 15) are correctly called "heuristic design constants", but the paper attaches specific CVSS v3.1 base-score ranges (7.5–9.0, 6.5–7.5, 4.0–6.0) without a derivation. Keep "heuristic", drop or justify the CVSS ranges. The sensitivity analysis perturbs heuristic weights; it does not calibrate them.

**F11 (Low) — Tool comparison not run.** The paper reports this correctly as NOT RUN.

**F12 (Medium) — Incident replay is plausibility only.** The three traces are researcher-constructed from public post-mortems by the same team, with labels chosen to match AIT categories, so 3/3 exact match is expected. The paper's framing ("plausibility evidence") is appropriate. It must not be counted as detection evaluation.

**F13 (Low) — Stale implementation references in the paper.** `main.tex` §Implementation references `generate_paper_results.py` and `generate_live_saas_results.py`, which do not exist in the repo. It says "Python 3.11+" while the env uses 3.12.

**F14 (Low) — Multiple unreconciled paper sources.** Committed `main.tex` and `report.tex`; untracked `ieee.tex` (2026-09-24), `ait_report.tex` (2026-10-25), and `main111.tex.txt`. All use the fuzzing/taint title. The canonical source must be chosen by the humans.

**F15 (Low) — Working-tree README and product claims are not research evidence.** The uncommitted README says AIT "continuously verifies" integrations and describes a production platform (Postgres, JWT, workers). Those features are backed by tests in the working tree but have no bearing on the paper's detection claims. Keep that restructure separate from the research PR.

**F16 (Medium) — Canary values are not part of the scenario schema.**
The required baseline component B (exact canary-value search) needs a per-scenario list of canary values. Existing scenarios embed marker-like values (`run-marker@example.test`, `TAX-RUN-MARKER`, `alias@x.test`) but never declare them as canaries. Adding canaries must be a separate, documented protocol file, not an edit of existing scenarios or labels.

## Prespecified expectations for the baseline comparison (recorded before any baseline exists)

These are hypotheses written now, before implementation, so they cannot be fitted to results:

- **H-B1:** Endpoint detection: AIT's DM1 is itself an allowlist (`H = R \ E` after `normalize_path`). The allowlist baseline is expected to **tie** AIT on the hidden-endpoint category for the existing corpus.
- **H-B2:** Sensitive-data detection: AIT matches field names; the baseline matches canary values. They are expected to **disagree** on (a) alias cases like FN4 (the baseline can catch them if the value is a declared canary) and (b) cases where a sensitive field name appears with a non-canary value (AIT flags it, the baseline does not).
- **H-B3:** AIT's only logic with no baseline counterpart is the baseline/mutated divergence (DM3). Any AIT advantage on the held-out set should come from DM3 cases. If it doesn't, the comparison is a tie or a loss.

## Smallest changes required (proposed — Gate 0, not started)

1. **Evidence chain (F1, F2):** Force-add one frozen derived set from a recorded run, and record its hashes next to the original pins (do not overwrite history). Add a payload-level comparison command (strip `provenance`) to the reproduction docs.
2. **Live relabel (F3, F4):** Rename the live table and prose to "Credential capability probes (AIT-issued requests)". Remove the "Detected: Yes" framing. Fix the NOT RUN contradiction.
3. **Baseline (F16, §3.1):** One module, about 80 lines: an endpoint allowlist using the same `normalize_path`, plus exact canary search over the response body, request body, and query values. Add a separate `canaries` protocol file and run it on the same scenarios as AIT. Save the raw predictions.
4. **Risk-score bug (F7):** Decide with the team whether to fix it. If fixed, re-run, report both versions, and document it as a post-audit code change.
5. **Terminology (F6, F8, F10):** Make text-only changes in the paper and README.
6. **Held-out set:** Member B authors, freezes, and tags it. No code is needed beyond running the existing scenario loader on a new directory.

Explicitly **not** proposed: fuzzing engine, taint engine, new providers, dashboard work, RESTler/EvoMaster integration.

## Candidate independently developed integrations (Phase 2)

Repository details below are from memory and are **not verified in this session**. Member A must confirm the URL, licence, last commit, and that the team did not write it.

| Candidate | Why plausible | Observation method (least intrusive) | Main risks |
|---|---|---|---|
| **Probot "Settings" GitHub App** (`repository-settings/app`, formerly `probot/settings`) | Open source, runs locally via Probot + smee.io against a sandbox repo/org; the team did not write it | Probot/Octokit debug logging (`LOG_LEVEL=trace`) logs outbound method + URL. GitHub App installation tokens are scoped and inspectable | Needs `administration` write on the sandbox repo, so it writes to the sandbox (acceptable only on a throwaway repo). Workflow is push-to-config driven. Log coverage of every request must be confirmed |
| **Slack Bolt sample app** (e.g., `slackapi/bolt-js-getting-started-app`) | Written by Slack, not the team; Socket Mode means no public URL | `@slack/web-api` `logLevel: DEBUG` logs API method names | Very small behaviour surface (one or two API calls), so a weak study. Requires a free Slack workspace and an app install |
| **Notion SDK example** (`makenotion/notion-sdk-js` `examples/`, e.g. database-update notifier) | Written by Notion; uses an internal-integration token | SDK `logLevel: LogLevel.DEBUG` logs request method + path | Examples are small. Some need a second service (email/GitHub). Page/database sharing must be configured manually |

Recommendation: **Probot Settings** gives the richest behaviour and an existing request log. Choose it only if Member A can give it a throwaway org/repo by Day 2. If not, use the Notion example with SDK debug logging. If neither works by end of Day 3, trigger the mandatory fallback (prototype + controlled evaluation; real-integration validation becomes a limitation).
