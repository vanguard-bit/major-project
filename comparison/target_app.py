from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="AIT Comparison Target",
    version="1.0.0",
    description="Isolated synthetic target for tool comparison.",
)

GROUND_TRUTH = {
    "CLIENT_POLICY_HIDDEN_ENDPOINT": "/api/v1/hidden/export",
    "CLIENT_POLICY_SENSITIVE_FIELD": "/api/v1/items/{item_id}",
    "SERVER_INTERNAL_ERROR": "/api/v1/items/{item_id}/explode",
    "OPENAPI_RESPONSE_VIOLATION": "/api/v1/items/{item_id}/schema-violation",
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/items")
def list_items() -> list[dict[str, str]]:
    return [{"id": "item-1", "name": "Widget"}]


@app.get("/api/v1/items/{item_id}")
def get_item(item_id: str) -> dict[str, str]:
    return {
        "id": item_id,
        "name": "Widget",
        "billing_email": "billing@example.test",
    }


@app.get("/api/v1/items/{item_id}/explode")
def explode_item(item_id: str) -> None:
    raise HTTPException(status_code=500, detail=f"controlled fault for {item_id}")


@app.get("/api/v1/items/{item_id}/schema-violation")
def schema_violation(item_id: str) -> dict[str, Any]:
    return {"id": item_id, "name": 12345}


@app.get("/api/v1/hidden/export")
def hidden_export() -> dict[str, str]:
    return {"dump": "synthetic-export"}
