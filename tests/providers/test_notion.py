from __future__ import annotations

from pathlib import Path

import yaml

from ait.live_runner import LivePlan, load_live_plan
from ait.providers.notion import build_headers, readonly_plan_dict


def test_notion_headers_contain_required_fields() -> None:
    headers = build_headers("notion-secret")
    assert headers["Authorization"] == "Bearer notion-secret"
    assert headers["Notion-Version"] == "2022-06-28"
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"] == "ait-research-artifact/0.1"


def test_notion_readonly_plan_matches_config() -> None:
    plan = load_live_plan(Path("configs/live/notion_readonly.yaml"))
    assert plan.id == "notion-readonly"
    assert plan.provider == "notion"
    assert plan.token_env == "AIT_NOTION_TOKEN"
    assert str(plan.base_url).rstrip("/") == "https://api.notion.com"
    assert plan.allowed_hosts == {"api.notion.com"}
    assert plan.expected_endpoints == ["/v1/users/me"]
    assert plan.sensitive_markers == []
    assert plan.requests[0].method == "GET"
    assert plan.requests[0].path == "/v1/users/me"
    assert LivePlan.model_validate(readonly_plan_dict()).id == plan.id


def test_notion_yaml_loads_without_network() -> None:
    raw = yaml.safe_load(Path("configs/live/notion_readonly.yaml").read_text(encoding="utf-8"))
    assert raw["provider"] == "notion"
    assert "mutation" not in yaml.safe_dump(raw).lower()
