# Reproducibility

Independent reviewers can regenerate offline tables and compile both papers from
this repository. Live SaaS and external-tool experiments are credential/Docker
gated and remain `NOT RUN` until real artifacts are selected.

## 1. Tested environment

| Component | Version / note |
|---|---|
| OS | Linux (Kali) 6.19.x amd64 |
| Python | 3.12 (via `uv`) |
| Package manager | `uv` (lockfile `uv.lock`) |
| LaTeX | `latexmk` + `pdflatex` (TeX Live). Packages: `latexmk`, `texlive-latex-extra`, and `texlive-publishers` (provides `IEEEtran.cls` for `main.tex`). PDF targets fail clearly when `latexmk` or required classes are absent. |
| Docker | Optional; required only for RESTler/EvoMaster comparison scripts under `comparison/` |

## 2. Clean setup

```bash
uv sync --dev
make check
```

## 3. Offline one-command reproduction

```bash
make research-artifact
```

This runs lint/tests, offline experiments, refreshes
`configs/paper_artifacts.yaml` hashes, staleness check, table render, claim
audit, and both PDF builds.

Manual equivalent:

```bash
uv run python -m ait.experiments.run_offline --output-root results
uv run python -m ait.paper.update_artifact_hashes
uv run python -m ait.paper.check_stale
uv run python -m ait.paper.render_tables \
  --manifest configs/paper_artifacts.yaml \
  --output results/generated
uv run python -m ait.paper.audit_claims
make paper-main paper-report
```

## 4. Live credentials and safety

- Plans: `configs/live/*.yaml`
- Runner: `uv run python -m ait.live_runner ...` (see CLI help)
- Tokens via environment only (`AIT_GITHUB_TOKEN`, Notion token vars as documented by the runner). Never commit secrets.
- Allowlisted hosts/paths only; treat findings as policy mismatch vs declared allowlist, not vendor exploits.
- `make experiments-live` does **not** call APIs; follow this document for explicit runs.

## 5. External-tool setup and budgets

See `comparison/README.md`. Digests must be pinned before claiming a run.
Wall-clock budget: 600 seconds; seed `20260727`. Until images are pinned and
present, scripts exit `NOT_RUN`. Do not cite parser fixtures as experiments.

## 6. Artifact directories

| Path | Meaning |
|---|---|
| `results/raw/` | Immutable observations |
| `results/derived/` | Recomputable aggregates + offline manifest |
| `results/generated/` | LaTeX fragments for both papers (`*.tex`) |

## 7. Paper compilation

```bash
make render-paper
make paper-main    # latexmk -pdf main.tex
make paper-report  # latexmk -pdf report.tex
```

Both documents `\input{results/generated/<fragment>.tex}` for empirical tables.

## 8. Expected runtime and disk

- Offline experiments: on the order of one to a few minutes on a laptop (dominated by benchmark repetitions).
- Disk: typically tens of MB under `results/` after a full offline run.

## 9. Verifying hashes

```bash
uv run python -m ait.paper.update_artifact_hashes   # rewrite digests from disk
uv run python -m ait.paper.check_stale              # inputs + offline artifacts
sha256sum results/derived/*.json
```

`configs/paper_artifacts.yaml` must name exact paths and SHA-256 values; the
renderer never auto-selects “best” or “newest” runs.

## 10. Known unavailable artifacts

| Selection | Status |
|---|---|
| `live_runs.*` | `null` → tables show `NOT RUN` |
| `tool_comparison` | `null` → `NOT RUN` |
| `robustness_metrics` / `reproducibility` | required by offline Phase~5 gate and `make research-artifact` |

## 11. Ethics

Synthetic mocks and researcher-constructed incident reconstructions are labeled
as such. Sandbox live data must be redacted before commit. No private repository
names, user IDs, tokens, or response bodies belong in artifacts or papers.
