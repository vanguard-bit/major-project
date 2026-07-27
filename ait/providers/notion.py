from __future__ import annotations

from typing import Any


def build_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
        "User-Agent": "ait-research-artifact/0.1",
    }


def readonly_plan_dict() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": "notion-readonly",
        "provider": "notion",
        "environment": "sandbox",
        "base_url": "https://api.notion.com",
        "allowed_hosts": ["api.notion.com"],
        "token_env": "AIT_NOTION_TOKEN",
        "expected_endpoints": ["/v1/users/me"],
        "sensitive_markers": [],
        "requests": [{"method": "GET", "path": "/v1/users/me", "phase": "baseline"}],
    }
