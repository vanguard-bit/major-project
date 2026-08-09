# Faculty demo — run guide

Goal: same flow as today. **Demo → results → Live → paste key → results.**  
Tokens stay in a local `.env` (never commit). Plan YAML under `configs/live/` is in git.

## One-time setup (any machine)

Needs **Python 3.12+**, [**uv**](https://github.com/astral-sh/uv), and **Node.js 20+**.

```bash
git clone <this-repo-url>
cd major_project
git checkout main

make setup
cd frontend && npm install && cd ..
```

Put the shared `.env` at the **repo root** (same folder as `Makefile`). Example shape — use the real values you receive separately:

```bash
# major_project/.env  (gitignored — do not commit)
AIT_GITHUB_TOKEN=ghp_...
AIT_GOOGLE_TOKEN=ya29....
AIT_NOTION_TOKEN=ntn_...
```

Confirm live plans are present (no secrets inside):

```bash
ls configs/live/*.yaml
```

## Start everything

```bash
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173**

| Service            | Port |
|--------------------|------|
| SPA                | 5173 |
| Coordinator API    | 8000 |
| Mock SaaS          | 8001 |
| Demo integration   | 8002 |

`npm run dev` turns on live probes (`AIT_DEMO_LIVE_PROBES=1`) and loads repo-root `.env` for tokens.

## Demo script (no extra steps)

### 1. Demo → results

1. Open **Demo** (home page).
2. Click **Start demo assessment**.
3. Wait for the run, then open the run — report and config show on that page.

### 2. Live → YAML → paste key → results

1. Open **Live**.
2. Pick a cell (e.g. GitHub × smoke). The plan YAML field fills from `configs/live/` automatically.
3. Paste the sandbox token into the token field (or rely on `.env` if already loaded).
4. Run the probe.
5. Stay on **Live** — the matrix and detail panel update with results.

That is the whole path: **show Demo → show results → move to Live → YAML loaded → paste key → show results.**

## Optional: Hide explanations / Screenshot mode

- **Hide explanations** (nav): cleaner screen while walking through.
- **Screenshot mode** (Live only): summary table for slides.

## If something fails

| Symptom | Fix |
|---------|-----|
| `npm run dev` asks for `npm install` | `cd frontend && npm install` |
| Live probe API 404 | Restart via `npm run dev` (must set `AIT_DEMO_LIVE_PROBES=1`) |
| Auth / credential errors on Live | Check repo-root `.env` tokens; paste token in the form as override |
| Ports in use | Stop other processes on 8000–8002 / 5173 |

Do not commit `.env`. Do commit / pull `configs/live/*.yaml` — those plans are required for Live auto-fill.
