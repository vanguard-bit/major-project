# Research Artifacts

This directory holds experiment outputs produced by AIT.

## Layout

- `raw/` — immutable observations from scenario, live, replay, benchmark, and tool runs
- `derived/` — reproducible aggregates and metrics computed from raw artifacts
- `generated/` — LaTeX fragments consumed by `main.tex` and `report.tex`

## Policy

- Every JSON artifact must use the `ArtifactEnvelope` schema from `ait.artifacts`, including
  schema version, UTC timestamp, command, seed, and environment provenance.
- Secrets and unredacted live payloads must never be committed.
- Do not hand-edit numerical results. Regenerate them with the experiment commands.
- Prefer committing only fixtures and policy files that are required for reproducibility;
  large private live captures stay local under gitignored paths.
