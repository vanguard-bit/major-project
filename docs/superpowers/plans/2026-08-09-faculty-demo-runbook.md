# Faculty Demo Runbook (2026-08-10)

UI-first product demo on branch `feature/faculty-demo`.

## Start services

From `frontend/`:

```bash
cd /home/loki/projects/major_project/frontend
npm run dev
```

Starts mock SaaS (:8001), demo integration (:8002), coordinator with `AIT_DEMO_LIVE_PROBES=1` (:8000), and Vite (:5173). Loads repo-root `.env` for live tokens.

UI-only: `npm run dev:ui`

## Act 1 — SPA mock (~12–15 min)

1. Dashboard — health OK; turn **Demo mode** on.
2. **Targets** — use seeded `demo-integration` (or create one).
3. Start run → confirm → Run Detail.
4. Wait for completed; call out hidden `/billing`, risk, findings.
5. **Open HTML report**.
6. Back to Dashboard — recent runs.

Talk track: *policy allowlist vs observed traffic*.

## Act 2 — Live UI (~6–8 min)

1. Nav **Live**.
2. Show prior-runs table (GitHub/Google/Notion).
3. **Run live probe**: provider GitHub, plan `smoke-extended`, paste token from `.env` / password manager (or `gh auth token`).
4. Show risk + hidden endpoints in the result panel.
5. Backup: Google smoke / smoke-extended, or narrate from the table only.

Kill rule: no OAuth debugging longer than 60 seconds.

## Kill / backup

| Failure | Action |
|---|---|
| Mock services down | Restart uvicorn trio; SPA alone is not enough for Act 1 |
| Live probe 404 | Confirm `AIT_DEMO_LIVE_PROBES=1` on coordinator |
| Live probe 502 / auth | Refresh Google token; try GitHub; else use evidence table |
| Token paste awkward | Pre-copy token to clipboard before talking |

## After demo

- Rotate Notion token if it was pasted in a shared room.
- Do not commit `.env`.
