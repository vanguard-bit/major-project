import pytest

from ait.baseline import classify_endpoint, run_baseline
from ait.experiments.compare_baseline import compute_metrics
from ait.models import CapturedExchange

CANARY = "canary-7f3a91@example.test"


def _ex(path, phase="baseline", request_body=None, response_body=None):
    return CapturedExchange(
        run_id="r",
        phase=phase,
        method="GET",
        path=path,
        status_code=200,
        request_body=request_body,
        response_body=response_body,
    )


def test_classify_endpoint_semantics():
    allowed = {"/a", "/b?x=1"}
    assert classify_endpoint("/a", allowed) == "allowed"
    assert classify_endpoint("/b?x=1", allowed) == "allowed"
    assert classify_endpoint("/a?page=2", allowed) == "ambiguous"
    assert classify_endpoint("/c", allowed) == "unexpected"
    assert classify_endpoint("c", allowed) == "unparseable"


def test_baseline_flags_unexpected_and_canary_in_outbound_request():
    exchanges = [
        _ex("/a", response_body={"email": CANARY}),
        _ex("/a?page=2"),
        _ex("/exfil", phase="mutated", request_body={"payload": [f"x {CANARY} y"]}),
    ]
    result = run_baseline(["/a"], [CANARY], exchanges)
    assert result.unexpected_endpoints == ["/exfil"]
    assert result.ambiguous_endpoints == ["/a?page=2"]
    assert {(h.endpoint, h.location) for h in result.canary_hits} == {
        ("/a", "response_body"),
        ("/exfil", "request_body"),
    }
    assert result.categories == {"hidden_endpoint", "sensitive_field_access"}


def test_short_canaries_rejected():
    with pytest.raises(ValueError):
        run_baseline(["/a"], ["short"], [_ex("/a")])


def test_compute_metrics_counts_and_unscored_cases():
    def row(sid, outcome, expected, ait, baseline):
        return {
            "scenario_id": sid,
            "outcome": outcome,
            "expected": expected,
            "ait": ait,
            "baseline": baseline,
            "baseline_detail": {"ambiguous_endpoints": []},
        }

    rows = [
        row("v1", "confirmed_policy_violation", ["behavioral_divergence"],
            ["behavioral_divergence"], []),
        row("p1", "permitted_behavior", [], [], ["hidden_endpoint"]),
        row("u1", "uncertain_policy", ["hidden_endpoint"], ["hidden_endpoint"], []),
    ]
    m = compute_metrics(rows)
    assert m["scored_count"] == 2
    assert [u["scenario_id"] for u in m["unscored"]] == ["u1"]
    ait, base = m["methods"]["ait"]["scenario_level"], m["methods"]["baseline"]["scenario_level"]
    assert (ait["tp"], ait["fp"], ait["fn"], ait["tn"]) == (1, 0, 0, 1)
    assert (base["tp"], base["fp"], base["fn"], base["tn"]) == (0, 1, 1, 0)
    assert m["methods"]["baseline"]["categories"]["behavioral_divergence"] == "n/a"
