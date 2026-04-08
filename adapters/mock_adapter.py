"""
Mock API Adapter
Sends real HTTP requests to the locally running mock FastAPI server.
"""

import time
from typing import Any, Dict, List, Optional

import httpx

from .base_adapter import BaseAdapter


class MockAdapter(BaseAdapter):
    """Adapter that talks to the local mock FastAPI server."""

    ENDPOINTS = [
        {"path": "/user",     "method": "GET"},
        {"path": "/messages", "method": "GET"},
        {"path": "/files",    "method": "GET"},
        {"path": "/admin",    "method": "GET"},
        {"path": "/search",   "method": "GET"},
    ]

    def authenticate(self) -> bool:
        try:
            resp = httpx.get(
                f"{self.base_url}/health",
                headers=self._auth_headers(),
                timeout=5,
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"[MockAdapter] Auth failed: {e}")
            return False

    def list_endpoints(self) -> List[Dict[str, Any]]:
        return self.ENDPOINTS

    def send_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        merged_headers = {**self._auth_headers(), **(headers or {})}
        start = time.time()

        try:
            response = httpx.request(
                method=method.upper(),
                url=url,
                headers=merged_headers,
                params=params,
                json=data if method.upper() in ("POST", "PUT", "PATCH") else None,
                timeout=10,
            )
            elapsed_ms = (time.time() - start) * 1000
            try:
                body = response.json()
            except Exception:
                body = response.text

            return {
                "status_code": response.status_code,
                "body": body,
                "headers": dict(response.headers),
                "elapsed_ms": round(elapsed_ms, 2),
                "error": None,
            }

        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000
            return {
                "status_code": 0,
                "body": {},
                "headers": {},
                "elapsed_ms": round(elapsed_ms, 2),
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
