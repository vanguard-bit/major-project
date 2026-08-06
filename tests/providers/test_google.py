from __future__ import annotations

from pathlib import Path

from ait.live_runner import LivePlan, load_live_plan
from ait.providers.google import build_headers, readonly_plan_dict, smoke_plan_dict


def test_google_headers() -> None:
    headers = build_headers("tok")
    assert headers["Authorization"] == "Bearer tok"
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"] == "ait-research-artifact/0.1"


def test_google_readonly_plan_matches_config() -> None:
    plan = load_live_plan(Path("configs/live/google_readonly.yaml"))
    assert plan.id == "google-readonly"
    assert plan.provider == "google"
    assert plan.token_env == "AIT_GOOGLE_TOKEN"
    assert plan.expected_endpoints == ["/oauth2/v2/userinfo"]
    assert LivePlan.model_validate(readonly_plan_dict()).id == plan.id


def test_google_smoke_includes_crm_over_scope() -> None:
    plan = load_live_plan(Path("configs/live/google_smoke.yaml"))
    assert plan.expected_endpoints == ["/oauth2/v2/userinfo"]
    paths = [r.path for r in plan.requests]
    assert paths[0] == "/oauth2/v2/userinfo"
    assert paths[1].startswith("https://cloudresourcemanager.googleapis.com/")
    assert LivePlan.model_validate(smoke_plan_dict()).id == plan.id
