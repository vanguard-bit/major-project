# Phase 3: Safe Live SaaS Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development. Execute only this file after Phase 1 passes. Real live execution requires explicit sandbox credentials.

**Goal:** Produce genuine, redacted GitHub and Notion sandbox observations using a safety-constrained live probe runner.

**Architecture:** Provider-neutral probe plans define allowed hosts, methods, paths, and policy expectations. A guarded HTTP client validates every request before transmission, records normalized exchanges, redacts credentials and payload secrets, and feeds observations into the existing analyzer. Provider files supply headers and sandbox plans; they do not duplicate transport logic.

**Tech Stack:** HTTPX, Pydantic 2, pytest, respx or HTTPX MockTransport, Typer.

## Scientific Scope

This runner measures whether requests made by AIT’s explicit live probe exceed a declared endpoint policy and whether provider responses expose configured fields. It does **not** passively observe arbitrary third-party integrations unless they use this client. Phase 6 must describe it as an instrumented live probe, not a transparent integration monitor.

## Safety Constraints

- Default allowed methods are `GET` and `HEAD`.
- Mutating methods require both `--allow-mutation` and `environment: sandbox`.
- Redirects are disabled. A redirect is recorded and rejected, not followed.
- Every absolute and redirected host must exactly match an allowlisted host.
- Maximum requests per run: 20.
- Maximum response bytes per request: 1 MiB.
- Default timeout: 10 seconds.
- Retry only `429`, `502`, `503`, and `504`, at most twice, respecting `Retry-After` up to 30 seconds.
- Tokens are read from named environment variables and are never accepted as CLI arguments.
- Raw bodies are disabled by default. Store extracted field names, status, selected safe headers, SHA-256 body digest, and byte length. `--store-bodies` may be used only with synthetic sandbox data.
- The response-header allowlist is exactly `content-type`, `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`, `retry-after`, and provider request IDs. Never store `set-cookie`, `cookie`, or authorization headers.
- If credentials are missing, exit with status `2` and write no result row.

## File Map

- Create `ait/live_runner.py`: models, safety guard, execution, CLI.
- Create `ait/providers/__init__.py`.
- Create `ait/providers/github.py`: GitHub headers and plans.
- Create `ait/providers/notion.py`: Notion headers and plans.
- Create `configs/live/github_readonly.yaml`.
- Create `configs/live/github_smoke.yaml`.
- Create `configs/live/notion_readonly.yaml`.
- Create `tests/test_live_runner.py`.
- Create `tests/providers/test_github.py`.
- Create `tests/providers/test_notion.py`.
- Modify `.gitignore` if present; otherwise create it to exclude `.env`, `results/raw/live-private/`, and local token files.
- Modify `README.md`: sandbox setup and safety warnings.

## Public Interfaces

```python
class LiveRequestSpec(BaseModel):
    method: Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    phase: Literal["baseline", "mutated"] = "baseline"
    json_body: dict[str, Any] | None = None

class LivePlan(BaseModel):
    schema_version: Literal["1.0.0"]
    id: str
    provider: Literal["github", "notion"]
    environment: Literal["sandbox", "production-readonly"]
    base_url: HttpUrl
    allowed_hosts: set[str]
    token_env: str
    expected_endpoints: list[str]
    sensitive_markers: list[str]
    requests: list[LiveRequestSpec]

class LiveObservation(BaseModel):
    request_index: int
    method: str
    normalized_path: str
    status_code: int
    response_bytes: int
    response_sha256: str
    response_fields: list[str]
    selected_headers: dict[str, str]
    elapsed_ms: float

def load_live_plan(path: Path) -> LivePlan: ...
def validate_request(plan: LivePlan, request: LiveRequestSpec, allow_mutation: bool) -> None: ...
async def execute_live_plan(plan: LivePlan, *, allow_mutation: bool = False,
                            store_bodies: bool = False) -> tuple[list[LiveObservation], RunReport]: ...
```

## Task 1: Safety Guard with TDD

- [ ] Test rejection of non-allowlisted hosts, scheme changes, user-info URLs, fragments, protocol-relative paths, `..` traversal, more than 20 requests, mutating methods without both gates, and production mutation.
- [ ] Test that query parameters are retained in evidence but endpoint identity uses normalized path only.
- [ ] Test that redirects are not followed.
- [ ] Test that authorization and provider tokens never appear in `repr`, exceptions, artifacts, or caplog output.
- [ ] Implement `load_live_plan` and `validate_request`.

## Task 2: Guarded HTTP Execution

- [ ] Use `httpx.AsyncClient(follow_redirects=False)`.
- [ ] Build provider headers from the environment inside provider modules.
- [ ] Stream responses and abort above 1 MiB.
- [ ] Extract field paths without retaining values.
- [ ] Convert observations to `CapturedExchange` objects with `response_body=None`.
- [ ] Feed those exchanges to `analyze_run`; use plan ID plus UTC run suffix as run ID.
- [ ] Write raw artifacts only after `redact_secrets`.
- [ ] Use MockTransport tests to prove retry limits, timeout handling, 401 handling, 429 handling, oversized response rejection, and success.

## Task 3: GitHub Plans

`github_readonly.yaml`:

- base URL `https://api.github.com`;
- token env `AIT_GITHUB_TOKEN`;
- allowlisted host `api.github.com`;
- request `GET /user`;
- expected endpoint `/user`;
- no sensitive markers.

`github_smoke.yaml`:

- same base and token;
- policy allowlists only `/user`;
- requests `/user`, `/user/repos?per_page=1&page=1`, `/user/repos?per_page=1&page=2`, and `/user/orgs?per_page=1`;
- expected detector output is computed, not stored in the plan.

Required headers:

```text
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Authorization: Bearer <env token>
User-Agent: ait-research-artifact/0.1
```

Tests must mock all requests; unit tests must never call GitHub.

## Task 4: Notion Plan

`notion_readonly.yaml`:

- base URL `https://api.notion.com`;
- token env `AIT_NOTION_TOKEN`;
- allowlisted host `api.notion.com`;
- request `GET /v1/users/me`;
- expected endpoint `/v1/users/me`;
- no sensitive markers.

Required headers:

```text
Authorization: Bearer <env token>
Notion-Version: 2022-06-28
Content-Type: application/json
User-Agent: ait-research-artifact/0.1
```

Do not add mutation to Notion unless the user supplies an isolated sandbox page/database and explicitly approves mutation.

## Task 5: CLI

Implement:

```bash
uv run python -m ait.live_runner run \
  --plan configs/live/github_readonly.yaml \
  --output-root results
```

Also implement `--dry-run`, which validates and prints method plus fully resolved URL without reading credentials or sending requests.

Exit codes:

- `0`: completed and artifact written;
- `1`: request or analysis failure;
- `2`: missing credentials;
- `3`: safety-policy rejection.

Artifacts:

- `results/raw/live/<plan-id>/<run-id>.json`;
- `results/derived/live_<plan-id>_<run-id>.json`.

Do not maintain a synthetic “latest success” file; Phase 6 chooses a run explicitly from a manifest.

## Task 6: Real Sandbox Execution

This task is manual-gated.

- [ ] User creates dedicated least-privilege sandbox credentials.
- [ ] User exports `AIT_GITHUB_TOKEN` and/or `AIT_NOTION_TOKEN` in the shell.
- [ ] Run `--dry-run` and review every URL.
- [ ] Run read-only plans.
- [ ] Inspect artifacts for accidental PII or tokens before adding them to a paper bundle.
- [ ] Record provider API version, token permission settings, UTC time, and response status.

Commands:

```bash
uv run python -m ait.live_runner run --plan configs/live/github_readonly.yaml
uv run python -m ait.live_runner run --plan configs/live/github_smoke.yaml
uv run python -m ait.live_runner run --plan configs/live/notion_readonly.yaml
```

If credentials are unavailable, mark this task `BLOCKED`, not complete.

## Task 7: Verification

```bash
uv run pytest tests/test_live_runner.py tests/providers -v
uv run python -m ait.live_runner run --plan configs/live/github_smoke.yaml --dry-run
uv run python -m ait.live_runner run --plan configs/live/notion_readonly.yaml --dry-run
uv run python -m ait.artifacts results
```

## Acceptance Criteria

- Unit/integration tests use mocked transports only.
- Real runs require environment credentials and explicit commands.
- No secrets or response values leak into default artifacts.
- Live status is distinguishable as completed, failed, blocked, or skipped.
- GitHub/Notion paper rows cannot be produced without a real completed artifact.
- The runner’s observational limitation is documented.

## Handoff to Phase 6

Phase 6 must select live artifacts by exact path and SHA-256 in the claim manifest. It must not select the most favorable run automatically.
