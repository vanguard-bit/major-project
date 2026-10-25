import json

import pytest
from typer.testing import CliRunner

from ait.integration_trace import IntegrationPolicy, app, assert_sanitized, evaluate

CANARY = "canary-run-5c1e@example.test"
TOKEN = "ghp_" + "A" * 36


def _policy(**overrides):
    data = {
        "integration": {
            "name": "probe-app",
            "repository": "https://example.invalid/upstream/app",
            "commit": "abc123",
            "license": "MIT",
        },
        "allowed_hosts": ["api.github.com"],
        "ignore_hosts": ["smee.io"],
        "expected_endpoints": ["GET /repos/{owner}/{repo}", "/repos/{owner}/{repo}/contents/{p*}"],
        "denied_endpoints": ["DELETE /repos/{owner}/{repo}"],
        "canaries": [CANARY],
    }
    data.update(overrides)
    return IntegrationPolicy.model_validate(data)


def _har(entries):
    return {"log": {"entries": [
        {
            "startedDateTime": f"2026-10-26T10:00:0{i}Z",
            "request": {
                "method": method,
                "url": url,
                "headers": [{"name": "Authorization", "value": f"Bearer {TOKEN}"}],
                **({"postData": {"text": json.dumps(body)}} if body else {}),
            },
            "response": {"status": 200, "content": {"text": json.dumps(resp) if resp else ""}},
        }
        for i, (method, url, body, resp) in enumerate(entries)
    ]}}


ENTRIES = [
    ("GET", f"https://api.github.com/repos/o/r?access_token={TOKEN}", None, {"name": "r"}),
    ("GET", "https://api.github.com/repos/o/r/contents/.github/settings.yml", None,
     {"email": CANARY}),
    ("DELETE", "https://api.github.com/repos/o/r", None, None),
    ("POST", "https://collector.example.net/ingest", {"leak": CANARY}, None),
    ("GET", "https://api.github.com/user/orgs", None, None),
    ("POST", "https://smee.io/channel", None, None),
]


def test_outcomes_and_no_secret_leak(tmp_path):
    har = tmp_path / "run.har"
    har.write_text(json.dumps(_har(ENTRIES)), encoding="utf-8")
    policy = tmp_path / "policy.yaml"
    policy.write_text(json.dumps(_policy().model_dump()), encoding="utf-8")
    out = tmp_path / "out.json"
    result = CliRunner().invoke(app, [
        "--policy", str(policy), "--baseline", str(har), "--workflow-id", "wf-1",
        "--source", "test-har", "--output", str(out),
    ])
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    assert TOKEN not in text and CANARY not in text and "Authorization" not in text
    payload = json.loads(text)["payload"]
    outcomes = [e["outcome"] for e in payload["entries"]]
    assert outcomes == [
        "permitted_behavior",
        "permitted_behavior",
        "confirmed_policy_violation",
        "confirmed_policy_violation",
        "uncertain_policy",
        "out_of_scope",
    ]
    assert payload["entries"][0]["query_param_names"] == ["access_token"]
    assert payload["entries"][1]["endpoint"] == "/repos/{owner}/{repo}/contents/{p*}"
    assert "hidden_endpoint" in payload["ait"]["categories"]
    assert payload["baseline"]["canary_hit_count"] == 2


def test_guard_rejects_secret_in_path():
    payload = evaluate(
        _policy(),
        {"baseline": [{"method": "GET", "url": f"https://api.github.com/x/{TOKEN}"}]},
        "wf",
        "jsonl",
    )
    with pytest.raises(ValueError):
        assert_sanitized(payload, [CANARY])
