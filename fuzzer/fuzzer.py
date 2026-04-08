"""
Phase 2 – Differential API Fuzzer
Generates and mutates API requests across all configured endpoints.
"""

import random
import string
import uuid
from typing import Any, Dict, List, Optional

from adapters.base_adapter import BaseAdapter


# ── Mutation helpers ───────────────────────────────────────────────────────────

def _random_string(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

def _random_int(lo: int = -9999, hi: int = 99999) -> int:
    return random.randint(lo, hi)

def _random_bool() -> bool:
    return random.choice([True, False])

def _invalid_tokens() -> List[str]:
    return [
        "",
        "null",
        "undefined",
        "' OR '1'='1",
        "<script>alert(1)</script>",
        "../../../etc/passwd",
        "A" * 500,
        str(uuid.uuid4()),
    ]


class Fuzzer:
    """
    Generates mutated HTTP requests for a list of endpoints and records
    each request + raw response for downstream analysis.
    """

    def __init__(
        self,
        adapter: BaseAdapter,
        endpoints: List[Dict[str, Any]],
        iterations: int = 5,
        strategies: Optional[List[str]] = None,
    ):
        self.adapter = adapter
        self.endpoints = endpoints
        self.iterations = iterations
        self.strategies = strategies or [
            "add_random_fields",
            "remove_required_fields",
            "inject_invalid_tokens",
            "boundary_values",
            "baseline",
        ]

    def run(self) -> List[Dict[str, Any]]:
        """Run fuzzing across all endpoints × iterations. Returns result list."""
        results = []
        for ep in self.endpoints:
            path = ep["path"]
            method = ep.get("method", "GET")

            for iteration in range(self.iterations):
                strategy = self.strategies[iteration % len(self.strategies)]
                params, data, extra_headers = self._mutate(strategy)

                response = self.adapter.send_request(
                    endpoint=path,
                    method=method,
                    data=data,
                    headers=extra_headers,
                    params=params,
                )

                results.append({
                    "endpoint": path,
                    "method": method,
                    "iteration": iteration + 1,
                    "strategy": strategy,
                    "params": params,
                    "data": data,
                    "extra_headers": extra_headers,
                    "response": response,
                })

        return results

    # ── Mutation strategies ────────────────────────────────────────────────────

    def _mutate(self, strategy: str):
        params: Dict[str, Any] = {}
        data: Dict[str, Any] = {}
        headers: Dict[str, str] = {}

        if strategy == "baseline":
            pass  # no mutation – clean request

        elif strategy == "add_random_fields":
            for _ in range(random.randint(1, 4)):
                params[_random_string(5)] = _random_string(8)

        elif strategy == "remove_required_fields":
            # Send request with intentionally empty / missing payload
            data = {}

        elif strategy == "inject_invalid_tokens":
            token = random.choice(_invalid_tokens())
            headers["Authorization"] = f"Bearer {token}"

        elif strategy == "boundary_values":
            params["q"] = random.choice([
                "",
                " ",
                "\x00",
                "A" * 10000,
                "0",
                str(_random_int()),
                "null",
                "true",
                "✓∆˜¬",
            ])

        return params, data, headers
