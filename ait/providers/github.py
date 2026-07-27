from __future__ import annotations

from typing import Any


def build_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
        "User-Agent": "ait-research-artifact/0.1",
    }


def readonly_plan_dict() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": "github-readonly",
        "provider": "github",
        "environment": "sandbox",
        "base_url": "https://api.github.com",
        "allowed_hosts": ["api.github.com"],
        "token_env": "AIT_GITHUB_TOKEN",
        "expected_endpoints": ["/user"],
        "sensitive_markers": [],
        "requests": [{"method": "GET", "path": "/user", "phase": "baseline"}],
    }


def smoke_plan_dict() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "id": "github-smoke",
        "provider": "github",
        "environment": "sandbox",
        "base_url": "https://api.github.com",
        "allowed_hosts": ["api.github.com"],
        "token_env": "AIT_GITHUB_TOKEN",
        "expected_endpoints": ["/user"],
        "sensitive_markers": [],
        "requests": [
            {"method": "GET", "path": "/user", "phase": "baseline"},
            {
                "method": "GET",
                "path": "/user/repos?per_page=1&page=1",
                "phase": "baseline",
            },
            {
                "method": "GET",
                "path": "/user/repos?per_page=1&page=2",
                "phase": "baseline",
            },
            {
                "method": "GET",
                "path": "/user/orgs?per_page=1",
                "phase": "baseline",
            },
        ],
    }
