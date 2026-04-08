"""
Phase 4 – Response Analyzer
Detects unauthorized / hidden data exposure by comparing
actual response fields against expected schema definitions.
"""

from typing import Any, Dict, List, Optional


class ResponseAnalyzer:
    """
    Analyzes API responses to detect:
      1. Hidden / unexpected fields in the response body.
      2. Sensitive fields that should never appear (e.g. ssn, password).
      3. Taint markers present in responses.
    """

    def __init__(self, endpoint_configs: List[Dict[str, Any]]):
        # Build lookup: path → { expected_fields, sensitive_fields }
        self._config: Dict[str, Dict[str, Any]] = {}
        for ep in endpoint_configs:
            path = ep["path"]
            self._config[path] = {
                "expected_fields": set(ep.get("expected_fields", [])),
                "sensitive_fields": set(ep.get("sensitive_fields", [])),
            }

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze(self, fuzzer_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze a list of fuzzer/taint result dicts.
        Returns a list of finding dicts.
        """
        findings = []
        for result in fuzzer_results:
            endpoint = result.get("endpoint", "unknown")
            response = result.get("response", {})
            body = response.get("body", {})
            status = response.get("status_code", 0)

            if status == 0 or response.get("error"):
                continue  # skip connection errors

            cfg = self._config.get(endpoint, {})
            expected = cfg.get("expected_fields", set())
            sensitive = cfg.get("sensitive_fields", set())

            # Flatten all field keys from body
            actual_keys = self._extract_keys(body)

            # Finding 1 – Unexpected fields (not in expected schema)
            if expected:
                unexpected = actual_keys - expected
                if unexpected:
                    findings.append({
                        "type": "UNEXPECTED_FIELDS",
                        "endpoint": endpoint,
                        "strategy": result.get("strategy", "n/a"),
                        "unexpected_fields": sorted(unexpected),
                        "severity": self._severity_for_unexpected(unexpected, sensitive),
                        "detail": f"Response contains {len(unexpected)} field(s) not in expected schema.",
                    })

            # Finding 2 – Sensitive field exposure
            exposed_sensitive = actual_keys & sensitive
            if exposed_sensitive:
                findings.append({
                    "type": "SENSITIVE_FIELD_EXPOSED",
                    "endpoint": endpoint,
                    "strategy": result.get("strategy", "n/a"),
                    "exposed_fields": sorted(exposed_sensitive),
                    "severity": "CRITICAL",
                    "detail": f"Sensitive field(s) {sorted(exposed_sensitive)} directly exposed in response.",
                })

            # Finding 3 – Auth bypass (sensitive data returned on 401/403 request)
            if status in (401, 403) and actual_keys & sensitive:
                findings.append({
                    "type": "AUTH_BYPASS_DATA_LEAK",
                    "endpoint": endpoint,
                    "strategy": result.get("strategy", "n/a"),
                    "exposed_fields": sorted(actual_keys & sensitive),
                    "severity": "CRITICAL",
                    "detail": "Sensitive data returned despite authentication failure.",
                })

        return findings

    def analyze_single(
        self,
        endpoint: str,
        response: Dict[str, Any],
        strategy: str = "manual",
    ) -> List[Dict[str, Any]]:
        """Convenience wrapper to analyze one response dict."""
        return self.analyze([{
            "endpoint": endpoint,
            "strategy": strategy,
            "response": response,
        }])

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _extract_keys(self, obj: Any, prefix: str = "") -> set:
        """Recursively extract all field keys from a nested dict/list."""
        keys = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                keys.add(k)
                keys.update(self._extract_keys(v, prefix=k))
        elif isinstance(obj, list):
            for item in obj:
                keys.update(self._extract_keys(item, prefix=prefix))
        return keys

    def _severity_for_unexpected(self, unexpected: set, sensitive: set) -> str:
        if unexpected & sensitive:
            return "CRITICAL"
        pii_keywords = {"email", "phone", "address", "dob", "name", "ip", "location"}
        if unexpected & pii_keywords:
            return "HIGH"
        return "MEDIUM"
