# Minimal Frontend SPA — Adversarial Integration Tester

**Date:** 2026-08-06  
**Status:** Approved for implementation planning  
**Approach:** Spec-exact Vite SPA (Approach 1) — no backend changes for v1

## Goal

Build a minimal React + TypeScript SPA under `frontend/` that lets researchers/operators:

- List and create targets against the coordinator API
- Start assessment runs
- View run status, findings, and open the HTML report
- Optionally use demo-mode controls for local mock SaaS debugging

Coordinator API (dev default): `http://localhost:8000`

## Architecture overview

### Tech stack

| Concern | Choice |
|---------|--------|
| Bundler / dev server | Vite |
| UI | React 18 + TypeScript |
| Routing | `react-router-dom` (`/`, `/targets`, `/runs/:id`) |
| HTTP | axios (`ApiClient.ts`) |
| Server state | TanStack Query (react-query) |
| Forms | react-hook-form + zod |
| Styles | Basic CSS (`src/styles/index.css`) — no Tailwind |
| Unit tests | Vitest + React Testing Library |
| E2E (optional) | Playwright — documented, not in default CI |

### Directory layout

```
frontend/
  package.json
  tsconfig.json
  tsconfig.node.json
  vite.config.ts
  index.html
  .env.example
  .gitignore
  README.md
  src/
    main.tsx                 # QueryClientProvider + BrowserRouter
    App.tsx                  # routes + layout nav
    types/
      api.ts                 # TargetConfig, RunRecord, Finding, etc.
    pages/
      Dashboard.tsx
      Targets.tsx
      RunDetail.tsx
    components/
      ApiClient.ts
      useApiHooks.ts
      CreateTargetForm.tsx
      StartRunButton.tsx
      RecentRuns.tsx
      DemoModeToggle.tsx
    hooks/
      useRecentRuns.ts
      useDemoMode.ts
    styles/
      index.css
    test/
      setup.ts
      createTargetPristine.test.ts   # or CreateTargetForm.test.tsx
      StartRunButton.test.tsx
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Coordinator base URL |
| `VITE_DEMO_MODE` | `false` | Build-time default for demo audit controls |

UI demo toggle may override via `localStorage` key `ait.demoMode` (see Demo-mode).

### npm scripts

- `npm run dev` — Vite on port 5173
- `npm run build` — typecheck + production build
- `npm run preview` — preview production build
- `npm run test` — Vitest
- `npm run test:e2e` — Playwright (optional; requires local services)

### Vite proxy (dev)

Do **not** proxy `'/'` (that would steal the SPA). Prefer path-specific proxying, e.g.:

```ts
server: {
  proxy: {
    '/health': { target: 'http://localhost:8000', changeOrigin: true },
    '/targets': { target: 'http://localhost:8000', changeOrigin: true },
    '/runs': { target: 'http://localhost:8000', changeOrigin: true },
  },
}
```

Alternatively, keep axios `baseURL` pointed at `:8000` and rely on coordinator CORS. Path-specific proxy is the safe local-dev default when using relative API paths; if using absolute `VITE_API_BASE_URL`, proxy is optional.

## Routes & page responsibilities

| Path | Page | Responsibility |
|------|------|----------------|
| `/` | `Dashboard` | Health status; recent runs (sessionStorage); short targets preview / link to `/targets`; Open run by ID; demo-mode toggle |
| `/targets` | `Targets` | Full targets list; CreateTargetForm; StartRunButton per target |
| `/runs/:id` | `RunDetail` | Run status (polled); findings table; Open report; demo audit panel when demo mode on |

**Layout chrome:** simple top nav — Dashboard | Targets. No authentication.

### Dashboard details

Always show:

1. API health (`GET /health`)
2. Targets summary (`GET /targets`) with link to full Targets page

Conditionally show:

3. **Recent runs (this browser)** — only if `ait.recentRuns` has entries
4. **Open run by ID** — text input + button → navigate to `/runs/:id` (supports IDs from CLI/other tools)

### Targets page details

- Table columns: `name`, `base_url`, `environment`, actions
- CreateTargetForm above or beside the list
- Each row: StartRunButton (confirm modal → `POST /runs`)

### RunDetail details

- Fetch `GET /runs/{id}` and `GET /runs/{id}/findings`
- Show status, timestamps/last-updated, findings table (severity, category, endpoint, title / description fields as available)
- **Open report** button: `window.open(`${apiBase}/runs/${runId}/report?format=html`, '_blank')`
- Poll run until terminal status (see Data flow)
- Demo panel (if demo mode): link to `http://localhost:8001/admin/audit/{run_id}` with developer warning

## Component & hook map

| Module | Role |
|--------|------|
| `types/api.ts` | Hand-authored types from `ait/models.py` |
| `ApiClient.ts` | axios instance + `mapValidationErrorsToForm` |
| `useApiHooks.ts` | `useHealth`, `useTargets`, `useCreateTarget`, `useStartRun`, `useRun`, `useFindings` |
| `CreateTargetForm.tsx` | Hybrid create form + advanced accordion |
| `StartRunButton.tsx` | Confirm modal → start run → recentRuns + toast + navigate |
| `RecentRuns.tsx` | List session runs via `useQueries`; clear / prune |
| `DemoModeToggle.tsx` | Env default + localStorage override |
| `useRecentRuns.ts` | sessionStorage contract for recent runs |
| `useDemoMode.ts` | Demo mode read/write |

## TypeScript API types (`src/types/api.ts`)

Derived from `ait/models.py`. Key rules:

- URLs are `string` on the wire (Pydantic `HttpUrl` serializes to string)
- Run identifier field is always `run_id` (never `id`)
- `auth_type`: `"static_token" | "oauth_client_credentials"` — default `static_token` when advanced unused
- `exchanges` may be typed loosely (`unknown[]`) in v1

```ts
export type AuthType = 'static_token' | 'oauth_client_credentials';

export interface TokenConfig {
  token?: string | null;
  token_url?: string | null;
  client_id?: string | null;
  client_secret?: string | null;
  scope?: string | null;
}

export interface TargetConfig {
  name: string;
  environment?: string;
  base_url: string;
  integration_sync_url: string;
  audit_base_url: string;
  auth_type?: AuthType;
  token_config?: TokenConfig;
  openapi_paths?: string[];
  seed_endpoints?: string[];
  expected_endpoints?: string[];
  expected_scopes?: string[];
  sensitive_markers?: string[];
  description?: string;
}

export interface TestRunConfig {
  crawl_depth?: number;
  mutation_budget?: number;
  taint_fields?: string[];
  replay_count?: number;
  timeout_seconds?: number;
  rate_limit_per_minute?: number;
  safety_mode?: boolean;
}

export interface Finding {
  severity: 'low' | 'medium' | 'high' | 'critical';
  category:
    | 'hidden_endpoint'
    | 'sensitive_field_access'
    | 'behavioral_divergence'
    | 'policy_violation';
  endpoint: string;
  title: string;
  evidence: string;
  expected_behavior: string;
  observed_behavior: string;
  confidence?: number;
  remediation_note?: string;
}

export interface RunReport {
  run_id: string;
  target_name: string;
  status: string;
  reached_endpoints: string[];
  hidden_endpoints: string[];
  sensitive_fields_accessed: string[];
  divergence_summary: string[];
  risk_score: number;
  findings: Finding[];
}

export interface RunRecord {
  run_id: string;
  status: string;
  target: TargetConfig;
  config: TestRunConfig;
  findings: Finding[];
  exchanges: unknown[];
  report?: RunReport | null;
}
```

## Data flow & caching

### Query keys (stable)

| Key | Endpoint |
|-----|----------|
| `['health']` | `GET /health` |
| `['targets']` | `GET /targets` |
| `['run', runId]` | `GET /runs/{runId}` |
| `['findings', runId]` | `GET /runs/{runId}/findings` |

There is **no** `GET /runs` list endpoint. Do not invent a global runs query.

### Cache / refetch rules

| Query | staleTime | Notes |
|-------|-----------|--------|
| health | 30s | Simple status badge |
| targets | 60s | Invalidate on create-target / start-run success |
| run | 3s | Poll via `refetchInterval` until terminal |
| findings | 5s | Refetch on window focus; also when run reaches terminal |

### Terminal run statuses (polling)

Codify explicitly so polling is deterministic:

```ts
export const TERMINAL_RUN_STATUSES = new Set([
  'completed',
  'failed',
  'error',
  'cancelled',
]);
```

`useRun` `refetchInterval`: return `false` when `data.status` is in `TERMINAL_RUN_STATUSES`, otherwise `3000`.

If the live API uses different terminal strings, update this set to match server values (document any mismatch in README).

### ApiClient

- `axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000', timeout: 15000 })`
- Helper `mapValidationErrorsToForm(err)` parses FastAPI 422 `detail[]` (`loc`, `msg`) into `{ [field]: message }` for `setError`

### Mutations

- **Create target:** `POST /targets` → invalidate `['targets']`; surface 422 to form
- **Start run:** `POST /runs` body `{ target_name, config? }` → response `RunRecord` with `run_id` → add to recent runs → toast with link + copy → navigate to `/runs/{run_id}`

### Recent runs (sessionStorage)

| Item | Value |
|------|--------|
| Key | `ait.recentRuns` |
| Shape | `Array<{ runId: string; startedAt: string; targetName?: string }>` |
| Cap | Last 10 entries |
| Lifecycle | Cleared when browser session ends |

Behavior:

1. On Start Run success: unshift `{ runId: data.run_id, startedAt: ISO, targetName }`; dedupe by `runId`; trim to 10
2. Dashboard: `useQueries` for each stored id with key `['run', runId]`
3. On **404**: remove that entry from storage
4. On **5xx / network**: keep entry; show “status unavailable”
5. Provide **Clear recent runs**

### Error UX

| Case | UI |
|------|-----|
| Network failure | Global banner with retry |
| 422 validation | Per-field errors on CreateTargetForm |
| Other 4xx/5xx | Toast / snackbar (“Server error — try again”) |

## CreateTargetForm behavior

### Visible fields

| Field | Required | Notes |
|-------|----------|--------|
| `name` | yes | string |
| `environment` | no | dropdown: `demo` / `sandbox` / `prod` (default `demo`) |
| `base_url` | yes | must include `http://` or `https://` |
| `integration_sync_url` | yes | auto-filled, editable |
| `audit_base_url` | yes | auto-filled, editable |

Helper text: “Auto-filled from base URL — edit if different.” Plus **Reset to default** for each auto-filled field.

### Pristine auto-fill rules

1. Track `integrationSyncPristine` and `auditBasePristine` (start `true`)
2. On `base_url` change / blur:
   - Validate/normalize with `new URL(value)` (reject missing protocol; show hint)
   - `normalizedBase = url.origin + url.pathname.replace(/\/+$/, '')` (or equivalent trailing-slash strip)
   - If sync pristine → `integration_sync_url = normalizedBase + '/sync'`
   - If audit pristine → `audit_base_url = normalizedBase` (trailing slash optional; prefer consistent with demo target style)
3. On user edit of sync/audit → set corresponding pristine to `false`
4. Reset control: restore default from current `base_url` and set pristine back to `true`
5. If `base_url` omitted/invalid, require sync/audit explicitly and show client errors

### Advanced section (collapsed by default)

Accessible accordion labeled **Advanced target settings (optional)**:

- `auth_type` — `static_token` | `oauth_client_credentials` (default `static_token`)
- `token_config.token_url`, `client_id`, `client_secret` (`type="password"` + optional show toggle; note: sent to API only, not stored in frontend)
- `openapi_paths`, `seed_endpoints`, `expected_endpoints` — multiline → string arrays
- `expected_scopes`, `sensitive_markers` — comma-separated → string arrays
- `description` — textarea

**POST payload rules:** omit empty optional/advanced fields. Always include required URLs.

### Validation

- Client: zod + `new URL()` for URL fields; required checks. On invalid submit, focus the first invalid field; mark fields with `aria-invalid` and visible helpers
- On submit failure (422): `mapValidationErrorsToForm` → `setError`; focus first invalid field

### Example minimal payload

```json
{
  "name": "demo-integration",
  "environment": "demo",
  "base_url": "http://127.0.0.1:8001/",
  "integration_sync_url": "http://127.0.0.1:8001/sync",
  "audit_base_url": "http://127.0.0.1:8001/",
  "description": "Created from minimal frontend"
}
```

## StartRunButton behavior

1. Confirm modal: “Start run for target `{name}`?”
2. `POST /runs` with `{ target_name: name }`
3. On success:
   - `useRecentRuns.add({ runId: data.run_id, startedAt, targetName })`
   - Toast: “Run started: `{run_id}`” with link to `/runs/{run_id}` and Copy run id
   - Navigate to `/runs/{run_id}`

## Demo-mode behavior

| Source | Behavior |
|--------|----------|
| `VITE_DEMO_MODE` | Build-time default (`false`) |
| UI toggle | Persists boolean in `localStorage` key `ait.demoMode` |
| Effective mode | UI override if set; else env default |

When effective demo mode is **true**, RunDetail shows a developer-only panel:

- Warning: “Developer demo-only control — do not use in production.”
- Button/link: `http://localhost:8001/admin/audit/{run_id}` (new tab)
- Hidden entirely when demo mode is off

## Testing matrix

### Unit (required, CI)

1. **Pristine auto-fill** — changing `base_url` fills sync/audit; after user edit, further `base_url` changes do not overwrite; Reset restores defaults
2. **StartRunButton** — confirm → mutation called with `{ target_name }`; on success calls `recentRuns.add` with `run_id`

### E2E (optional, not in default CI)

Playwright flow documented in README:

1. Start coordinator (`:8000`), mock SaaS (`:8001`), demo integration (`:8002`)
2. Open frontend, create target (or use seed `demo-integration`)
3. Start run, wait for terminal status, open report HTML and assert expected content

### CI

Minimal GitHub Actions job (optional but recommended):

- `working-directory: frontend`
- `npm ci`
- `npm test`

Do **not** run Playwright in default CI unless services are orchestrated.

## Dev notes (README must document)

### Local services

```bash
# from repo root (venv activated, package installed)
uvicorn ait.mock_saas:app --port 8001 --reload
uvicorn ait.demo_integration:app --port 8002 --reload
uvicorn ait.api:app --port 8000 --reload
```

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

### `.env.example`

```
VITE_API_BASE_URL=http://localhost:8000
VITE_DEMO_MODE=false
```

### Contracts to document

- sessionStorage key: `ait.recentRuns`
- localStorage key: `ait.demoMode`
- Terminal statuses used for polling
- Report URL pattern: `{VITE_API_BASE_URL}/runs/{run_id}/report?format=html`

### `.gitignore` (frontend)

Include at least: `node_modules/`, `dist/`, `.env`, `coverage/`, Playwright artifacts if present.

## Out of scope (v1)

- Backend `GET /runs` list endpoint
- Auth / multi-user sessions
- Tailwind / design system
- Editing or deleting existing targets via UI
- Configuring mock SaaS base URL beyond hardcoded `:8001` (may follow later)

## Acceptance criteria

1. SPA runs locally and talks to coordinator via `VITE_API_BASE_URL`
2. List targets; create target with hybrid auto-fill + editable sync/audit URLs
3. Advanced accordion fields included only when non-empty; POST succeeds
4. Start run → navigate to Run Detail; recent run appears on Dashboard for this session
5. Run Detail shows findings (when present); Open report opens HTML report
6. Demo-mode toggle/env shows/hides audit link
7. Open run by ID works for pasted `run_id`
8. At least one unit test passes; `npm run test` succeeds
9. README documents setup, env vars, ports, storage keys, and optional E2E

## Implementation notes for implementers

- Prefer TanStack Query v5 API (`queryKey` / `queryFn` object form) when scaffolding
- Match FastAPI field names exactly (`run_id`, `base_url`, snake_case throughout)
- Keep styling utilitarian; prioritize clarity and a11y over polish
- Do not add secrets to git; `client_secret` is form-only, sent to API
`)
