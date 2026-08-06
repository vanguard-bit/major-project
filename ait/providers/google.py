from __future__ import annotations

from typing import Any


def build_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ait-research-artifact/0.1",
    }


def readonly_plan_dict() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": "google-readonly",
        "provider": "google",
        "environment": "sandbox",
        "base_url": "https://www.googleapis.com",
        "allowed_hosts": [
            "www.googleapis.com",
            "cloudresourcemanager.googleapis.com",
        ],
        "token_env": "AIT_GOOGLE_TOKEN",
        "expected_endpoints": ["/oauth2/v2/userinfo"],
        "sensitive_markers": [],
        "requests": [
            {"method": "GET", "path": "/oauth2/v2/userinfo", "phase": "baseline"},
        ],
    }


def smoke_plan_dict() -> dict[str, Any]:
    """Policy allowlists only OAuth userinfo; CRM project listing is over-scope."""
    return {
        "schema_version": "1.0.0",
        "id": "google-smoke",
        "provider": "google",
        "environment": "sandbox",
        "base_url": "https://www.googleapis.com",
        "allowed_hosts": [
            "www.googleapis.com",
            "cloudresourcemanager.googleapis.com",
        ],
        "token_env": "AIT_GOOGLE_TOKEN",
        "expected_endpoints": ["/oauth2/v2/userinfo"],
        "sensitive_markers": [],
        "requests": [
            {"method": "GET", "path": "/oauth2/v2/userinfo", "phase": "baseline"},
            {
                "method": "GET",
                "path": (
                    "https://cloudresourcemanager.googleapis.com/v1/projects?pageSize=1"
                ),
                "phase": "baseline",
            },
        ],
    }
