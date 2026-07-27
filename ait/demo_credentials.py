from __future__ import annotations

import os

DEMO_CLIENT_ID_ENV = "AIT_DEMO_CLIENT_ID"
DEMO_CLIENT_SECRET_ENV = "AIT_DEMO_CLIENT_SECRET"
DEMO_ACCESS_TOKEN_ENV = "AIT_DEMO_ACCESS_TOKEN"

_DEFAULTS = {
    DEMO_CLIENT_ID_ENV: "demo-client",
    DEMO_CLIENT_SECRET_ENV: "demo-secret",
    DEMO_ACCESS_TOKEN_ENV: "demo-static-access-token",
}


def ensure_demo_credentials() -> None:
    """Populate demo credential env vars when unset (local demo/tests only)."""
    for key, value in _DEFAULTS.items():
        os.environ.setdefault(key, value)


def demo_client_id() -> str:
    ensure_demo_credentials()
    return os.environ[DEMO_CLIENT_ID_ENV]


def demo_client_secret() -> str:
    ensure_demo_credentials()
    return os.environ[DEMO_CLIENT_SECRET_ENV]


def demo_access_token() -> str:
    ensure_demo_credentials()
    return os.environ[DEMO_ACCESS_TOKEN_ENV]
