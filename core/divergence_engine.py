"""
Phase 5 – Behavioral Divergence Engine
Compares expected schema/behavior per endpoint against observed behavior
and logs any structural or semantic deviations.
"""

from typing import Any, Dict, List, Optional, Set


class DivergenceEngine:
    """
    Detects behavioral divergence between what an API *should* return
    (defined schema) and what it *actually* returns.

    Divergence types:
      - SCHEMA_MISMATCH    : fields present but wrong type
      - EXTRA_FIELDS       : server adds undocumented fields
      - MISSING_FIELDS     : expected fields absent
      - STATUS_ANOMALY     : unexpected HTTP status codes
      - EMPTY_RESPONSE     : non-4xx with empty body
      - OVERSIZED_RESPONSE : response suspiciously large (data dump)
    """

    EXPECTED_TYPES: Dict[str, type] = {
        "id":          str,
        "username":    str,
        "email":       str,
        "content":     str,
        "sender_id":   str,
        "filename":    str,
        "size":        int,
        "count":       int,
    }

    def __init__(self, endpoint_configs: List[Dict[str, Any]]):
        self._config: Dict[str, Dict[str, Any]] = {}
        for ep in endpoint_configs:
            self._config[ep["path"]] = {
                "expected_fields": set(ep.get("expected_fields", [])),
                "sensitive_fields": set(ep.get("sensitive_fields", [])),
            }

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Accepts fuzzer / taint result list.
        Returns a list of divergence anomaly dicts.
        """
        anomalies = []

        for result in results:
            endpoint = result.get("endpoint", "unknown")
            response = result.get("response", {})
            status   = response.get("status_code", 0)
            body     = response.get("body", {})

            if response.get("error"):
                continue

            cfg      = self._config.get(endpoint, {})
            expected = cfg.get("expected_fields", set())

            # 1. Status anomaly
            anomalies += self._check_status(endpoint, status, result)

            # 2. Empty response on success
            anomalies += self._check_empty(endpoint, status, body, result)

            # 3. Extra / missing fields
            if expected:
                flat_keys = self._extract_keys(body)
                anomalies += self._check_extra(endpoint, flat_keys, expected, result)
                anomalies += self._check_missing(endpoint, flat_keys, expected, result)

            # 4. Type mismatches in top-level objects
            anomalies += self._check_types(endpoint, body, result)

            # 5. Oversized response (potential data dump)
            anomalies += self._check_oversized(endpoint, body, result)

        return anomalies

    # ── Checks ─────────────────────────────────────────────────────────────────

    def _check_status(self, ep, status, result) -> List[Dict]:
        anomalies = []
        strategy  = result.get("strategy", "n/a")
        # Valid authenticated baseline request should return 2xx
        if strategy == "baseline" and status not in range(200, 300):
            anomalies.append({
                "type": "STATUS_ANOMALY",
                "endpoint": ep,
                "strategy": strategy,
                "observed_status": status,
                "severity": "HIGH",
                "detail": f"Baseline request returned non-2xx status {status}.",
            })
        # Invalid-token strategy should get 401 — if it gets 200 → auth bypass
        if strategy == "inject_invalid_tokens" and status == 200:
            anomalies.append({
                "type": "AUTH_BYPASS",
                "endpoint": ep,
                "strategy": strategy,
                "observed_status": status,
                "severity": "CRITICAL",
                "detail": "Request with invalid/empty token returned HTTP 200. Possible auth bypass.",
            })
        return anomalies

    def _check_empty(self, ep, status, body, result) -> List[Dict]:
        if status in range(200, 300) and not body:
            return [{
                "type": "EMPTY_RESPONSE",
                "endpoint": ep,
                "strategy": result.get("strategy", "n/a"),
                "severity": "LOW",
                "detail": "Successful response has an empty body.",
            }]
        return []

    def _check_extra(self, ep, actual: Set[str], expected: Set[str], result) -> List[Dict]:
        extra = actual - expected
        if extra:
            return [{
                "type": "EXTRA_FIELDS",
                "endpoint": ep,
                "strategy": result.get("strategy", "n/a"),
                "extra_fields": sorted(extra),
                "severity": "HIGH",
                "detail": f"Response includes undocumented field(s): {sorted(extra)}",
            }]
        return []

    def _check_missing(self, ep, actual: Set[str], expected: Set[str], result) -> List[Dict]:
        missing = expected - actual
        if missing:
            return [{
                "type": "MISSING_FIELDS",
                "endpoint": ep,
                "strategy": result.get("strategy", "n/a"),
                "missing_fields": sorted(missing),
                "severity": "MEDIUM",
                "detail": f"Expected field(s) absent from response: {sorted(missing)}",
            }]
        return []

    def _check_types(self, ep, body, result) -> List[Dict]:
        anomalies = []
        flat_items = self._flatten_items(body)
        for key, value in flat_items.items():
            if key in self.EXPECTED_TYPES:
                exp_type = self.EXPECTED_TYPES[key]
                if not isinstance(value, exp_type):
                    anomalies.append({
                        "type": "SCHEMA_MISMATCH",
                        "endpoint": ep,
                        "strategy": result.get("strategy", "n/a"),
                        "field": key,
                        "expected_type": exp_type.__name__,
                        "actual_type": type(value).__name__,
                        "severity": "MEDIUM",
                        "detail": f"Field '{key}' expected {exp_type.__name__}, got {type(value).__name__}.",
                    })
        return anomalies

    def _check_oversized(self, ep, body, result) -> List[Dict]:
        import json
        size_bytes = len(json.dumps(body).encode("utf-8"))
        if size_bytes > 50_000:  # > 50 KB is suspicious for a mock API
            return [{
                "type": "OVERSIZED_RESPONSE",
                "endpoint": ep,
                "strategy": result.get("strategy", "n/a"),
                "size_bytes": size_bytes,
                "severity": "HIGH",
                "detail": f"Response body is {size_bytes} bytes – possible data dump.",
            }]
        return []

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _extract_keys(self, obj: Any) -> Set[str]:
        keys: Set[str] = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                keys.add(k)
                keys.update(self._extract_keys(v))
        elif isinstance(obj, list):
            for item in obj:
                keys.update(self._extract_keys(item))
        return keys

    def _flatten_items(self, obj: Any) -> Dict[str, Any]:
        """Return first occurrence of each key in nested body."""
        items: Dict[str, Any] = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k not in items:
                    items[k] = v
                items.update(self._flatten_items(v))
        elif isinstance(obj, list):
            for item in obj:
                items.update(self._flatten_items(item))
        return items
