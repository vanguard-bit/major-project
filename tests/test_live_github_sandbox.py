from __future__ import annotations

import os

import pytest

from ait.live_github import run_live_github_sandbox


@pytest.mark.anyio
async def test_live_github_sandbox_detects_user_repos_under_user_only_policy():
    if not os.environ.get("AIT_GITHUB_TOKEN"):
        pytest.skip("Set AIT_GITHUB_TOKEN to run the live GitHub sandbox probe.")
    record = await run_live_github_sandbox()
    assert record.report is not None
    assert "/user/repos" in record.report.hidden_endpoints
    assert "/user/orgs" in record.report.hidden_endpoints
    assert len(record.report.hidden_endpoints) >= 2
    assert record.report.risk_score >= 50
