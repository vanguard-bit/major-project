"""
Mock FastAPI Server  (Phase 8 – Test Scenario)
Run with:  uvicorn mock_server:app --host 127.0.0.1 --port 8888

Intentional vulnerabilities:
  • /user  leaks hidden `ssn` and `credit_card` fields
  • /messages  leaks sender `email` in every message
  • /admin  is accessible without proper privilege check
"""

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional

app = FastAPI(title="Mock Vulnerable SaaS API", version="1.0.0")

# ── Simulated database ─────────────────────────────────────────────────────────
USERS_DB = [
    {
        "id": "u001",
        "username": "alice",
        "email": "alice@example.com",
        # --- hidden / sensitive fields that should never be exposed ---
        "ssn": "123-45-6789",
        "credit_card": "4111-1111-1111-1111",
        "password_hash": "$2b$12$FAKEHASH",
    },
    {
        "id": "u002",
        "username": "bob",
        "email": "bob@example.com",
        "ssn": "987-65-4321",
        "credit_card": "5500-0000-0000-0004",
        "password_hash": "$2b$12$FAKEHASH2",
    },
]

MESSAGES_DB = [
    {
        "id": "m001",
        "content": "Hey Alice!",
        "sender_id": "u002",
        # should NOT be here – leaks PII
        "email": "bob@example.com",
        "phone": "+1-555-0100",
    },
    {
        "id": "m002",
        "content": "Project update attached.",
        "sender_id": "u001",
        "email": "alice@example.com",
        "phone": "+1-555-0101",
    },
]

FILES_DB = [
    {
        "id": "f001",
        "filename": "report_Q1.pdf",
        "size": 204800,
        # internal metadata leak
        "internal_path": "/var/data/users/u001/report_Q1.pdf",
        "owner_secret": "SECRET_TOKEN_XYZ",
    },
]

VALID_TOKEN = "test-api-key-12345"


# ── Auth helper ────────────────────────────────────────────────────────────────
def _check_auth(authorization: Optional[str]) -> bool:
    if not authorization:
        return False
    parts = authorization.split()
    return len(parts) == 2 and parts[1] == VALID_TOKEN


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/user")
def get_users(
    authorization: Optional[str] = Header(default=None),
    q: Optional[str] = Query(default=None),
):
    """
    Returns user list.
    BUG: returns ALL fields including ssn and credit_card.
    """
    if not _check_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    results = USERS_DB
    if q:
        results = [u for u in USERS_DB if q.lower() in u["username"].lower()]

    # Intentional bug: no field filtering – ssn, credit_card exposed
    return JSONResponse(content={"users": results})


@app.get("/messages")
def get_messages(authorization: Optional[str] = Header(default=None)):
    """
    Returns messages.
    BUG: includes sender email & phone in every message.
    """
    if not _check_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return JSONResponse(content={"messages": MESSAGES_DB})


@app.get("/files")
def get_files(authorization: Optional[str] = Header(default=None)):
    """
    Returns file listing.
    BUG: exposes internal_path and owner_secret.
    """
    if not _check_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return JSONResponse(content={"files": FILES_DB})


@app.get("/admin")
def admin_panel(authorization: Optional[str] = Header(default=None)):
    """
    Admin panel – accessible to ANY authenticated user (missing role check).
    """
    if not _check_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return JSONResponse(content={
        "admin_data": "ALL_USER_SECRETS",
        "user_count": len(USERS_DB),
        "all_ssns": [u["ssn"] for u in USERS_DB],
    })


@app.get("/search")
def search(
    q: Optional[str] = Query(default=""),
    authorization: Optional[str] = Header(default=None),
):
    """
    Search endpoint – returns matching users including hidden fields.
    """
    if not _check_auth(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    results = [u for u in USERS_DB if q and q.lower() in str(u).lower()]
    return JSONResponse(content={"results": results, "count": len(results)})
