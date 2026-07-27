from __future__ import annotations

import httpx
from fastapi import FastAPI

app = FastAPI(title="Demo Integration")


async def _fetch(client: httpx.AsyncClient, path: str, run_id: str, phase: str, token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Run-Id": run_id,
        "X-Phase": phase,
    }
    response = await client.get(path, headers=headers)
    response.raise_for_status()
    return response.json()


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
            billing = await _fetch(
                client,
                f"/api/v1/customers/{customer_id}/billing",
                run_id,
                phase,
                token,
            )
    return {
        "synced": True,
        "customer_count": len(customers),
        "customer_name": customer["name"],
        "note_count": len(notes["notes"]),
        "billing_touched": billing is not None,
    }
