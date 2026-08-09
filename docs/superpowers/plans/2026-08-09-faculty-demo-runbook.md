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

## Act 1 — SPA Demo (`/demo`, ~12–15 min)

1. Nav is **Demo | Live** only. Confirm API health on Demo.
2. Walk **Why → This act → Policy in play** (use **Explain** if faculty ask).
3. **Start demo assessment** on seeded `demo-integration` → Run Detail.
4. Wait for completed; call out hidden `/billing`, risk, findings — all visible on the run page report.
5. Point at **Run config** (allowlist / scopes / sensitive markers) on the same page.
6. Back to Demo → **Outcome** (recent runs) → **Continue to Live**.

Advanced (collapsed): create target, open run by id, demo mode — only if asked.

Talk track: *policy allowlist vs observed traffic*.

## Act 2 — Live (`/live`, ~6–8 min)

1. Nav **Live** — transition copy, then probe form (YAML auto-fills).
2. Scroll to **Live probe results** board (nine plan cells; do **not** say “3×3” on screen).
3. Optional: **Screenshot mode** for a slide capture.
4. Optional live click: provider GitHub, plan `smoke-extended`, paste sandbox token only.
5. Advanced → prior-runs table if someone asks for a raw run id.

Kill rule: no OAuth debugging longer than 60 seconds.

Rehearsal tip: uncheck nothing by default (explanations visible). Use **Hide explanations** in the nav (or per-panel **Hide**) when you want a cleaner walkthrough.

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
