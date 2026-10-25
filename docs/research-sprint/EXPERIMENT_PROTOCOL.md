# Experiment Protocol

Status: **frozen for the development-corpus comparison** (written and committed before the baseline existed or was run).
The held-out section is a procedure that stays **pending** until Member B delivers frozen cases.
Any change after the first run is recorded in §12.

## 1. Research questions

- **RQ1:** On the same traces and declared policy, does AIT detect endpoint-policy violations and sensitive-data exposure differently from a simple two-part baseline (endpoint allowlist + exact canary search)?
- **RQ2:** Does AIT's baseline-vs-mutated comparison (DM3) identify cases the simple baseline cannot?
- **RQ3:** How do both methods perform on a small, independently authored held-out set? (pending)
- **RQ4:** What does an independently developed integration actually do under a defined workflow, relative to a declared policy? (pending; see `REAL_INTEGRATION_STUDY.md`)

## 2. Hypotheses (prespecified; first recorded in `FINDINGS.md`, commit `3475baf`)

- **H-B1:** Hidden-endpoint category: the baseline ties AIT on the development corpus, except where the baseline's explicit `ambiguous` rule (§5) withholds a flag.
- **H-B2:** Sensitive-data category: the methods disagree only where a declared canary appears outside a marker-named field, or a marker-named field carries a non-canary value.
- **H-B3:** Any AIT advantage at the scenario level comes from DM3 (behavioural divergence), which the baseline does not model.
- **H-HO (held-out):** No directional hypothesis. Results are reported as observed.

## 3. Integration identity

No independently developed integration had been observed when this protocol was frozen. Status: `not run`, owned by humans (see `REAL_INTEGRATION_STUDY.md`). Fallback rule: if no valid observation exists by end of Day 3, the paper claims only a prototype with controlled evaluation.

## 4. Datasets

| Set | Source | Authors | Role |
|---|---|---|---|
| Development corpus | `configs/scenarios/{crm,platform,robustness,evasion}/*.yaml` at commit `fe1a2bb`: 33 cases (6 CRM + 10 platform + 13 robustness + 4 evasion). Excludes `schema.example.yaml` and `evasion/invalid/` | Same team that wrote the detector | **Development data**: seen, author-scripted; not a test set |
| Held-out set | `configs/heldout/<tag>/*.yaml` (pending) | Member B only | Test set, frozen and tagged before first evaluation |
| Live capability probes | `results/raw/live/**` | AIT issuing planned requests | **Not used** in RQ1–RQ3 (not integration behaviour) |

Scenario generation: hand-written YAML. Exchanges are replayed through `httpx.MockTransport` (`ait/experiments/mock_executor.py`); no integration executes.

## 5. Methods under comparison

Both methods consume the same `CapturedExchange` list produced by `execute_scenario`, and the same `target.expected_endpoints`.

**AIT** (`ait/analysis.py::analyze_run`, default weights 25/20/15): predicts categories `hidden_endpoint`, `sensitive_field_access`, `behavioral_divergence` from its findings.

**Baseline** (`ait/baseline.py`). It shares only `normalize_path` (query-parameter sorting) with AIT and does not import AIT's finding logic.

- *A, endpoint allowlist.* Policy semantics are exact normalized-path equality. Each observed request path is classified as:
  - `allowed`: exact match with a declared entry.
  - `unparseable`: does not start with `/`.
  - `ambiguous`: its path without the query string equals the path without the query string of some declared entry, but the full normalized path matches no entry.
  - `unexpected`: none of the above.
  Only `unexpected` predicts `hidden_endpoint`. `ambiguous` and `unparseable` are reported separately and count as not flagged.
- *B, exact canary search.* Each canary string is searched for (substring match) in every string key and value of the request path, request body, and response body of every exchange. Any hit predicts `sensitive_field_access`. Hit records store the canary index, endpoint, phase and location, never the canary value.
- The baseline has no counterpart to DM3. For `behavioral_divergence` it is reported as `n/a` and excluded from the baseline's category metrics. At the scenario level it simply never predicts divergence.

## 6. Canary definition

- If a scenario declares `canaries:` (optional list of strings, each at least 8 characters), those are used. Held-out authors must declare canaries for every case that seeds synthetic sensitive values.
- Development-corpus rule, used when nothing is declared: canaries are the distinct string values of at least 8 characters found in response bodies at fields whose leaf name is in `target.sensitive_markers`. This mirrors `POST /admin/seed`, which writes run-specific values into exactly those fields. **Known consequence:** on the development corpus, part B overlaps DM2 by construction. This limits what RQ1 can show and is reported as such.
- Canaries are synthetic. No real secrets or personal data are ever used as canaries.

## 7. Ground truth and outcome categories

- Per-category truth comes from `expected_labels` (category presence; endpoint qualification is ignored for this comparison).
- Scenario outcome: `ground_truth_outcome` if declared (one of `confirmed_policy_violation`, `permitted_behavior`, `uncertain_policy`, `incomplete_observation`, `out_of_scope`). Otherwise `confirmed_policy_violation` if `expected_labels` is non-empty, else `permitted_behavior`.
- Only `confirmed_policy_violation` and `permitted_behavior` cases enter the confusion matrices. The other three outcomes are listed separately, with both methods' predictions.
- Development-corpus labels are used **as committed**. Questionable labels (e.g., `rob-crm-c1-compliant-ambiguous-profile`, FINDINGS F9) are flagged in the report, not edited.

## 8. Metrics

- **Unit (category level):** one scenario × one category. Positive means the category is in the expected labels. Counts are TP/FP/FN/TN per category, plus micro-sums over the categories the method models.
- **Unit (scenario level):** one scenario. Positive means `confirmed_policy_violation`; predicted positive means the method flagged any category.
- Precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2PR/(P+R). Each is undefined (`null`) when its denominator is 0.
- Request-level and scenario-level counts are never mixed.
- Intervals: 95% Wilson score intervals on precision and recall (`ait/experiments/statistics.py::wilson_interval`). They assume independent Bernoulli trials, an assumption that hand-written, related scenarios (parents and variants) violate, so treat the intervals as descriptive.
- No significance testing is performed (sample too small; cases not independent).
- Repetitions: none needed; both methods are deterministic, as confirmed by the Phase 0 reproducibility run. Seed 20260727 is recorded in provenance but not consumed.
- Runtime: **not measured** for this comparison.

## 9. Exclusion rules

Files that fail schema validation, `schema.example.yaml`, and anything under an `invalid/` directory are excluded. No other exclusions. Every loaded case appears in the predictions file.

## 10. Held-out freeze procedure (Member B)

1. Write 15–25 cases in `configs/heldout/v1/` using the scenario schema (`configs/scenarios/schema.example.yaml`). Optional fields: `canaries`, `ground_truth_outcome`. Use `suite:` from the allowed values (`crm`/`platform`/`robustness`/`evasion`); the field does not affect evaluation. Do **not** read `ait/analysis.py`, `ait/baseline.py`, or existing scenario labels while authoring.
2. Add `configs/heldout/v1/RATIONALE.md` giving each case's intended outcome and the reasoning.
3. Validate the schema only (this does not run any detector):
   `uv run python -c "from pathlib import Path; from ait.experiments.scenario_loader import load_scenario; [load_scenario(p) for p in sorted(Path('configs/heldout/v1').glob('*.yaml'))]; print('ok')"`
4. Hash: `uv run python -m ait.experiments.compare_baseline hash configs/heldout/v1 > configs/heldout/v1/SHA256SUMS`
5. Commit, then tag without overwriting an existing tag: `git tag blind-eval-v1` (choose `-v2` etc. if it exists), then `git push origin blind-eval-v1`.
6. Record here: freeze commit, tag, the SHA256SUMS digest, timestamp, and who authored the cases.
7. Only then does Member A (detector side) run: `uv run python -m ait.experiments.compare_baseline run --scenario-root configs/heldout/v1 --corpus heldout-v1`.
8. If any held-out case is later used for debugging or tuning, it becomes development data. A fresh set is then required for a held-out claim.

Freeze record (fill in): commit `____`, tag `____`, SHA256SUMS sha256 `____`, timestamp `____`, author `____`, first-evaluation commit `____`.

## 11. Reproduction commands

```bash
uv sync --dev
uv run python -m ait.experiments.run_offline --output-root results        # includes the dev-corpus comparison
uv run python -m ait.experiments.compare_baseline run --scenario-root configs/scenarios --corpus dev
```

Outputs: `results/raw/baseline-comparison/<corpus>/predictions.json` (per-case predictions and ground truth) and `results/derived/baseline_comparison_<corpus>.json` (metrics recomputable from the predictions file).

## 12. Post-freeze change log

| Date | Change | Affects results? |
|---|---|---|
| 2026-10-25 | Risk score: `ait/analysis.py` now adds `w_D` per endpoint in `M \ B` instead of per divergence summary line (which also counted baseline-only endpoints with no finding). Unit test expectation 95 → 80. | No. All 33 dev-corpus scores and all derived payloads are identical before and after (re-run verified). Only archived early live runs (risk 15 without a finding) reflect the old behaviour. |
| 2026-10-25 | `run_offline` gained step 7/7: the dev-corpus baseline comparison. | No. Predictions identical to the first frozen run (`08c9c3d`). |
| 2026-10-25 | Live table relabelled as credential capability probes ("Paths outside declared policy", "Reachable", "Within policy"). | No. Presentation only. |
| 2026-10-25 | Added `ait/integration_trace.py` (Experiment A tooling; see `REAL_INTEGRATION_STUDY.md`). | No. Not run on any integration yet. |
| 2026-10-25 | `configs/paper_artifacts.yaml` pins regenerated by `update_artifact_hashes` after a fresh `run_offline`. Original pins are in history at `fe1a2bb`. The derived JSON set is now force-added so `check_stale` passes on a fresh clone (fixes F1). | No. Payloads identical to Phase 0 run; byte hashes differ only through provenance timestamps. |
