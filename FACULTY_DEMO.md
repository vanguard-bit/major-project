# Faculty demo — run guide

Goal: same flow as today. **Demo → results → Live → paste key → results.**  
Tokens stay in a local `.env` (never commit). Plan YAML under `configs/live/` is in git.

## One-time setup

Needs **Python 3.12+**, [**uv**](https://github.com/astral-sh/uv), and **Node.js 20+**.

`Make` is **not** required. (`make setup` is only an optional alias for `uv sync --dev`.)

### macOS / Linux

```bash
git clone <this-repo-url>
cd major_project
git checkout main

uv sync --dev
cd frontend && npm install && cd ..
```

### Windows (PowerShell)

Same install, without the bash `npm run dev` helper. Run these in **PowerShell** from the repo root:

```powershell
git clone <this-repo-url>
cd major_project
git checkout main

uv sync --dev
cd frontend
npm install
cd ..
```

Put the shared `.env` at the **repo root** (same folder as `README.md`). Example shape — use the real values you receive separately:

```text
# major_project/.env  (gitignored — do not commit)
AIT_GITHUB_TOKEN=ghp_...
AIT_GOOGLE_TOKEN=ya29....
AIT_NOTION_TOKEN=ntn_...
```

Confirm live plans are present (no secrets inside):

```bash
ls configs/live/*.yaml
```

Windows:

```powershell
dir configs\live\*.yaml
```

## Start everything

### macOS / Linux (one command)

```bash
cd frontend
npm run dev
```

That starts all four services (same as the four Windows windows below).

### Windows (four terminals — run one command each)

Open **four** PowerShell windows. In **each**, `cd` to the repo root (`major_project`), then set tokens and the live-probe flag once:

```powershell
cd path\to\major_project
$env:AIT_DEMO_LIVE_PROBES = "1"
# Optional: paste tokens here if you are not loading .env another way
$env:AIT_GITHUB_TOKEN = "ghp_..."
$env:AIT_GOOGLE_TOKEN = "ya29...."
$env:AIT_NOTION_TOKEN = "ntn_..."
```

Then start **one** service per window (leave each running):

**1 — Mock SaaS (port 8001)**

```powershell
uv run uvicorn ait.mock_saas:app --host 127.0.0.1 --port 8001 --reload
```

**2 — Demo integration (port 8002)**

```powershell
uv run uvicorn ait.demo_integration:app --host 127.0.0.1 --port 8002 --reload
```

**3 — Coordinator API (port 8000)**

```powershell
$env:AIT_DEMO_LIVE_PROBES = "1"
uv run uvicorn ait.api:app --host 127.0.0.1 --port 8000 --reload
```

**4 — Vite SPA (port 5173)**

```powershell
cd frontend
npm run dev:ui
```

Open **http://127.0.0.1:5173**

| Service            | Port |
|--------------------|------|
| SPA                | 5173 |
| Coordinator API    | 8000 |
| Mock SaaS          | 8001 |
| Demo integration   | 8002 |

You can paste the sandbox token in the Live form even if the env vars above are empty.

## Demo script (no extra steps)

### 1. Demo → results

1. Open **Demo** (home page).
2. Click **Start demo assessment**.
3. Wait for the run, then open the run — report and config show on that page.

### 2. Live → YAML → paste key → results

1. Open **Live**.
2. Pick a cell (e.g. GitHub × smoke). The plan YAML field fills from `configs/live/` automatically.
3. Paste the sandbox token into the token field (or rely on env tokens if set).
4. Run the probe.
5. Stay on **Live** — the matrix and detail panel update with results.

That is the whole path: **show Demo → show results → move to Live → YAML loaded → paste key → show results.**

## Optional: Hide explanations / Screenshot mode

- **Hide explanations** (nav): cleaner screen while walking through.
- **Screenshot mode** (Live only): summary table for slides.

## If something fails

| Symptom | Fix |
|---------|-----|
| `npm run dev` / missing `node_modules` | `cd frontend` then `npm install` |
| Live probe API 404 | Restart the API window with `$env:AIT_DEMO_LIVE_PROBES = "1"` set |
| Auth / credential errors on Live | Paste token in the form, or set `AIT_*_TOKEN` in that PowerShell session |
| Ports in use | Stop other processes on 8000–8002 / 5173 |

Do not commit `.env`. Do commit / pull `configs/live/*.yaml` — those plans are required for Live auto-fill.
