from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException


app = FastAPI(title="Mock SaaS")

CUSTOMERS: dict[str, dict[str, Any]] = {
    "cust-001": {
        "customer_id": "cust-001",
        "name": "Aster Labs",
        "notes": [{"id": "note-1", "text": "Prefers weekly summaries."}],
        "billing": {
            "billing_email": "billing+seed@example.com",
            "tax_id": "TAX-DEFAULT",
            "plan": "enterprise",
        },
    }
}

AUDIT_LOGS: dict[str, list[dict[str, Any]]] = {}
OAUTH_TOKENS = {"demo-client": "demo-static-access-token"}


def _append_audit(
    run_id: str,
    phase: str,
    path: str,
    response_body: Any,
    method: str = "GET",
    request_body: dict[str, Any] | None = None,
) -> None:
    body_fields = []
    contains_sensitive_marker = False
    if isinstance(response_body, dict):
        body_fields = sorted(response_body.keys())
        contains_sensitive_marker = "billing_email" in response_body or "tax_id" in response_body
    AUDIT_LOGS.setdefault(run_id, []).append(
        {
            "run_id": run_id,
            "phase": phase,
            "method": method,
            "path": path,
            "status_code": 200,
            "request_headers": {},
            "request_body": request_body,
            "response_body": response_body,
            "extracted_fields": body_fields,
            "contains_sensitive_marker": contains_sensitive_marker,
        }
    )


@app.post("/oauth/token")
async def issue_token(payload: dict[str, str]):
    client_id = payload.get("client_id")
    client_secret = payload.get("client_secret")
    if client_id != "demo-client" or client_secret != "demo-secret":
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    return {"access_token": OAUTH_TOKENS[client_id], "token_type": "bearer"}


@app.post("/admin/seed")
async def seed_run(payload: dict[str, Any]):
    run_id = payload["run_id"]
    markers = payload.get("sensitive_markers", [])
    CUSTOMERS["cust-001"]["billing"]["billing_email"] = f"{run_id}@example.test"
    CUSTOMERS["cust-001"]["billing"]["tax_id"] = f"TAX-{run_id.upper()}"
    AUDIT_LOGS[run_id] = []
    return {"status": "seeded", "markers": markers}


@app.get("/admin/audit/{run_id}")
async def get_audit(run_id: str):
    return {"entries": AUDIT_LOGS.get(run_id, [])}


def _authorize(authorization: str | None) -> None:
    if authorization != "Bearer demo-static-access-token":
        raise HTTPException(status_code=401, detail="Missing or invalid token")


@app.get("/api/v1/customers")
async def list_customers(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = [
        {"customer_id": customer["customer_id"], "name": customer["name"]}
        for customer in CUSTOMERS.values()
    ]
    _append_audit(x_run_id, x_phase, "/api/v1/customers", response)
    return response


@app.get("/api/v1/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {
        "customer_id": CUSTOMERS[customer_id]["customer_id"],
        "name": CUSTOMERS[customer_id]["name"],
    }
    _append_audit(x_run_id, x_phase, f"/api/v1/customers/{customer_id}", response)
    return response


@app.get("/api/v1/customers/{customer_id}/notes")
async def get_notes(
    customer_id: str,
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"notes": CUSTOMERS[customer_id]["notes"]}
    _append_audit(x_run_id, x_phase, f"/api/v1/customers/{customer_id}/notes", response)
    return response


@app.get("/api/v1/customers/{customer_id}/billing")
async def get_billing(
    customer_id: str,
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = CUSTOMERS[customer_id]["billing"]
    _append_audit(x_run_id, x_phase, f"/api/v1/customers/{customer_id}/billing", response)
    return response
