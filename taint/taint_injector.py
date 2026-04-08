"""
Phase 3 – Taint Injection Module
Injects identifiable synthetic markers into API requests and tracks them
across all responses to detect data leakage.
"""

import uuid
from typing import Any, Dict, List, Optional

from adapters.base_adapter import BaseAdapter


class TaintInjector:
    """
    Injects tainted (synthetic, traceable) values into API requests
    and records whether those values appear in responses from OTHER endpoints.
    """

    def __init__(
        self,
        adapter: BaseAdapter,
        endpoints: List[Dict[str, Any]],
        taint_fields: Optional[List[str]] = None,
        marker_prefix: str = "TAINT",
    ):
        self.adapter = adapter
        self.endpoints = endpoints
        self.taint_fields = taint_fields or ["email", "username", "phone"]
        self.marker_prefix = marker_prefix

        # Registry: taint_id → { field, value, injected_at }
        self._registry: Dict[str, Dict[str, Any]] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def generate_tainted_payload(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build a dict of tainted field values and register each taint marker."""
        payload: Dict[str, Any] = {}
        for field in self.taint_fields:
            taint_id = f"{self.marker_prefix}_{uuid.uuid4().hex[:8].upper()}"
            value = self._make_value(field, taint_id)
            payload[field] = value
            self._registry[taint_id] = {
                "field": field,
                "value": value,
                "injected_in": [],  # populated during injection
            }
        if extra:
            payload.update(extra)
        return payload

    def inject_and_collect(self) -> List[Dict[str, Any]]:
        """
        Send one tainted request per endpoint, record the full
        (taint_id, endpoint, response) triples.
        """
        results = []
        for ep in self.endpoints:
            path = ep["path"]
            method = ep.get("method", "GET")

            payload = self.generate_tainted_payload()
            taint_ids = list(self._registry.keys())[-len(self.taint_fields):]

            # Record which endpoint each taint was injected into
            for tid in taint_ids:
                self._registry[tid]["injected_in"].append(path)

            response = self.adapter.send_request(
                endpoint=path,
                method=method,
                params=payload if method == "GET" else None,
                data=payload if method != "GET" else None,
            )

            results.append({
                "endpoint": path,
                "method": method,
                "taint_ids": taint_ids,
                "payload": payload,
                "response": response,
            })

        return results

    def scan_responses_for_taint(
        self, all_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Scan every response body for any registered taint marker.
        Returns a list of leak findings.
        """
        leaks = []

        for result in all_results:
            body_str = self._flatten_to_str(result.get("response", {}).get("body", ""))
            endpoint = result.get("endpoint", "unknown")

            for taint_id, meta in self._registry.items():
                # A leak = taint value appears in a response from a different endpoint,
                # OR appears in query responses at all (since taint was sent as input)
                if meta["value"] in body_str:
                    # Check if it appears outside the endpoint where it was injected
                    is_unexpected = endpoint not in meta.get("injected_in", [])
                    leaks.append({
                        "taint_id": taint_id,
                        "field": meta["field"],
                        "value": meta["value"],
                        "found_in_endpoint": endpoint,
                        "injected_in": meta.get("injected_in", []),
                        "unexpected": is_unexpected,
                        "severity": "HIGH" if is_unexpected else "LOW",
                    })

        return leaks

    @property
    def registry(self) -> Dict[str, Dict[str, Any]]:
        return self._registry

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_value(self, field: str, taint_id: str) -> str:
        templates = {
            "email":    f"test+{taint_id}@taintdemo.com",
            "username": f"user_{taint_id}",
            "phone":    f"+1-555-{taint_id[:4]}-{taint_id[4:8]}",
        }
        return templates.get(field, f"{taint_id}_value")

    def _flatten_to_str(self, obj: Any) -> str:
        """Recursively convert any object to a single searchable string."""
        if isinstance(obj, str):
            return obj
        if isinstance(obj, (int, float, bool)):
            return str(obj)
        if isinstance(obj, dict):
            return " ".join(self._flatten_to_str(v) for v in obj.values())
        if isinstance(obj, list):
            return " ".join(self._flatten_to_str(i) for i in obj)
        return str(obj)
