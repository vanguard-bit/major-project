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
        # Track both default and scenario-specific sensitive fields
        sensitive_fields = {"billing_email", "tax_id", "repo_secret", "private_key", "auth_token"}
        contains_sensitive_marker = any(field in response_body for field in sensitive_fields)
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
async def issue_token(form_data: dict[str, str]):
    client_id = form_data.get("client_id")
    client_secret = form_data.get("client_secret")
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


# --- Platform Mock Endpoints ---

@app.get("/slack/auth.test")
async def slack_auth_test(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"ok": True, "url": "https://test.slack.com/", "user": "bot-user"}
    _append_audit(x_run_id, x_phase, "/slack/auth.test", response)
    return response


@app.get("/slack/users.list")
async def slack_users_list(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"ok": True, "members": [{"id": "U123", "name": "alice"}]}
    _append_audit(x_run_id, x_phase, "/slack/users.list", response)
    return response


@app.get("/slack/conversations.history")
async def slack_conv_history(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"ok": True, "messages": [{"text": "hello"}]}
    _append_audit(x_run_id, x_phase, "/slack/conversations.history", response)
    return response


@app.get("/github/user/public_repos")
async def github_public_repos(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = [{"id": 1, "full_name": "org/public-repo"}]
    _append_audit(x_run_id, x_phase, "/github/user/public_repos", response)
    return response


@app.get("/github/user/private_repos")
async def github_private_repos(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {
        "id": 2,
        "full_name": "org/private-repo",
        "repo_secret": "github_pat_SECRET123",
        "private_key": "BEGIN-RSA-KEY",
    }
    _append_audit(x_run_id, x_phase, "/github/user/private_repos", response)
    return response


@app.get("/google/gmail/readonly")
async def google_gmail_readonly(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"messages": [{"id": "msg1"}]}
    _append_audit(x_run_id, x_phase, "/google/gmail/readonly", response)
    return response


@app.post("/google/gmail/send")
async def google_gmail_send(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"id": "sent123", "auth_token": "SENSITIVE-TOKEN-456"}
    _append_audit(x_run_id, x_phase, "/google/gmail/send", response, method="POST")
    return response


@app.get("/notion/pages/read")
async def notion_pages_read(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"object": "page", "id": "p1"}
    _append_audit(x_run_id, x_phase, "/notion/pages/read", response)
    return response


@app.get("/notion/pages/list")
async def notion_pages_list(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"results": [{"id": "p1"}]}
    _append_audit(x_run_id, x_phase, "/notion/pages/list", response)
    return response


@app.patch("/notion/pages/update")
async def notion_pages_update(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"id": "p1", "updated": True}
    _append_audit(x_run_id, x_phase, "/notion/pages/update", response, method="PATCH")
    return response


@app.get("/trello/boards")
async def trello_boards(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = [{"id": "b1", "name": "Project Board"}]
    _append_audit(x_run_id, x_phase, "/trello/boards", response)
    return response


@app.post("/trello/cards")
async def trello_cards(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"id": "c1", "name": "New Card"}
    _append_audit(x_run_id, x_phase, "/trello/cards", response, method="POST")
    return response


@app.get("/misc/health")
async def misc_health(
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"status": "ok"}
    _append_audit(x_run_id, x_phase, "/misc/health", response)
    return response


@app.get("/api/v1/customers/{customer_id}/extension")
async def get_customer_extension(
    customer_id: str,
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    """Synthetic field name not covered by typical marker lists (FN4 demo)."""
    _authorize(authorization)
    response = {"masked_credential": "EXFIL-SIMULATION-VALUE"}
    _append_audit(x_run_id, x_phase, f"/api/v1/customers/{customer_id}/extension", response)
    return response


@app.get("/api/v1/customers/{customer_id}/profile")
async def get_customer_profile(
    customer_id: str,
    x_run_id: str = Header(...),
    x_phase: str = Header(...),
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    response = {"customer_id": customer_id, "alias": "non-canonical-profile-view"}
    _append_audit(x_run_id, x_phase, f"/api/v1/customers/{customer_id}/profile", response)
    return response


# --- Original Endpoints ---

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
    full = CUSTOMERS[customer_id]["billing"]
    # Baseline may return only a subset of sensitive fields (partial exposure).
    if x_phase == "baseline":
        response = {"billing_email": full["billing_email"]}
    else:
        response = dict(full)
    _append_audit(x_run_id, x_phase, f"/api/v1/customers/{customer_id}/billing", response)
    return response
