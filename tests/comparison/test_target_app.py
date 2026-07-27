from __future__ import annotations

from fastapi.testclient import TestClient

from comparison.target_app import GROUND_TRUTH, app

client = TestClient(app)


def test_health_and_documented_endpoints():
    assert client.get("/health").json() == {"status": "ok"}
    items = client.get("/api/v1/items").json()
    assert items[0]["id"] == "item-1"
    item = client.get("/api/v1/items/item-1").json()
    assert item["billing_email"] == "billing@example.test"


def test_hidden_endpoint_reachable():
    response = client.get("/api/v1/hidden/export")
    assert response.status_code == 200
    assert "dump" in response.json()
    assert GROUND_TRUTH["CLIENT_POLICY_HIDDEN_ENDPOINT"] == "/api/v1/hidden/export"


def test_controlled_server_500():
    response = client.get("/api/v1/items/item-1/explode")
    assert response.status_code == 500


def test_openapi_response_schema_violation_returns_non_string_name():
    payload = client.get("/api/v1/items/item-1/schema-violation").json()
    assert isinstance(payload["name"], int)
