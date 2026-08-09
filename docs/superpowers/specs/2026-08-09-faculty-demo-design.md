# Faculty Product Demo — Design

**Date:** 2026-08-09  
**Status:** Approved  
**Demo date:** 2026-08-10  
**Audience:** Faculty (UI-first)  
**Format:** ~20+ minute product walkthrough (Approach 1 / two-act, UI-centric)

## Goal

Ship a rehearsable product demo that:

1. Walks the Vite SPA through mock CRM assessment (create/select target → run → findings → HTML report).
2. Shows a **Live** SPA page with prior live SaaS evidence (five-row table).
3. Lets the presenter **paste a sandbox API token** in the UI, run one real live probe (GitHub or Google), and see risk/findings **in the UI** — no terminal as the primary prop.

## Non-goals (tomorrow)

- Production-hardening of token handling beyond localhost demo gate
- Notion live probe in the primary path (keep as optional later)
- Wiring full paper/LaTeX automation into the demo
- Cloud deploy of the coordinator with paste-token enabled

## Demo arc

| Block | Time | Surface |
|---|---|---|
| Cold open | 1–2 min | One sentence: AIT finds undeclared integration behavior vs allowlist |
| Act 1 — SPA mock | 12–15 min | Dashboard → Targets → Start run → Run Detail → HTML report |
| Act 2 — Live UI | 6–8 min | Live evidence table → paste token → live probe → findings panel |
| Close | 2–3 min | Five-row live results + limitations |

**Talk track:** policy allowlist → observed traffic → findings (mock and live tell the same story).

## Act 1 — SPA mock path

**Branch base:** `origin/feature/frontend-spa` (already has Vite SPA + coordinator CORS).

**Services:**

| Service | Port |
|---|---|
| Coordinator API | 8000 |
| Mock SaaS | 8001 |
| Demo integration | 8002 |
| Vite | 5173 |

**Click path:**

1. Dashboard — health OK, demo mode on.
2. Targets — seed `demo-integration` or create via form; explain expected endpoints as allowlist.
3. Start run — confirm modal → Run Detail.
4. Poll to completed — highlight hidden endpoint / risk / findings.
5. Open HTML report; optional mock audit link in demo mode.
6. Recent runs on Dashboard (sessionStorage only).

## Act 2 — Live evidence + paste-token probe

### Live evidence (read-only UI)

New SPA route `/live` (nav: **Live**):

- Table of the five selected completed live runs (Google smoke/readonly, GitHub smoke/readonly, Notion readonly).
- Columns: Platform, Scenario, Risk, Result (short text).
- Row expand or detail panel: run id, reached/hidden endpoints, findings list.
- Data source: static JSON bundled or fetched from coordinator `GET /live/evidence` that reads committed `results/derived/live_*.json` (preferred: one API so paths stay server-side).

### Paste-token live probe (demo-only)

**Form fields:**

- Provider: `github` | `google`
- Plan: `smoke` | `readonly` | `smoke-extended` (maps to `configs/live/{provider}_{plan}.yaml` with underscores; extended plans pull more GETs from official API docs, up to the 20-request cap)
- Token: password input (“Paste sandbox token”)
- Submit button
- Demo default: prefer `smoke-extended` when showing live (GitHub 12 calls / Google 8 calls); keep short `smoke` / `readonly` for fast fallback

**On success:** show risk score, hidden endpoints, findings in-page; clear token field; never re-display raw token.

**On failure:** show scrubbed error; clear token field; presenter falls back to evidence table / prior markdown.

### Backend

`POST /live/probes` (coordinator):

Request body:

```json
{
  "provider": "github",
  "plan": "smoke",
  "token": "<sandbox token>"
}
```

Behavior:

1. Reject unless demo live probes are enabled (`AIT_DEMO_LIVE_PROBES=1`) **and** request appears local (Host is `localhost` / `127.0.0.1`).
2. Resolve plan file under `configs/live/` only (allowlist of the five known YAML files; no arbitrary paths).
3. Call `execute_live_plan` with an **in-memory token override** (do not require env for this request; do not persist token).
4. Write artifacts under `results/` as today (redacted); response returns redacted report summary JSON only.
5. Never log the raw token; existing `scrub_secrets` / redact paths apply.

Response (success):

```json
{
  "run_id": "...",
  "provider": "github",
  "plan_id": "github-smoke",
  "status": "completed",
  "risk_score": 50.0,
  "hidden_endpoints": ["/user/orgs", "/user/repos"],
  "reached_endpoints": ["/user", "/user/orgs", "/user/repos"],
  "findings": [ /* Finding models, redacted */ ]
}
```

### Frontend security rules (hard)

- Token never written to `localStorage` / `sessionStorage`.
- Masked input; clear on success, error, and unmount.
- Calls go through Vite proxy or `localhost:8000` only for the demo machine.
- Use throwaway sandbox tokens; rotate after shared-room demos if pasted.

## Failure backups

1. Alternate provider (Google ↔ GitHub) via same form.
2. Skip live POST; narrate from `/live` evidence table (prior successful artifacts).
3. Never spend >60s debugging OAuth in front of faculty.

## Success criteria

- [ ] Act 1 completes without terminal.
- [ ] `/live` shows the five-row evidence table.
- [ ] Paste GitHub **or** Google smoke token produces findings in the SPA.
- [ ] Token not present in browser storage after the run.
- [ ] Full dry run rehearsed once the night before.

## Branch / delivery

- Worktree or branch off `feature/frontend-spa`.
- Bring forward needed live result artifacts from `feature/research-phases` if missing on SPA branch.
- Keep paste-token endpoint behind `AIT_DEMO_LIVE_PROBES=1` so default installs do not expose it.
