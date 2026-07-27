from __future__ import annotations

from pathlib import Path

import yaml

from ait.live_runner import LivePlan, load_live_plan
from ait.providers.github import build_headers, readonly_plan_dict, smoke_plan_dict


def test_github_headers_contain_required_fields() -> None:
    headers = build_headers("test-token")
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["User-Agent"] == "ait-research-artifact/0.1"


def test_github_readonly_plan_matches_config() -> None:
    config_path = Path("configs/live/github_readonly.yaml")
    plan = load_live_plan(config_path)
    assert plan.id == "github-readonly"
    assert plan.token_env == "AIT_GITHUB_TOKEN"
    assert str(plan.base_url).rstrip("/") == "https://api.github.com"
    assert plan.allowed_hosts == {"api.github.com"}
    assert plan.expected_endpoints == ["/user"]
    assert plan.sensitive_markers == []
    assert len(plan.requests) == 1
    assert plan.requests[0].method == "GET"
    assert plan.requests[0].path == "/user"
    assert LivePlan.model_validate(readonly_plan_dict()).id == plan.id


def test_github_smoke_plan_policy_only_user() -> None:
    plan = load_live_plan(Path("configs/live/github_smoke.yaml"))
    assert plan.expected_endpoints == ["/user"]
    paths = [r.path for r in plan.requests]
    assert paths == [
        "/user",
        "/user/repos?per_page=1&page=1",
        "/user/repos?per_page=1&page=2",
        "/user/orgs?per_page=1",
    ]
    assert LivePlan.model_validate(smoke_plan_dict()).requests[1].path == paths[1]


def test_github_yaml_loads_without_network() -> None:
    raw = yaml.safe_load(Path("configs/live/github_readonly.yaml").read_text(encoding="utf-8"))
    assert raw["provider"] == "github"
