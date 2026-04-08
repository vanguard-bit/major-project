"""
Base Adapter Interface
All API adapters must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseAdapter(ABC):
    """Abstract base class for API adapters."""

    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the API. Returns True if successful."""
        pass

    @abstractmethod
    def list_endpoints(self) -> List[Dict[str, Any]]:
        """Return list of available endpoints as dicts with 'path' and 'method'."""
        pass

    @abstractmethod
    def send_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send an HTTP request to the adapter's target API.

        Returns a dict with:
          - status_code (int)
          - body (dict or str)
          - headers (dict)
          - elapsed_ms (float)
          - error (str or None)
        """
        pass
