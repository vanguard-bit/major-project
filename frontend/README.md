# AIT Frontend

Vite + React + TypeScript SPA for the Adversarial Integration Tester coordinator.

## Quick start

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Scripts

| Command | Description |
|---------|-------------|
| `npm install` | Install dependencies |
| `npm run dev` | Start Vite dev server (port 5173) |
| `npm run build` | Typecheck (`tsc -b`) and production build to `dist/` |
| `npm run test` | Run Vitest unit tests once |
| `npm run test:watch` | Run Vitest in watch mode |
| `npm run preview` | Preview production build locally |

## Environment variables

Create a `.env` file in `frontend/` (optional — defaults work for local dev):

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_DEMO_MODE=false
```

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Coordinator API base URL |
| `VITE_DEMO_MODE` | `false` | When `true`, demo-mode UI is enabled by default (overridable via localStorage) |

## Local services and ports

Start backend services from the repo root (venv activated, package installed):

```bash
uvicorn ait.mock_saas:app --port 8001 --reload
uvicorn ait.demo_integration:app --port 8002 --reload
uvicorn ait.api:app --port 8000 --reload
```

| Service | Port |
|---------|------|
| Coordinator API | 8000 |
| Mock SaaS | 8001 |
| Demo integration | 8002 |
| Vite dev server | 5173 |

## CORS and Vite proxy

The dev server proxies API paths to the coordinator so you can avoid CORS during local development:

- `/health`, `/targets`, `/runs` → `http://localhost:8000`

The proxy does **not** match `/` (the SPA root), so client-side routing is unaffected.

If you set an absolute `VITE_API_BASE_URL` (browser calls `:8000` directly), the coordinator must allow CORS — it ships with `CORSMiddleware` for local SPA use. Alternatively, leave the default and rely on the path proxy by using relative API paths (the default client uses the absolute base URL).

## Browser storage

| Key | Storage | Purpose |
|-----|---------|---------|
| `ait.recentRuns` | `sessionStorage` | Recent run entries for this tab session (max 10). Cleared when the tab closes. |
| `ait.demoMode` | `localStorage` | User toggle for demo-mode UI. Falls back to `VITE_DEMO_MODE` when unset. |

There is no `GET /runs` list endpoint — recent runs are client-side only.

## HTML report URL

From Run Detail, **Open report** opens:

```
{VITE_API_BASE_URL}/runs/{run_id}/report?format=html
```

Example: `http://localhost:8000/runs/abc123/report?format=html`

In demo mode, an audit link is also shown: `http://localhost:8001/admin/audit/{run_id}`.

## Optional Playwright E2E (not in CI)

End-to-end tests are optional and not run in GitHub Actions (services are not orchestrated in CI).

Suggested manual flow:

1. Start coordinator (`:8000`), mock SaaS (`:8001`), and demo integration (`:8002`).
2. Run `npm run dev` and open the SPA.
3. Create a target (or use seed `demo-integration`).
4. Start a run, wait for a terminal status on Run Detail.
5. Open the HTML report and assert expected content.

To add Playwright later: install `@playwright/test`, add `npm run test:e2e`, and keep it out of the default CI workflow unless backend services are started in the job.

## CI

GitHub Actions runs `npm ci`, `npm test`, and `npm run build` on changes under `frontend/` (see `.github/workflows/frontend.yml`).
