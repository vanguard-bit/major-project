"""Controlled false-negative demo: aliased secret field vs marker list (FN4)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
import yaml

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


@pytest.mark.anyio
async def test_fn4_alias_field_not_flagged_when_not_in_markers(monkeypatch):
    monkeypatch.setattr("ait.runner.httpx.AsyncClient", RoutedAsyncClient)
    monkeypatch.setattr("ait.demo_integration.httpx.AsyncClient", RoutedAsyncClient)
    path = Path(__file__).resolve().parents[1] / "test_cases" / "fn4_field_alias.yaml"
    target = yaml.safe_load(path.read_text(encoding="utf-8"))
    from ait.models import TargetConfig

    run = await run_assessment(TargetConfig.model_validate(target), RunConfigModel())
    assert run.report is not None
    bodies = [e.response_body for e in run.exchanges if isinstance(e.response_body, dict)]
    assert any(b.get("masked_credential") for b in bodies)
    assert not any(f.category.value == "sensitive_field_access" for f in run.findings)
    assert run.report.risk_score == 0
