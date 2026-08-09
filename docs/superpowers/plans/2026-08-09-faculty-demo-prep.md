# Faculty Demo Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overnight, make a UI-first faculty demo: SPA mock path + Live evidence page + paste-token live probe against GitHub/Google.

**Architecture:** Branch from `feature/frontend-spa`. Add demo-gated `POST /live/probes` and `GET /live/evidence` on the coordinator; add SPA `/live` page with evidence table and masked token form. Token is request-scoped only (override into `execute_live_plan`), never stored in browser storage or server logs.

**Tech Stack:** FastAPI, existing `ait.live_runner`, Vite React SPA, Vitest, pytest.

## Global Constraints

- Demo live endpoints require `AIT_DEMO_LIVE_PROBES=1` and Host `localhost`/`127.0.0.1`.
- Plan files allowlisted to `configs/live/{github,google}_{smoke,readonly}.yaml` only (Notion optional later).
- Token never in `localStorage` / `sessionStorage`; clear input after submit settles.
- Do not commit real tokens. Use sandbox tokens only during rehearsal.
- Prefer TDD for backend probe endpoint and frontend form helpers.

---

### Task 1: Branch from frontend SPA and verify baseline

**Files:**
- None created yet (git / smoke check only)

**Interfaces:**
- Consumes: `origin/feature/frontend-spa`
- Produces: local branch `feature/faculty-demo` with SPA + CORS coordinator

- [ ] **Step 1: Create branch from SPA tip**

```bash
cd /home/loki/projects/major_project
git fetch origin
git checkout -b feature/faculty-demo origin/feature/frontend-spa
```

Expected: on `feature/faculty-demo`, `frontend/` present.

- [ ] **Step 2: Install frontend deps and run unit tests**

```bash
cd frontend && npm ci && npm test && npm run build
```

Expected: tests pass; build succeeds.

- [ ] **Step 3: Confirm live artifacts exist (copy from research branch if missing)**

```bash
ls results/derived/live_*.json | wc -l
# If fewer than 5 selected runs, checkout files from research-phases:
# git checkout origin/feature/research-phases -- results/derived/live_*.json results/raw/live
```

Expected: at least the five paper-selected derived live JSONs present.

- [ ] **Step 4: Commit nothing yet** (branch only)

---

### Task 2: Token override on `execute_live_plan`

**Files:**
- Modify: `ait/live_runner.py` (`execute_live_plan`)
- Test: `tests/test_live_runner.py`

**Interfaces:**
- Consumes: existing `execute_live_plan(plan, ...)`
- Produces: `execute_live_plan(..., token: str | None = None)` — when `token` is provided, use it instead of `_read_token(plan)`; still scrub via `secrets = [token]`

- [ ] **Step 1: Write failing test**

Add to `tests/test_live_runner.py` a test that:
- builds a minimal plan using existing fixtures / MockTransport patterns in that file
- calls `execute_live_plan(..., token="override-secret")` without setting `plan.token_env` in the environment
- asserts the outbound provider auth header used `override-secret`
- asserts the env var was not required

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_live_runner.py -k token_override -v
```

Expected: FAIL (unexpected keyword `token` or missing credentials).

- [ ] **Step 3: Implement minimal override**

In `execute_live_plan`, add `token: str | None = None`. When `token` is `None`, keep `_read_token(plan)`. When set, reject blank strings with `MissingCredentialsError` and use the override; set `secrets = [token]`. Do not write into `os.environ`.

- [ ] **Step 4: Re-run test**

```bash
uv run pytest tests/test_live_runner.py -k token_override -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ait/live_runner.py tests/test_live_runner.py
git commit -m "$(cat <<'EOF'
feat: allow in-memory token override for live probes

EOF
)"
```

---

### Task 3: Demo-gated live probe + evidence API

**Files:**
- Create: `ait/live_api.py` (request/response models + helpers)
- Modify: `ait/api.py` (mount routes; keep CORS from SPA branch)
- Create: `tests/test_live_api.py`

**Interfaces:**
- Consumes: `execute_live_plan`, `load_live_plan`, allowlisted plan paths
- Produces:
  - `GET /live/evidence` → list of summary rows from `results/derived/live_*.json`
  - `POST /live/probes` body `{provider, plan, token}` → redacted summary

Allowlist:

```python
PLAN_FILES = {
    ("github", "smoke"): Path("configs/live/github_smoke.yaml"),
    ("github", "readonly"): Path("configs/live/github_readonly.yaml"),
    ("github", "smoke-extended"): Path("configs/live/github_smoke_extended.yaml"),
    ("google", "smoke"): Path("configs/live/google_smoke.yaml"),
    ("google", "readonly"): Path("configs/live/google_readonly.yaml"),
    ("google", "smoke-extended"): Path("configs/live/google_smoke_extended.yaml"),
}
```

Gate: `AIT_DEMO_LIVE_PROBES=1` and Host host-part in `{localhost, 127.0.0.1}`. If disabled, return **404** (do not advertise the endpoint).

- [ ] **Step 1: Write failing tests** for disabled gate, unknown plan (422), evidence listing from fixture root, and happy-path probe with `execute_live_plan` monkeypatched (no real network).

- [ ] **Step 2: Run tests — expect fail**

```bash
uv run pytest tests/test_live_api.py -v
```

- [ ] **Step 3: Implement `ait/live_api.py` and wire routes in `ait/api.py`**

- `POST /live/probes`: validate body; resolve allowlisted plan; `await execute_live_plan(plan, token=body.token, output_root=Path("results"), ...)`; return summary; scrub token from errors.
- `GET /live/evidence`: read `results/derived/live_*.json` into Platform / Scenario / Risk / Result rows.

- [ ] **Step 4: Tests pass**

```bash
uv run pytest tests/test_live_api.py tests/test_live_runner.py -v
```

- [ ] **Step 5: Commit**

```bash
git add ait/live_api.py ait/api.py tests/test_live_api.py
git commit -m "$(cat <<'EOF'
feat: demo-gated live evidence and paste-token probe API

EOF
)"
```

---

### Task 4: SPA Live page — evidence table

**Files:**
- Create: `frontend/src/pages/Live.tsx`
- Modify: `frontend/src/App.tsx` (nav + route `/live`)
- Modify: `frontend/src/components/ApiClient.ts`, `useApiHooks.ts`, `types/api.ts`
- Modify: `frontend/vite.config.ts` — proxy `/live`
- Test: `frontend/src/test/LiveEvidence.test.tsx`

**Interfaces:**
- Consumes: `GET /live/evidence`
- Produces: table columns Platform | Scenario | Risk | Result; row detail for findings

- [ ] **Step 1: Add types, client method, failing table test**
- [ ] **Step 2: Implement `/live` page + nav link**
- [ ] **Step 3: `npm test` passes**
- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "$(cat <<'EOF'
feat: add Live evidence page to SPA

EOF
)"
```

---

### Task 5: SPA paste-token probe form

**Files:**
- Create: `frontend/src/components/LiveProbeForm.tsx`
- Modify: `frontend/src/pages/Live.tsx`
- Test: `frontend/src/test/LiveProbeForm.test.tsx`

**Interfaces:**
- Consumes: `POST /live/probes`
- Produces: provider/plan/token form + result panel; clears token after settle

- [ ] **Step 1: Failing tests** — submit calls API; password cleared after success; no token in `sessionStorage`/`localStorage`
- [ ] **Step 2: Implement form** (`provider`: github|google, `plan`: smoke|readonly, masked `token`)
- [ ] **Step 3: Result panel** — risk, hidden endpoints, findings
- [ ] **Step 4: `npm test` && `npm run build`**
- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "$(cat <<'EOF'
feat: add paste-token live probe form to Live page

EOF
)"
```

---

### Task 6: Rehearsal runbook + dry run

**Files:**
- Create: `docs/superpowers/plans/2026-08-09-faculty-demo-runbook.md`

- [ ] **Step 1: Write runbook** with start commands:

```bash
export AIT_DEMO_LIVE_PROBES=1
uv run uvicorn ait.mock_saas:app --port 8001 --reload
uv run uvicorn ait.demo_integration:app --port 8002 --reload
uv run uvicorn ait.api:app --port 8000 --reload
cd frontend && npm run dev
```

Include Act 1 click path, Act 2 paste-token path, backup (evidence-only), kill rule (no OAuth debug >60s).

- [ ] **Step 2: Full dry run once** (mock + one real smoke via UI)
- [ ] **Step 3: Commit runbook**

```bash
git add docs/superpowers/plans/2026-08-09-faculty-demo-runbook.md
git commit -m "$(cat <<'EOF'
docs: faculty demo rehearsal runbook

EOF
)"
```

---

## Overnight schedule

| Window | Focus |
|---|---|
| 0–1h | Tasks 1–2 |
| 1–2.5h | Task 3 |
| 2.5–4h | Tasks 4–5 |
| 4–4.75h | Task 6 rehearsal |
| Buffer | Fix only; no new features |

## Spec coverage

| Spec item | Task |
|---|---|
| SPA mock Act 1 | Task 1 (existing SPA) |
| Live evidence table | Tasks 3–4 |
| Paste-token probe UI | Task 5 |
| Demo-gated API + token override | Tasks 2–3 |
| Backups / rehearsal | Task 6 |
| No browser token storage | Task 5 tests |
