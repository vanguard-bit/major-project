from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
import yaml

from ait.demo_integration import app as integration_app
from ait.mock_saas import app as mock_saas_app
from ait.models import TargetConfig, TestRunConfig as RunConfigModel
from ait.runner import run_assessment

REAL_ASYNC_CLIENT = httpx.AsyncClient


class RoutedAsyncClient:
    """Route httpx calls to in-process FastAPI apps (same pattern as test_end_to_end)."""

    def __init__(self, *args, base_url: str | None = None, timeout: int | None = None, **kwargs):
        del args, timeout, kwargs
        self.base_url = base_url.rstrip("/") if base_url else None
        self.clients = {
            "127.0.0.1:8001": REAL_ASYNC_CLIENT(
                transport=httpx.ASGITransport(app=mock_saas_app),
                base_url="http://127.0.0.1:8001",
            ),
            "127.0.0.1:8000": REAL_ASYNC_CLIENT(
                transport=httpx.ASGITransport(app=integration_app),
                base_url="http://127.0.0.1:8000",
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

    async def request(self, method: str, url: str, **kwargs):
        client, absolute = self._resolve(url)
        return await client.request(method, absolute, **kwargs)

    async def post(self, url: str, **kwargs):
        client, absolute = self._resolve(url)
        return await client.post(absolute, **kwargs)


def _load(name: str) -> TargetConfig:
    path = Path(__file__).resolve().parents[1] / "test_cases" / name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TargetConfig.model_validate(data)


@pytest.mark.anyio
async def test_noisy_crm_still_finds_billing_violation(monkeypatch):
    monkeypatch.setattr("ait.runner.httpx.AsyncClient", RoutedAsyncClient)
    monkeypatch.setattr("ait.demo_integration.httpx.AsyncClient", RoutedAsyncClient)
    target = _load("noisy_crm.yaml")
    run = await run_assessment(target, RunConfigModel())
    assert run.report
    assert "/api/v1/customers/cust-001/billing" in run.report.hidden_endpoints
    assert "/misc/health" not in run.report.hidden_endpoints


@pytest.mark.anyio
async def test_partial_billing_sensitive_detection(monkeypatch):
    monkeypatch.setattr("ait.runner.httpx.AsyncClient", RoutedAsyncClient)
    monkeypatch.setattr("ait.demo_integration.httpx.AsyncClient", RoutedAsyncClient)
    target = _load("partial_billing.yaml")
    run = await run_assessment(target, RunConfigModel())
    assert run.report
    assert run.report.risk_score > 0
    assert any("billing" in f.endpoint for f in run.findings)


@pytest.mark.anyio
async def test_ambiguous_profile_hidden_endpoint(monkeypatch):
    monkeypatch.setattr("ait.runner.httpx.AsyncClient", RoutedAsyncClient)
    monkeypatch.setattr("ait.demo_integration.httpx.AsyncClient", RoutedAsyncClient)
    target = _load("ambiguous_profile.yaml")
    run = await run_assessment(target, RunConfigModel())
    assert run.report
    assert "/api/v1/customers/cust-001/profile" in run.report.hidden_endpoints
