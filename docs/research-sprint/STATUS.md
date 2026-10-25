# Research Sprint — Status

Sprint: Research Paper Improvement Sprint (7 days, team of two).
Current phase: **All agent-executable work done. Remaining items are human-owned** (see "Phase progress" and `FINAL_REVIEW.md`).

## Phase progress (updated 2026-10-25)

| Phase | Status | Evidence |
|---|---|---|
| 0 Baseline audit | done | this file, `FINDINGS.md`, `CLAIM_EVIDENCE_MATRIX.md` (commit `3475baf`) |
| 1 Reproducibility + claim audit | done | F1 fixed: derived set force-added, pins regenerated, `check_stale` passes. Payload-level reproduction verified. Risk-score bug fixed (no result change) |
| 2 Real integration | **tooling done; study not run** (human-owned: credentials, sandbox, ToS) | `ait/integration_trace.py`, `REAL_INTEGRATION_STUDY.md` |
| 3a Baseline comparison (dev) | done; result: tie | protocol frozen first (`0fef5cb`), `ait/baseline.py`, `results/derived/baseline_comparison_dev.json` (`08c9c3d`) |
| 3b Independent held-out set | **not run** (human-owned: Member B authors and freezes) | procedure in `EXPERIMENT_PROTOCOL.md` §10 |
| 4 Paper revision | done for `main.tex` and `report.tex` (`.tex` only, no PDF per team instruction); title kept pending guide approval | see `FINAL_REVIEW.md` |
| 5 Release review | done (agent side) | `FINAL_REVIEW.md` |

### Commands run after Phase 0 (worktree `research-sprint/sprint-work`)

| Command | Exit | Outcome |
|---|---|---|
| `uv run pytest -q` | 0 | 231 passed |
| `uv run ruff check ait tests` | 0 | all checks passed |
| `uv run python -m ait.experiments.run_offline --output-root results` | 0 | 46 artifacts; derived payloads identical to Phase 0 run; comparison identical to `08c9c3d` |
| `uv run python -m ait.paper.update_artifact_hashes` | 0 | pins rewritten (originals in history at `fe1a2bb`) |
| `uv run python -m ait.paper.check_stale --manifest configs/paper_artifacts.yaml` | 0 | passed |
| `uv run python -m ait.paper.render_tables --manifest configs/paper_artifacts.yaml --output results/generated` | 0 | 10 fragments (new: `baseline_comparison.tex`) |
| `uv run python -m ait.paper.audit_claims` | 0 | passed, including the new `baseline-comparison` claim in both papers |
| Secret-pattern scan over all tracked + new files | — | only obviously fake fixtures in `tests/test_live_runner.py` (`ghp_SUPER_SECRET_TOKEN_DO_NOT_LEAK` etc.) |

The Phase 0 record below is kept unchanged for history.

## Repository state at audit time (2026-10-25)

| Item | Value |
|---|---|
| Branch audited | `main` |
| Commit audited | `fe1a2bbc946c2cdadd9f6a37bcb3b88ef34ed69e` (`origin/main` identical) |
| Tags | none |
| Stash | `stash@{0}` on `antigravity-version` (untouched) |
| Working tree | Large **uncommitted** "production restructure" (66 files staged/modified: `ait/api/`, `ait/db/`, `ait/services/`, `ait/workers/`, Docker, CI, README rewrite, frontend pages) plus many untracked files (`ieee.tex`, `ait_report.tex`, `main111.tex.txt`, PDFs, images, new live raw artifacts). **All preserved; nothing reset, deleted, or committed on their behalf.** |
| Audit method | Clean detached worktree of `fe1a2bb` at `C:\Users\SHREYA\ait-baseline` (outside OneDrive). All regeneration happened there so committed artifacts in the main checkout were not overwritten. |

## Environment

| Component | Version |
|---|---|
| OS | Windows 11 10.0.26300 (paper's tested env: Linux Kali 6.19, Python 3.12.13) |
| Python | 3.12.10 (via `uv` 0.11.16, `uv.lock`) |
| Key deps | pydantic 2.13.4, fastapi 0.140.0, httpx 0.28.1, typer 0.27.0, jinja2 3.1.6, pyyaml 6.0.3, pytest 8.4.2, ruff 0.16.0 |
| Node | 22.19.0 (frontend not part of research evidence) |
| LaTeX | MiKTeX `latexmk`/`pdflatex` present; `latexmk` unusable (no Perl). PDF build **not run** per team instruction — only `.tex` fragments are generated. |

## Commands run and actual outcomes

All commands run in the clean `fe1a2bb` worktree unless noted.

| # | Command | Exit | Outcome |
|---|---|---|---|
| 1 | `uv run pytest -q` (main checkout, **uncommitted working tree**) | 0 | 249 passed |
| 2 | `uv sync --dev` | 0 | env created from `uv.lock` |
| 3 | `uv run pytest -q` | 0 | 225 passed (committed tree) |
| 4 | `uv run ruff check ait tests` | 0 | all checks passed |
| 5 | `uv run python -m ait.artifacts results` (`make validate-artifacts`) | 0 | 51 artifacts schema-valid |
| 6 | `uv run python -m ait.paper.check_stale` (fresh clone, before regen) | 1 | **FAIL**: `missing artifact file: results/derived/offline_manifest.json` — `results/derived/*.json` is gitignored, so pinned derived artifacts are not in the repo |
| 7 | `uv run python -m ait.experiments.run_offline --output-root results` (run 1) | 0 | 16/16 scenarios PASS, 3/3 replay PASS, 13/13 robustness in-scope PASS, 4/4 evasion cases FAIL as designed, reproducibility 5/5; 44 artifacts; ~12 s |
| 8 | Hash comparison vs `configs/paper_artifacts.yaml` | — | **All 8 offline pins DIFFER**; all 5 live pins MATCH |
| 9 | Payload comparison (provenance stripped) vs committed raw files | — | 34/38 identical; 3 replay differ only by Windows path separator in `configuration.source_path`; benchmark differs (timings) |
| 10 | `run_offline` (run 2) + compare derived payloads to run 1 | 0 | scenario_metrics, replay, robustness, reproducibility, sensitivity **identical**; benchmark_summary and offline_manifest differ (timing-dependent) |
| 11 | `uv run python -m ait.paper.update_artifact_hashes` | 0 | rewrote pins **in the throwaway worktree only** (documented pipeline step) |
| 12 | `uv run python -m ait.paper.check_stale` | 0 | passed (after step 11) |
| 13 | `uv run python -m ait.paper.render_tables --manifest configs/paper_artifacts.yaml --output results/generated` | 0 | 9 `.tex` fragments written |
| 14 | `uv run python -m ait.paper.audit_claims` | 0 | passed — but see FINDINGS F3 (it does not catch prose/table contradictions) |
| 15 | `latexmk -pdf main.tex` / `report.tex` | 1 | MiKTeX: Perl missing. PDF build then cancelled by team decision. **No PDF produced or claimed.** |

## Evidence categories (kept separate everywhere)

| Category | What exists | Status |
|---|---|---|
| 1. Unit/integration tests | 225 tests (committed), 249 (working tree) | verified (pass) |
| 2. Synthetic/mocked scenarios | 16 YAML scenarios; 13 robustness + 4 evasion; 3 incident reconstructions | reproduced (payload-level) — **author-scripted traces and labels; no integration executes** |
| 3. Offline benchmark | Analysis Engine micro-benchmark over synthetic log widths | reproduced (non-deterministic timings, as expected) |
| 4. Credential/token-capability probes | `results/raw/live/*` (GitHub, Google, Notion; 13 committed + untracked new ones) | artifacts present; **these are AIT sending planned requests with a team token — capability probes, not integration behaviour** |
| 5. Actual third-party integration observations | none | **not run** |
| 6. Blocked / not run | RESTler/EvoMaster comparison (`NOT_RUN reason=image_digest_unpinned`); independent held-out set; real integration study; PDF build | not run |

## Gate 0 — proposed minimal plan (as proposed at Phase 0; items 1–4 now done, 5–6 human-owned)

See `FINDINGS.md` §"Smallest changes required".

1. Make the evidence chain reproducible without editing original pins: commit a frozen derived set from a recorded run (force-add), record new hashes alongside the original ones, and document that byte-hash reproduction is impossible by design (timestamps in provenance) — compare payloads instead.
2. Two-part baseline (`endpoint allowlist` + `exact canary-value search`) in one small module, run over the same scenario corpus.
3. Relabel live artifacts as **capability probes** in prose and tables; resolve the live NOT RUN vs. rendered-rows contradiction.
4. Terminology: drop "differential fuzzing" and "taint" claims (no input generation; sensitive detection is field-name matching).
5. Real-integration study (human-owned prerequisites) or documented fallback by Day 3.
6. Independent held-out set authored by Member B, frozen and tagged before first evaluation.

## Human actions needed next

| Owner | Action |
|---|---|
| Both | Review FINDINGS.md and the claim matrix; approve/modify the Gate 0 plan. |
| Both | Decide the **canonical paper source**: committed `main.tex`/`report.tex` vs untracked `ieee.tex` / `ait_report.tex` / `main111.tex.txt`. |
| Both | Decide what happens to the uncommitted production restructure (separate branch/PR?) so research changes don't get mixed with it. |
| Member A | Pick one candidate integration (FINDINGS §"Candidate integrations"), confirm provider ToS for automated testing, create sandbox account/repo/workspace, obtain minimum-scope credentials **into env vars only**. |
| Member A | Confirm whether earlier live runs with risk 15 / no hidden endpoint (F7) came from an older code version. |
| Member B | Start drafting 15–25 held-out scenarios **without reading `ait/analysis.py` or existing scenario YAMLs' labels**; agree the scenario file format with Member A using only `configs/scenarios/schema.example.yaml`. |
| Member B | Check institution and target-venue AI-use disclosure rules. |
| Either | Send the two guide questions below. |

## Two questions for the guide (Day 1)

1. **Title and claim scope:** The registered title says "Differential Fuzzing and Taint-Seeded Data Tracking", but the implementation performs neither input fuzzing nor taint propagation (it is differential baseline/mutated policy-conformance testing with canary/field-name checks). May we retitle (e.g., "Policy-Based Monitoring of Third-Party SaaS Integration Behavior: A Prototype and Controlled Evaluation"), or must the registered title be kept with corrected terminology in the body?
2. **Target venue and acceptable evidence:** Which venue/format (and page limit) are we targeting, and is a controlled-evaluation prototype paper acceptable if observation of a real third-party integration proves infeasible within the sprint (with that gap stated as a limitation)?
