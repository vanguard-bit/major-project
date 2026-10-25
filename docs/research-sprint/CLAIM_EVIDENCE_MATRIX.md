# Claim–Evidence Matrix

Audited commit `fe1a2bb`; sources `main.tex` (M) and `report.tex` (R) unless noted. Finding IDs refer to `FINDINGS.md`.
Statuses: `verified` · `partially verified` · `unverified` · `failed` · `not run`.
Reproduction commands assume the repo root and `uv sync --dev`.

| # | Paper/README claim | Code location | Supporting artifact | Reproduction command | Current status | Required action |
|---|---|---|---|---|---|---|
| 1 | Title/contribution: "Differential **Fuzzing**" (M L31–32, L176–178; R L168, L179, L323) | `ait/runner.py` L65, `ait/demo_integration.py` L31 (fixed phase flag) | none | — | **failed** (no input generation/mutation; F8) | Replace with "differential (baseline vs. state-varied) policy-conformance testing"; title change needs guide approval |
| 2 | "**Taint-seeded** data tracking", "instrumentation-free taint-injection mechanism" (M L186–188, L498–509) | `ait/analysis.py` L70–74, L104–111; `ait/mock_saas.py` L43; `ait/runner.py` L30–34 | none | — | **failed** (field-name match; seeded values never matched; F6) | Describe as sensitive-field-name policy check plus run-attribution markers; do not use "taint" |
| 3 | Detect C1 hidden endpoints, DM1 `H = R \ E` (M L513–519) | `ait/analysis.py` L96–103, L134–147 | `results/derived/scenario_metrics.json` (hidden_endpoint TP=7 FP=0 FN=0 TN=9) | `uv run python -m ait.experiments.run_offline --output-root results` | **partially verified**: logic matches equation; evaluation is author-scripted (F5) | Keep; reframe metrics as implementation validation; add baseline + held-out set |
| 4 | Detect C2 sensitive field access, DM2 (M L521–524) | `ait/analysis.py` L104–111, L165–190 | scenario_metrics (sensitive TP=3 TN=13) | same | **partially verified** (field names only; F6) | State the field-name semantics; compare with canary baseline |
| 5 | Detect C3 state-dependent evasion, DM3 `D = M \ B` (M L526–533) | `ait/analysis.py` L112–132, L149–163 | scenario_metrics (divergence TP=6 TN=10) | same | **partially verified**: works for author-scripted phase flags; no real state-dependent integration observed | Keep as "baseline vs. mutated-phase comparison"; scope C3 claim to controlled cases |
| 6 | Risk score `S = min(100, wH|H| + wF|Fs| + wD|D|)` (M L555–560) | `ait/analysis.py` L40–54, L192–200 | sensitivity_rows.json | same | **partially verified**: code uses `len(divergence_summary)` (≤2, includes baseline-only), not `|D|` (F7) | Fix code or equation; disclose |
| 7 | Weights "inspired by CVSS v3.1" with base-score ranges (M L562–569) | `ait/analysis.py` L19–27 | none | — | **unverified** (ranges asserted, not derived; F10) | Keep "heuristic"; drop or justify the CVSS ranges |
| 8 | Mock detection P/R/F1 table, micro F1 (M L713–734) | `ait/experiments/metrics.py`, `run_offline.py` | scenario_metrics.json (micro TP=16 FP=0 FN=0 TN=48) | same | **verified** as reproduction (payload-identical over 2 runs); **pinned hash failed** (F1, F2) | Report raw counts and the unit (scenario × category); label as author-constructed |
| 9 | Platform-inspired mock suite across Slack/GitHub/Gmail/Notion/Trello idioms (M L742–786) | `configs/scenarios/platform/*.yaml` | `results/raw/scenarios/platform-*.json` | same | **verified** as synthetic replay; no vendor API involved (paper says so) | Keep framing; avoid "multi-ecosystem evaluation" wording that implies breadth |
| 10 | Live SaaS sandbox results "BLOCKED / NOT RUN" (M L60–65, L794–828; R L211–212, L1187) | `ait/live_runner.py` | `results/raw/live/**` (5 pinned, all match) rendered into `live_results.tex` with 5 rows | `uv run python -m ait.paper.render_tables --manifest configs/paper_artifacts.yaml --output results/generated` | **failed**: prose contradicts generated table (F3) | Choose one truth; relabel the rows as capability probes |
| 11 | Live smoke rows show "Hidden endpoint … Detected: Yes" (generated `live_results.tex`) | `configs/live/*_smoke*.yaml` | `results/raw/live/github-smoke/…911e040c.json`, `google-smoke/…4d0a5a31.json` | same | **failed** as integration evidence: AIT itself sent the undeclared requests (F4) | Report as `capability probe` + self-inserted positive control only |
| 12 | Log-based replay of CircleCI/Okta/GitHub incidents, 3/3 exact match (M L915–941) | `ait/experiments/replay_incidents.py`, `configs/incidents/*.yaml` | `results/derived/replay_match_table.json` | same | **verified** as reproduction; plausibility only (F12) | Keep "plausibility", not detection evidence |
| 13 | False-negative analysis FN1–FN4 (M L539–551, §fn) | `configs/scenarios/evasion/*.yaml` | `results/raw/robustness/eva-*.json` (4/4 missed as designed) | same | **verified** | Keep; FN4 is a natural baseline comparison case |
| 14 | Robustness suite 13/13 in-scope (M L843–862) | `ait/experiments/robustness.py` | `results/derived/robustness_metrics.json` | same | **verified** (deterministic); one label questionable (F9) | Revisit the label under new outcome categories without editing it |
| 15 | Deterministic reproducibility 5/5 (M L853–854) | `ait/experiments/reproducibility.py` | `results/derived/reproducibility.json` | same | **verified**; shows determinism only | Don't present as robustness or independence |
| 16 | Risk sensitivity ±30% (M L943+) | `ait/experiments/risk_sensitivity.py` | `results/derived/sensitivity_summary.json` | same | **verified** (payload-identical) | Keep as heuristic-weight sensitivity |
| 17 | Analysis Engine micro-benchmark / "scalability" (M L865–890) | `ait/experiments/benchmark_analysis.py` | `results/derived/benchmark_summary.json` | same | **partially verified**: runs; timings machine-dependent; synthetic widths only | Report machine; avoid "scalability" beyond the synthetic analysis step |
| 18 | Tool comparison vs RESTler/EvoMaster (M L892–912) | `comparison/` | `results/raw/tool-comparison/*/status.txt` (`NOT_RUN`) | `bash comparison/run_restler.sh` (Docker) | **not run** (correctly reported) | Leave NOT RUN or drop the section |
| 19 | "Results within the mock environment are exact by construction" (M L131) | — | — | — | **verified** (and explains F5) | Keep; extend the honesty to the tables |
| 20 | Offline pipeline reproducible with pinned SHA-256 (docs/REPRODUCIBILITY.md §3, §9) | `ait/paper/check_stale.py`, `update_artifact_hashes.py` | `configs/paper_artifacts.yaml` | `uv run python -m ait.paper.check_stale` | **failed** on a fresh clone (F1); pins non-reproducible by design (F2) | Commit the frozen derived set; add payload comparison |
| 21 | `make research-artifact` one-command reproduction incl. PDFs | `Makefile` | — | `make research-artifact` | **not run** (no `make` on Windows; PDF build skipped by team decision) | Document a Windows/WSL path; `.tex` generation verified (row 10 command) |
| 22 | Claim audit protects paper claims | `ait/paper/audit_claims.py` | `configs/claims.yaml` | `uv run python -m ait.paper.audit_claims` | **partially verified**: passes, but it misses F3 | Don't cite as evidence of claim correctness |
| 23 | Implementation uses `generate_paper_results.py`, `generate_live_saas_results.py`; Python 3.11+ (M §Implementation) | — | — | — | **failed** (files absent; F13) | Fix text |
| 24 | README (working tree): "continuously verifies whether third-party SaaS integrations … stay within approved scopes" | uncommitted `ait/services/`, `ait/workers/` | tests only | `uv run pytest -q` | **unverified** as a research claim; no integration was observed | Keep it out of the paper; soften README |
| 25 | Generalization to arbitrary production SaaS: explicitly **not** claimed (M L133–138) | — | — | — | **verified** (claim correctly withheld) | Keep |
| 26 | Actual third-party integration behaviour | none | none | — | **not run** | Phase 2 study or fallback |
| 27 | Independent / held-out evaluation | none | none | — | **not run** | Phase 3 (Member B) |
| 28 | Simple baseline comparison | none | none | — | **not run** | Phase 3 baseline |
| 29 | Citations (35 `\bibitem` in M) support attributed claims | `main.tex` bibliography | — | — | **unverified** (no human verification yet) | Member B verifies the 8–10 core citations against originals |

## Status after revision (2026-10-25, branch `research-sprint/sprint-work`)

The rows above are the Phase 0 audit of `fe1a2bb` and are kept as audited. This table records what changed.

| # | New status | What was done |
|---|---|---|
| 1 | resolved in body; **title pending guide** | Body uses "differential (baseline vs. state-varied) policy-conformance testing"; Terminology section added; registered title kept with a `TITLE PENDING GUIDE APPROVAL` comment |
| 2 | resolved | "taint" removed as a description of AIT; DM2 described as field-name check; seeded values described as run attribution only |
| 3–5 | partially verified (unchanged evidence) | Metrics framed as implementation validation on author-written traces |
| 6 | **fixed** | Code now uses `|M \ B|`; no corpus result changed; disclosed as "post-audit correction" in both papers |
| 7 | resolved | CVSS base-score ranges removed; weights stated as heuristic, uncalibrated |
| 8, 20 | **verified** | Derived set committed; pins regenerated; `check_stale` passes on the committed tree; payload reproduction documented |
| 10, 11 | resolved | Live rows relabelled as credential capability probes in template, prose and captions; NOT RUN/BLOCKED contradiction removed |
| 17 | partially verified | "scalability" claims avoided; synthetic widths only |
| 21 | not run | unchanged (no `make`/PDF) |
| 22 | partially verified | New `baseline-comparison` claim added; audit still does not check prose semantics |
| 23 | resolved | Stale script names and Python version fixed in both papers |
| 26 | **not run** | Tooling ready: `ait/integration_trace.py`, `REAL_INTEGRATION_STUDY.md` |
| 27 | **not run** | Freeze procedure ready (`EXPERIMENT_PROTOCOL.md` §10); needs Member B |
| 28 | **verified (dev corpus)** | Tie: scenario-level TP 15 / FP 0 / FN 4 / TN 14 for both. `results/raw/baseline-comparison/dev/predictions.json`, `results/derived/baseline_comparison_dev.json`, `uv run python -m ait.experiments.compare_baseline run --scenario-root configs/scenarios --corpus dev` |
| 29 | **unverified; 3 removed** | `petsios2017` (SlowFuzz cited as differential testing), `bulekov2023` (author/title mismatch), `wermke2022` (title unrelated to claim) removed from both papers. Remaining list for human verification in `FINAL_REVIEW.md` |
| 30 (new) | partially verified | "Integration Trace Tool" (paper §Architecture): unit-tested on a synthetic HAR only (`tests/test_integration_trace.py`) |
