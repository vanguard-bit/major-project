from __future__ import annotations

from urllib.parse import urlparse

import httpx
import pytest

from ait.api import DEMO_TARGET
from ait.demo_integration import app as integration_app
from ait.mock_saas import app as mock_saas_app
from ait.models import TestRunConfig as RunConfigModel
from ait.runner import run_assessment

REAL_ASYNC_CLIENT = httpx.AsyncClient


class RoutedAsyncClient:
    def __init__(self, *args, base_url: str | None = None, timeout: int | None = None, **kwargs):
        del args, timeout, kwargs
        self.base_url = base_url.rstrip("/") if base_url else None
        self.clients = {
            "127.0.0.1:8001": REAL_ASYNC_CLIENT(
                transport=httpx.ASGITransport(app=mock_saas_app),
                base_url="http://127.0.0.1:8001",
            ),
            "127.0.0.1:8002": REAL_ASYNC_CLIENT(
                transport=httpx.ASGITransport(app=integration_app),
                base_url="http://127.0.0.1:8002",
            ),
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        await self.aclose()

    async def aclose(self):
        for client in self.clients.values():
            await client.aclose()

    def _resolve(self, url: str) -> tuple[httpx.AsyncClient, str]:
        absolute = url if url.startswith("http") else f"{self.base_url}{url}"
        parsed = urlparse(absolute)
        return self.clients[parsed.netloc], absolute

    async def get(self, url: str, **kwargs):
        client, absolute = self._resolve(url)
        return await client.get(absolute, **kwargs)

    async def post(self, url: str, **kwargs):
        client, absolute = self._resolve(url)
        return await client.post(absolute, **kwargs)


@pytest.mark.anyio
async def test_run_assessment_detects_hidden_billing_access(monkeypatch):
    monkeypatch.setattr("ait.runner.httpx.AsyncClient", RoutedAsyncClient)
    monkeypatch.setattr("ait.demo_integration.httpx.AsyncClient", RoutedAsyncClient)

    run = await run_assessment(DEMO_TARGET, RunConfigModel())

    assert run.report is not None
    assert "/api/v1/customers/cust-001/billing" in run.report.hidden_endpoints
    assert "billing_email" in run.report.sensitive_fields_accessed
    assert any(f.category.value == "behavioral_divergence" for f in run.findings)
