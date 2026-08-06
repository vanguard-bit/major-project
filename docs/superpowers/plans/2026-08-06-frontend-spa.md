# Minimal Frontend SPA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Vite + React 18 + TypeScript SPA under `frontend/` that lists/creates targets, starts runs, shows run status/findings/report, and supports sessionStorage recent runs plus demo-mode audit links against the coordinator API.

**Architecture:** Spec-exact SPA (Approach 1). Axios client + TanStack Query for server state; react-hook-form + zod for Create Target; react-router for `/`, `/targets`, `/runs/:id`. No `GET /runs` — recent runs live in `sessionStorage`. Absolute `VITE_API_BASE_URL` by default; coordinator gets minimal CORS so the browser can call `:8000`.

**Tech Stack:** Vite, React 18, TypeScript, react-router-dom, axios, @tanstack/react-query v5, react-hook-form, zod, @hookform/resolvers, Vitest, React Testing Library, basic CSS.

**Spec:** `docs/superpowers/specs/2026-08-06-frontend-spa-design.md`

## Global Constraints

- Field names match FastAPI / Pydantic snake_case (`run_id`, `base_url`, `integration_sync_url`, …).
- `auth_type` is only `"static_token" | "oauth_client_credentials"` (default `static_token`).
- Query keys: `['health']`, `['targets']`, `['run', runId]`, `['findings', runId]`.
- sessionStorage key `ait.recentRuns`; localStorage key `ait.demoMode`.
- Terminal statuses: `completed`, `failed`, `error`, `cancelled`.
- Do not proxy Vite `'/'`; path-proxy is optional; default is absolute `VITE_API_BASE_URL`.
- No Tailwind; utilitarian CSS only.
- Playwright E2E is documented only — not required in CI.

---

## File structure (create)

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
    main.tsx
    App.tsx
    vite-env.d.ts
    types/api.ts
    components/ApiClient.ts
    components/useApiHooks.ts
    components/CreateTargetForm.tsx
    components/StartRunButton.tsx
    components/RecentRuns.tsx
    components/DemoModeToggle.tsx
    hooks/useRecentRuns.ts
    hooks/useDemoMode.ts
    lib/createTargetDefaults.ts
    lib/mapValidationErrors.ts
    pages/Dashboard.tsx
    pages/Targets.tsx
    pages/RunDetail.tsx
    styles/index.css
    test/setup.ts
    test/createTargetDefaults.test.ts
    test/StartRunButton.test.tsx
    test/mapValidationErrors.test.ts
ait/api.py                          # minimal CORSMiddleware addition
.github/workflows/frontend.yml      # npm ci + test + build
```

---

### Task 1: Scaffold `frontend/` + API types + CORS on coordinator

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/.env.example`, `frontend/.gitignore`, `frontend/src/vite-env.d.ts`, `frontend/src/types/api.ts`, `frontend/src/styles/index.css`, `frontend/src/test/setup.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx` (stub)
- Modify: `ait/api.py` (add CORSMiddleware)

**Interfaces:**
- Produces: `TargetConfig`, `RunRecord`, `Finding`, `TERMINAL_RUN_STATUSES` in `src/types/api.ts`
- Produces: Vite app that boots with a placeholder page

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "ait-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@hookform/resolvers": "^3.9.0",
    "@tanstack/react-query": "^5.59.0",
    "axios": "^1.7.7",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-hook-form": "^7.53.0",
    "react-router-dom": "^6.26.2",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.0",
    "typescript": "^5.5.4",
    "vite": "^5.4.3",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2: Add Vite / TS config files**

`frontend/vite.config.ts`:

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
      '/targets': { target: 'http://localhost:8000', changeOrigin: true },
      '/runs': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
});
```

`frontend/tsconfig.json` — standard Vite React TS config with `"strict": true`, include `src`.  
`frontend/tsconfig.node.json` — for `vite.config.ts`.  
`frontend/index.html` — root div `#root`, script `/src/main.tsx`.  
`frontend/.env.example`:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_DEMO_MODE=false
```

`frontend/.gitignore`: `node_modules/`, `dist/`, `.env`, `coverage/`.

`frontend/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

`frontend/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 3: Add `frontend/src/types/api.ts`**

Copy the interfaces from the design spec (`AuthType`, `TokenConfig`, `TargetConfig`, `TestRunConfig`, `Finding`, `RunReport`, `RunRecord`) and add:

```ts
export const TERMINAL_RUN_STATUSES = new Set([
  'completed',
  'failed',
  'error',
  'cancelled',
]);

export type RecentRunEntry = {
  runId: string;
  startedAt: string;
  targetName?: string;
};
```

- [ ] **Step 4: Stub `main.tsx` / `App.tsx` + minimal CSS**

`main.tsx`: mount `<App />` with `QueryClientProvider` + `BrowserRouter`.  
`App.tsx`: nav links + `<Routes>` with a single home stub “AIT Frontend”.  
`styles/index.css`: reset-ish body font, nav, tables, forms, modal, accordion, banners (utilitarian).

- [ ] **Step 5: Enable CORS on coordinator**

In `ait/api.py`, after creating `app`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 6: Install and verify boot**

```bash
cd frontend
npm install
npm run build
```

Expected: build succeeds (stub app).

- [ ] **Step 7: Commit**

```bash
git add frontend ait/api.py
git commit -m "scaffold: Vite React frontend and coordinator CORS for local SPA"
```

---

### Task 2: Validation error mapper + ApiClient

**Files:**
- Create: `frontend/src/lib/mapValidationErrors.ts`, `frontend/src/components/ApiClient.ts`, `frontend/src/test/mapValidationErrors.test.ts`

**Interfaces:**
- Produces: `api` axios instance; `mapValidationErrorsToForm(err: unknown): Record<string, string>`
- Produces: `getApiBaseUrl(): string`

- [ ] **Step 1: Write failing test**

`frontend/src/test/mapValidationErrors.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { mapValidationErrorsToForm } from '../lib/mapValidationErrors';

describe('mapValidationErrorsToForm', () => {
  it('maps FastAPI 422 loc leaf to field name', () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ['body', 'base_url'], msg: 'invalid url', type: 'value_error' },
            { loc: ['body', 'token_config', 'client_id'], msg: 'required', type: 'missing' },
          ],
        },
      },
    };
    expect(mapValidationErrorsToForm(err)).toEqual({
      base_url: 'invalid url',
      client_id: 'required',
    });
  });

  it('returns empty object when detail missing', () => {
    expect(mapValidationErrorsToForm({})).toEqual({});
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd frontend && npm run test -- src/test/mapValidationErrors.test.ts
```

Expected: FAIL (module not found).

- [ ] **Step 3: Implement mapper + ApiClient**

`frontend/src/lib/mapValidationErrors.ts`:

```ts
export function mapValidationErrorsToForm(err: unknown): Record<string, string> {
  const result: Record<string, string> = {};
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (!Array.isArray(detail)) return result;
  for (const item of detail) {
    const loc = (item as { loc?: unknown[]; msg?: string }).loc;
    const msg = (item as { msg?: string }).msg ?? 'Invalid';
    if (!Array.isArray(loc) || loc.length === 0) {
      result.non_field = msg;
      continue;
    }
    const strings = loc.filter((p): p is string => typeof p === 'string');
    const leaf = strings[strings.length - 1] ?? 'non_field';
    result[leaf] = msg;
  }
  return result;
}
```

`frontend/src/components/ApiClient.ts`:

```ts
import axios from 'axios';

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
}

export const api = axios.create({
  baseURL: getApiBaseUrl(),
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
});

export { mapValidationErrorsToForm } from '../lib/mapValidationErrors';
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd frontend && npm run test -- src/test/mapValidationErrors.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/mapValidationErrors.ts frontend/src/components/ApiClient.ts frontend/src/test/mapValidationErrors.test.ts
git commit -m "feat: add axios ApiClient and FastAPI 422 form error mapper"
```

---

### Task 3: `createTargetDefaults` pristine helpers (TDD)

**Files:**
- Create: `frontend/src/lib/createTargetDefaults.ts`, `frontend/src/test/createTargetDefaults.test.ts`

**Interfaces:**
- Produces: `normalizeBaseUrl(baseUrl: string): string` (throws / returns null on invalid)
- Produces: `defaultsFromBaseUrl(baseUrl: string): { integration_sync_url: string; audit_base_url: string } | null`

- [ ] **Step 1: Write failing test**

```ts
import { describe, it, expect } from 'vitest';
import { defaultsFromBaseUrl, normalizeBaseUrl } from '../lib/createTargetDefaults';

describe('createTargetDefaults', () => {
  it('normalizes trailing slash and builds sync/audit defaults', () => {
    expect(normalizeBaseUrl('http://127.0.0.1:8001/')).toBe('http://127.0.0.1:8001');
    expect(defaultsFromBaseUrl('http://127.0.0.1:8001/')).toEqual({
      integration_sync_url: 'http://127.0.0.1:8001/sync',
      audit_base_url: 'http://127.0.0.1:8001',
    });
  });

  it('returns null for missing protocol', () => {
    expect(defaultsFromBaseUrl('example.test')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd frontend && npm run test -- src/test/createTargetDefaults.test.ts
```

- [ ] **Step 3: Implement**

```ts
export function normalizeBaseUrl(baseUrl: string): string | null {
  try {
    const url = new URL(baseUrl);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    const path = url.pathname.replace(/\/+$/, '');
    return `${url.origin}${path === '/' ? '' : path}`;
  } catch {
    return null;
  }
}

export function defaultsFromBaseUrl(
  baseUrl: string,
): { integration_sync_url: string; audit_base_url: string } | null {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) return null;
  return {
    integration_sync_url: `${normalized}/sync`,
    audit_base_url: normalized,
  };
}
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd frontend && npm run test -- src/test/createTargetDefaults.test.ts
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/createTargetDefaults.ts frontend/src/test/createTargetDefaults.test.ts
git commit -m "feat: add create-target URL default helpers with unit tests"
```

---

### Task 4: `useRecentRuns` + `useDemoMode`

**Files:**
- Create: `frontend/src/hooks/useRecentRuns.ts`, `frontend/src/hooks/useDemoMode.ts`
- Test: extend with a small unit test for recent-runs list logic if extracted; otherwise exercise via StartRunButton later

**Interfaces:**
- Produces: `useRecentRuns()` → `{ entries, add, remove, clear, setEntries }`
- Produces: `useDemoMode()` → `{ enabled: boolean; setEnabled: (v: boolean) => void }`

- [ ] **Step 1: Implement `useRecentRuns`**

```ts
import { useCallback, useState } from 'react';
import type { RecentRunEntry } from '../types/api';

const KEY = 'ait.recentRuns';
const CAP = 10;

function read(): RecentRunEntry[] {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as RecentRunEntry[]) : [];
  } catch {
    return [];
  }
}

function write(list: RecentRunEntry[]) {
  sessionStorage.setItem(KEY, JSON.stringify(list));
}

export function useRecentRuns() {
  const [entries, setEntriesState] = useState<RecentRunEntry[]>(() => read());

  const setEntries = useCallback((list: RecentRunEntry[]) => {
    write(list);
    setEntriesState(list);
  }, []);

  const add = useCallback((entry: RecentRunEntry) => {
    const next = [entry, ...read().filter((r) => r.runId !== entry.runId)].slice(0, CAP);
    write(next);
    setEntriesState(next);
  }, []);

  const remove = useCallback((runId: string) => {
    const next = read().filter((r) => r.runId !== runId);
    write(next);
    setEntriesState(next);
  }, []);

  const clear = useCallback(() => {
    write([]);
    setEntriesState([]);
  }, []);

  return { entries, add, remove, clear, setEntries };
}
```

- [ ] **Step 2: Implement `useDemoMode`**

```ts
import { useCallback, useState } from 'react';

const KEY = 'ait.demoMode';

function envDefault(): boolean {
  return String(import.meta.env.VITE_DEMO_MODE ?? 'false').toLowerCase() === 'true';
}

function read(): boolean {
  const stored = localStorage.getItem(KEY);
  if (stored === null) return envDefault();
  return stored === 'true';
}

export function useDemoMode() {
  const [enabled, setEnabledState] = useState<boolean>(() => read());

  const setEnabled = useCallback((value: boolean) => {
    localStorage.setItem(KEY, String(value));
    setEnabledState(value);
  }, []);

  return { enabled, setEnabled };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useRecentRuns.ts frontend/src/hooks/useDemoMode.ts
git commit -m "feat: add recent-runs sessionStorage and demo-mode hooks"
```

---

### Task 5: React Query API hooks

**Files:**
- Create: `frontend/src/components/useApiHooks.ts`

**Interfaces:**
- Consumes: `api` from `ApiClient`; `TERMINAL_RUN_STATUSES` from types
- Produces: `useHealth`, `useTargets`, `useCreateTarget`, `useStartRun`, `useRun`, `useFindings`

- [ ] **Step 1: Implement hooks (TanStack Query v5 object form)**

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './ApiClient';
import type { Finding, RunRecord, TargetConfig } from '../types/api';
import { TERMINAL_RUN_STATUSES } from '../types/api';

const POLL_MS = 3000;
const MAX_POLL_MS = 5 * 60 * 1000;

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get('/health').then((r) => r.data as { status: string }),
    staleTime: 30_000,
  });
}

export function useTargets() {
  return useQuery({
    queryKey: ['targets'],
    queryFn: () => api.get('/targets').then((r) => r.data as TargetConfig[]),
    staleTime: 60_000,
  });
}

export function useCreateTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: TargetConfig) =>
      api.post('/targets', payload).then((r) => r.data as TargetConfig),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['targets'] }),
  });
}

export function useStartRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { target_name: string; config?: Record<string, unknown> }) =>
      api.post('/runs', payload).then((r) => r.data as RunRecord),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['targets'] }),
  });
}

export function useRun(runId: string, enabled = true) {
  const pollStartedAt = useRef(Date.now());
  return useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.get(`/runs/${runId}`).then((r) => r.data as RunRecord),
    enabled: enabled && !!runId,
    staleTime: 3000,
    retry: 2,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && TERMINAL_RUN_STATUSES.has(data.status)) return false;
      const elapsed = Date.now() - pollStartedAt.current;
      if (elapsed > MAX_POLL_MS) return false;
      if (query.state.fetchFailureCount >= 5) return 30_000;
      return POLL_MS;
    },
  });
}

export function useFindings(runId: string) {
  return useQuery({
    queryKey: ['findings', runId],
    queryFn: () => api.get(`/runs/${runId}/findings`).then((r) => r.data as Finding[]),
    enabled: !!runId,
    staleTime: 5000,
  });
}
```

Implement `pollStartedAt` with `useRef(Date.now())` inside `useRun` (import `useRef` from React).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/useApiHooks.ts
git commit -m "feat: add TanStack Query hooks for health, targets, runs, findings"
```

---

### Task 6: `StartRunButton` (TDD)

**Files:**
- Create: `frontend/src/components/StartRunButton.tsx`, `frontend/src/test/StartRunButton.test.tsx`

**Interfaces:**
- Consumes: `useStartRun`, `useRecentRuns.add`
- Props: `{ targetName: string }`

- [ ] **Step 1: Write failing test**

Mock `useStartRun` and navigate. Assert confirm → mutate called with `{ target_name: 'demo-integration' }` and `add` called with `run_id` from response.

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { StartRunButton } from '../components/StartRunButton';

const mutateAsync = vi.fn();
const add = vi.fn();

vi.mock('../components/useApiHooks', () => ({
  useStartRun: () => ({ mutateAsync, isPending: false }),
}));

vi.mock('../hooks/useRecentRuns', () => ({
  useRecentRuns: () => ({ add, entries: [], remove: vi.fn(), clear: vi.fn() }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

describe('StartRunButton', () => {
  beforeEach(() => {
    mutateAsync.mockReset();
    add.mockReset();
    mutateAsync.mockResolvedValue({
      run_id: 'run-123',
      status: 'completed',
      target: { name: 'demo-integration' },
      config: {},
      findings: [],
      exchanges: [],
    });
  });

  it('starts a run after confirm and records recent run', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <StartRunButton targetName="demo-integration" />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole('button', { name: /start run/i }));
    await user.click(screen.getByRole('button', { name: /confirm/i }));
    expect(mutateAsync).toHaveBeenCalledWith({ target_name: 'demo-integration' });
    expect(add).toHaveBeenCalledWith(
      expect.objectContaining({ runId: 'run-123', targetName: 'demo-integration' }),
    );
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd frontend && npm run test -- src/test/StartRunButton.test.tsx
```

- [ ] **Step 3: Implement `StartRunButton`**

Confirm modal; on confirm `await mutateAsync({ target_name })`; `add({ runId: data.run_id, startedAt: new Date().toISOString(), targetName })`; simple alert/toast text with run id; `navigate(`/runs/${data.run_id}`)`.

- [ ] **Step 4: Run test — expect PASS**

```bash
cd frontend && npm run test -- src/test/StartRunButton.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StartRunButton.tsx frontend/src/test/StartRunButton.test.tsx
git commit -m "feat: add StartRunButton with confirm modal and unit test"
```

---

### Task 7: `CreateTargetForm`

**Files:**
- Create: `frontend/src/components/CreateTargetForm.tsx`

**Interfaces:**
- Consumes: `useCreateTarget`, `defaultsFromBaseUrl`, `mapValidationErrorsToForm`
- Produces: form that POSTs `TargetConfig` and invalidates targets list

- [ ] **Step 1: Implement form with zod schema**

Visible: `name`, `environment` (`demo|sandbox|prod`), `base_url`, `integration_sync_url`, `audit_base_url`.  
Pristine booleans in `useState`; on `base_url` change apply defaults when pristine; Reset buttons.  
Advanced accordion: auth_type, token fields, multiline path lists, comma lists, description.  
On submit: build payload omitting empty advanced fields; on 422 map errors via `setError`. Focus first invalid field.

- [ ] **Step 2: Manual smoke (optional)** — `npm run dev` with coordinator up; create a target.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CreateTargetForm.tsx
git commit -m "feat: add CreateTargetForm with hybrid auto-fill and advanced accordion"
```

---

### Task 8: Shared UI pieces — `RecentRuns`, `DemoModeToggle`

**Files:**
- Create: `frontend/src/components/RecentRuns.tsx`, `frontend/src/components/DemoModeToggle.tsx`

**Interfaces:**
- `RecentRuns`: uses `useRecentRuns` + `useQueries` for `['run', id]`; prune 404; clear button; links to `/runs/:id`
- `DemoModeToggle`: checkbox bound to `useDemoMode`

- [ ] **Step 1: Implement both components**

For 404 pruning: in `useQueries` `select`/`useEffect`, when `error.response?.status === 404`, call `remove(runId)`.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/RecentRuns.tsx frontend/src/components/DemoModeToggle.tsx
git commit -m "feat: add RecentRuns panel and DemoModeToggle"
```

---

### Task 9: Pages — Dashboard, Targets, RunDetail + wire `App.tsx`

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Targets.tsx`, `frontend/src/pages/RunDetail.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/styles/index.css`

**Interfaces:**
- Routes as in spec
- RunDetail: Open report via `window.open(`${getApiBaseUrl()}/runs/${id}/report?format=html`, '_blank')`
- Demo audit link only when `useDemoMode().enabled`

- [ ] **Step 1: Implement Dashboard**

Health badge; Open run by ID form; `RecentRuns`; targets preview linking to `/targets`; `DemoModeToggle`.

- [ ] **Step 2: Implement Targets**

`useTargets` table + `CreateTargetForm` + `StartRunButton` per row.

- [ ] **Step 3: Implement RunDetail**

`useParams().id` → `useRun` + `useFindings`; status; last-updated; findings table (`severity`, `category`, `endpoint`, `title`); Open report; demo panel with warning + audit URL.

Show “Still waiting — refresh manually” when polling stopped due to max duration / failures and status still non-terminal.

- [ ] **Step 4: Wire routes in `App.tsx`**

```tsx
<Routes>
  <Route path="/" element={<Dashboard />} />
  <Route path="/targets" element={<Targets />} />
  <Route path="/runs/:id" element={<RunDetail />} />
</Routes>
```

- [ ] **Step 5: Verify**

```bash
cd frontend && npm run test && npm run build
```

Expected: all tests pass; build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages frontend/src/App.tsx frontend/src/styles/index.css
git commit -m "feat: wire Dashboard, Targets, and RunDetail pages"
```

---

### Task 10: README + CI workflow

**Files:**
- Create: `frontend/README.md`, `.github/workflows/frontend.yml`

- [ ] **Step 1: Write `frontend/README.md`**

Document:

- `npm install` / `npm run dev` / `npm run build` / `npm run test`
- Env vars `VITE_API_BASE_URL`, `VITE_DEMO_MODE`
- Ports: coordinator 8000, mock SaaS 8001, demo integration 8002, Vite 5173
- sessionStorage `ait.recentRuns`, localStorage `ait.demoMode`
- CORS / proxy note
- Optional Playwright E2E outline (not automated in CI)
- How to open HTML report URL pattern

- [ ] **Step 2: Add GitHub Actions**

`.github/workflows/frontend.yml`:

```yaml
name: Frontend
on:
  push:
    paths: ['frontend/**', '.github/workflows/frontend.yml']
  pull_request:
    paths: ['frontend/**', '.github/workflows/frontend.yml']
jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm test
      - run: npm run build
```

- [ ] **Step 3: Ensure lockfile exists**

```bash
cd frontend && npm install
```

Commit `package-lock.json`.

- [ ] **Step 4: Final verification**

```bash
cd frontend && npm test && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/README.md frontend/package-lock.json .github/workflows/frontend.yml
git commit -m "docs: frontend README and CI for test + build"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Vite React TS scaffold + scripts | 1, 10 |
| Types from models | 1 |
| ApiClient + 422 leaf mapping | 2 |
| Hybrid create form + pristine + advanced | 3, 7 |
| Recent runs sessionStorage | 4, 8 |
| Demo mode env + localStorage | 4, 8, 9 |
| Query hooks + polling + backoff | 5 |
| Start run confirm + navigate | 6 |
| Dashboard / Targets / RunDetail | 9 |
| Open report + Open by ID | 9 |
| Unit tests | 2, 3, 6 |
| README + CI test/build | 10 |
| CORS for absolute base URL | 1 |

## Self-review notes

- No `GET /runs` invented.
- `run_id` used everywhere (not `id`).
- Proxy does not steal `'/'`.
- Playwright left out of CI per spec.
