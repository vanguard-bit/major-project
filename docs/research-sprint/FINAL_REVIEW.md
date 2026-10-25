# Final Review (Phase 5)

Branch `research-sprint/sprint-work`, based on `fe1a2bb` (`main`). The user's uncommitted production restructure in the main checkout was not touched.
Reviewer: AI coding agent. **Not yet reviewed by a human.** Every item under "Human checks outstanding" must be closed before submission.

## Bottom line

AIT is now presented as **a prototype with a controlled evaluation**. On its own 33 author-written cases, it ties with a simple allowlist plus canary-search baseline. The two studies that could support stronger claims (an independently developed integration and an independently authored held-out set) are **not run**. Tooling and frozen procedures for both are in the repository.

## What was completed and reproduced

| Item | Evidence | Command |
|---|---|---|
| Offline pipeline reproduced at payload level (byte hashes cannot reproduce: provenance timestamps) | `STATUS.md` rows 7–10; derived payloads identical across Phase 0 run, run 2, and the final run | `uv run python -m ait.experiments.run_offline --output-root results` |
| Fresh-clone staleness check (F1) fixed | derived set force-added; `check_stale` exit 0 | `uv run python -m ait.paper.check_stale --manifest configs/paper_artifacts.yaml` |
| Protocol frozen before baseline | commit `0fef5cb` precedes `08c9c3d` | `git log --oneline` |
| Baseline comparison (dev) | `results/raw/baseline-comparison/dev/predictions.json`, `results/derived/baseline_comparison_dev.json` | `uv run python -m ait.experiments.compare_baseline run --scenario-root configs/scenarios --corpus dev` |
| Tests / lint | 231 passed; ruff clean | `uv run pytest -q`; `uv run ruff check ait tests` |
| Paper tables + claim audit | 10 fragments; audit passed | `uv run python -m ait.paper.render_tables --manifest configs/paper_artifacts.yaml --output results/generated`; `uv run python -m ait.paper.audit_claims` |

## Results

| Unit | AIT (TP/FP/FN/TN) | Baseline (TP/FP/FN/TN) |
|---|---|---|
| Scenario (any flag), 33 cases | 15 / 0 / 4 / 14 | 15 / 0 / 4 / 14 |
| Hidden endpoint | 12 / 0 / 2 / 19 | 12 / 0 / 2 / 19 |
| Sensitive field | 5 / 0 / 2 / 26 | 5 / 0 / 2 / 26 |
| Behavioural divergence | 7 / 0 / 0 / 26 | n/a (no counterpart) |

0 disagreements; 0 ambiguous paths; the 4 FNs are the 4 designed evasion cases.
H-B1 holds. H-B2 did not materialize, because the canary rule overlaps DM2 by construction. H-B3 is **not supported**: every divergence case also has an undeclared endpoint.
This is author-written development data, so no statistical claim is made.

## Implementation changes

- `ait/baseline.py` (new): endpoint allowlist (allowed / ambiguous / unparseable / unexpected) plus exact canary search, sharing only `normalize_path` with AIT.
- `ait/experiments/compare_baseline.py` (new): `run` and `hash` commands; Wilson intervals; per-case predictions with ground truth.
- `ait/experiments/schema.py`: optional `canaries`, `ground_truth_outcome` (5 outcome categories).
- `ait/analysis.py`: risk uses `|M \ B|` (was the summary-line count). No corpus result changed; test expectation 95 → 80.
- `ait/integration_trace.py` (new): sanitized HAR/JSONL ingestion, outcome classification, AIT + baseline on the same trace, secret/canary leak guard. `configs/integration/TEMPLATE.policy.yaml`; `traces/` gitignored.
- `run_offline` step 7 (comparison); `baseline_comparison` added to the paper manifest, renderer, template and claims.
- Live table relabelled as capability probes.

## Paper changes (`main.tex`, `report.tex`; `.tex` only, no PDF built per team instruction)

- Title **unchanged** (department-registered). A comment proposes a retitle pending guide approval. A Terminology section explains why the body does not use "fuzzing" or "taint".
- Abstract, contributions, scope, conclusion: bounded to 33 author-written cases, the tie, capability probes, and studies not run.
- New sections: Baseline Comparison, Credential Capability Probes (replaces "Live SaaS Evaluation" / GitHub smoke), Observation of an Independently Developed Integration (not run), Integration Trace Tool, Reproducibility, Ethics.
- Limitations: External Validity, Circular Evaluation, Scale, Baseline Strength added.
- Risk section: CVSS base-score ranges removed; post-audit correction disclosed.
- Stale `generate_*.py` references and Python 3.11 fixed.
- Removed citations: `petsios2017`, `bulekov2023`, `wermke2022` (internally inconsistent; see matrix row 29). `github2022`, `okta2022`, `circleci2023` are now cited at the replay section of `report.tex`.
- Checked by script: no cited-but-missing keys, no unresolved `\ref`, no duplicate labels in either file.

## Not run (and must stay labelled so)

| Study | Why | Owner | Procedure |
|---|---|---|---|
| Independently developed integration (Experiment A) | needs credentials, sandbox, ToS check | Member A | `REAL_INTEGRATION_STUDY.md` |
| Independent held-out set | needs a second author who has not read the detector | Member B | `EXPERIMENT_PROTOCOL.md` §10 |
| RESTler/EvoMaster comparison | image digests unpinned | — | `comparison/` |
| PDF build, `make research-artifact` | team decision; no Perl/`make` on Windows | — | — |

## Human checks outstanding

1. **Guide:** send the two Day-1 questions (`STATUS.md`). They cover the retitle, the target venue, and whether a controlled-evaluation paper is acceptable. Do not change the title without approval.
2. **AI-use disclosure:** check institution and venue policy, then replace the `AI-USE DISCLOSURE: PENDING HUMAN CHECK` comment in both papers with an accurate statement (or remove it if the policy says so). Do not claim compliance before this.
3. **Citations:** verify each against the original (title, authors, venue, year, and that it supports the sentence). These look high-risk or possibly non-existent and must be confirmed or removed: `aliyu2023`, `mainka2022`, `boucher2024`, `lundberg2024`, `kim2022`, `pan2022`, `ding2023`, `chandramouli2023`, `csa2023`, `decarne2023`, `benamara2020`. Also check the `atlidakis2022`/`atlidakis2020` venue. The agent did not judge these against the originals.
4. **Held-out set:** Member B authors, freezes, hashes and tags (`blind-eval-v1`) before any evaluation.
5. **Real integration:** Member A follows `REAL_INTEGRATION_STUDY.md`, including the human redaction review before committing outputs.
6. **Canonical source:** decide whether `main.tex`/`report.tex` (revised here) or the untracked `ieee.tex`/`ait_report.tex` in the main checkout are canonical. The untracked files were **not** revised.
7. **Robustness label F9:** revisit under the new outcome categories, and record any change in the protocol change log rather than editing silently.
8. **Production restructure:** the main checkout's uncommitted work (README claims such as "continuously verifies…") is outside the paper. Keep it out of research claims.

## Risks

- **Main threat to validity:** every positive result is on author-written data. The tie suggests AIT's extra logic is unproven, not that it is useless.
- The canary rule for the dev corpus is derived from marker-named fields, so Part B cannot disagree with DM2 there by construction. Only planted, independently chosen canaries (held-out set or Experiment A) can test it.
- Hash pins were regenerated. The originals are in history at `fe1a2bb`, and `EXPERIMENT_PROTOCOL.md` §12 records the change.
- Archived early live artifacts reflect the pre-fix risk computation (risk 15 without a finding).

## Artifacts

- Docs: `docs/research-sprint/{STATUS,FINDINGS,CLAIM_EVIDENCE_MATRIX,EXPERIMENT_PROTOCOL,REAL_INTEGRATION_STUDY,FINAL_REVIEW}.md`
- Raw: `results/raw/baseline-comparison/dev/predictions.json` (per-case predictions + ground truth); regenerated `results/raw/{scenarios,robustness,replay,sensitivity,benchmark}/`
- Derived (force-added): `results/derived/{offline_manifest,scenario_metrics,sensitivity_summary,replay_match_table,benchmark_summary,robustness_metrics,reproducibility,baseline_comparison_dev}.json`
- Paper inputs: `configs/paper_artifacts.yaml`, `configs/claims.yaml`, `results/generated/*.tex` (gitignored; regenerate with the render command)
