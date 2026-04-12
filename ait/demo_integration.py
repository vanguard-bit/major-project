from __future__ import annotations

import httpx
from fastapi import FastAPI


app = FastAPI(title="Demo Integration")


async def _fetch(
    client: httpx.AsyncClient,
    path: str,
    run_id: str,
    phase: str,
    token: str,
    method: str = "GET",
):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Run-Id": run_id,
        "X-Phase": phase,
    }
    response = await client.request(method, path, headers=headers)
    response.raise_for_status()
    return response.json()


@app.post("/sync/slack")
async def sync_slack(payload: dict[str, str]):
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/slack/auth.test", run_id, phase, token)
        # Score 80: 2 hidden, 0 sensitive, 2 divergence (baseline_only and mutated_only)
        if phase == "baseline":
            await _fetch(client, "/slack/users.list", run_id, phase, token)
        if phase == "mutated":
            await _fetch(client, "/slack/conversations.history", run_id, phase, token)
    return {"status": "synced"}


@app.post("/sync/github")
async def sync_github(payload: dict[str, str]):
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/github/user/public_repos", run_id, phase, token)
        # Score 65: 1 hidden, 2 sensitive fields, 0 divergence
        await _fetch(client, "/github/user/private_repos", run_id, phase, token)
    return {"status": "synced"}


@app.post("/sync/google")
async def sync_google(payload: dict[str, str]):
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/google/gmail/readonly", run_id, phase, token)
        # Score 45: 1 hidden, 1 sensitive field, 0 divergence
        await _fetch(client, "/google/gmail/send", run_id, phase, token, method="POST")
    return {"status": "synced"}


@app.post("/sync/notion")
async def sync_notion(payload: dict[str, str]):
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/notion/pages/read", run_id, phase, token)
        # Score 55: 1 hidden, 0 sensitive, 2 divergence
        if phase == "baseline":
            await _fetch(client, "/notion/pages/list", run_id, phase, token)
        if phase == "mutated":
            await _fetch(client, "/notion/pages/update", run_id, phase, token, method="PATCH")
    return {"status": "synced"}


@app.post("/sync/trello")
async def sync_trello(payload: dict[str, str]):
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/trello/boards", run_id, phase, token)
        # Score 40: 1 hidden, 0 sensitive, 1 divergence (mutated_only)
        if phase == "mutated":
            await _fetch(client, "/trello/cards", run_id, phase, token, method="POST")
    return {"status": "synced"}


@app.post("/sync/slack-compliant")
async def sync_slack_compliant(payload: dict[str, str]):
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/slack/auth.test", run_id, phase, token)
    return {"status": "synced"}


@app.post("/sync/github-compliant")
async def sync_github_compliant(payload: dict[str, str]):
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/github/user/public_repos", run_id, phase, token)
    return {"status": "synced"}


@app.post("/sync/noisy_crm")
async def sync_noisy_crm(payload: dict[str, str]):
    """Irrelevant health polls interleaved with CRM calls (declared policy excludes billing)."""
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    customer_id = "cust-001"
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        for _ in range(8):
            await _fetch(client, "/misc/health", run_id, phase, token)
        customers = await _fetch(client, "/api/v1/customers", run_id, phase, token)
        customer = await _fetch(client, f"/api/v1/customers/{customer_id}", run_id, phase, token)
        notes = await _fetch(client, f"/api/v1/customers/{customer_id}/notes", run_id, phase, token)
        billing = None
        if phase == "mutated":
            billing = await _fetch(client, f"/api/v1/customers/{customer_id}/billing", run_id, phase, token)
    return {
        "synced": True,
        "health_polls": 8,
        "customer_count": len(customers),
        "billing_touched": billing is not None,
    }


@app.post("/sync/partial_billing")
async def sync_partial_billing(payload: dict[str, str]):
    """Billing in both phases: baseline returns partial sensitive payload; mutated full."""
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    customer_id = "cust-001"
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/api/v1/customers", run_id, phase, token)
        await _fetch(client, f"/api/v1/customers/{customer_id}", run_id, phase, token)
        await _fetch(client, f"/api/v1/customers/{customer_id}/notes", run_id, phase, token)
        await _fetch(client, f"/api/v1/customers/{customer_id}/billing", run_id, phase, token)
    return {"synced": True, "phase": phase}


@app.post("/sync/fn4_alias")
async def sync_fn4_alias(payload: dict[str, str]):
    """Reads aliased secret field name not listed in sensitive_markers (FN4)."""
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    customer_id = "cust-001"
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/api/v1/customers", run_id, phase, token)
        await _fetch(client, f"/api/v1/customers/{customer_id}/extension", run_id, phase, token)
    return {"synced": True, "fn4_demo": True}


@app.post("/sync/ambiguous_profile")
async def sync_ambiguous_profile(payload: dict[str, str]):
    """Canonical customer paths plus a non-declared profile alias path."""
    run_id, phase, token = payload["run_id"], payload["phase"], payload["token"]
    customer_id = "cust-001"
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        await _fetch(client, "/api/v1/customers", run_id, phase, token)
        await _fetch(client, f"/api/v1/customers/{customer_id}", run_id, phase, token)
        await _fetch(client, f"/api/v1/customers/{customer_id}/notes", run_id, phase, token)
        await _fetch(client, f"/api/v1/customers/{customer_id}/profile", run_id, phase, token)
        if phase == "mutated":
            await _fetch(client, f"/api/v1/customers/{customer_id}/billing", run_id, phase, token)
    return {"synced": True}


@app.post("/sync")
async def sync(payload: dict[str, str]):
    run_id = payload["run_id"]
    phase = payload["phase"]
    token = payload["token"]
    customer_id = "cust-001"
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as client:
        customers = await _fetch(client, "/api/v1/customers", run_id, phase, token)
        customer = await _fetch(client, f"/api/v1/customers/{customer_id}", run_id, phase, token)
        notes = await _fetch(client, f"/api/v1/customers/{customer_id}/notes", run_id, phase, token)
        billing = None
        if phase == "mutated":
            billing = await _fetch(client, f"/api/v1/customers/{customer_id}/billing", run_id, phase, token)
    return {
        "synced": True,
        "customer_count": len(customers),
        "customer_name": customer["name"],
        "note_count": len(notes["notes"]),
        "billing_touched": billing is not None,
    }
