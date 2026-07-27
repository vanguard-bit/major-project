# Generated paper fragments

Files in this directory are produced by:

```bash
uv run python -m ait.paper.render_tables \
  --manifest configs/paper_artifacts.yaml \
  --output results/generated
```

Do not hand-edit `*.tex` here. Each fragment starts with a
`GENERATED FILE — DO NOT EDIT` header.

Regenerate after offline experiments and hash refresh:

```bash
make experiments-offline
make update-paper-hashes
make render-paper
```
