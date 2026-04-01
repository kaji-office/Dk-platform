"""
BaseConnector — abstract port for all REST/API connectors.
Every connector in the platform must implement this interface.
"""
from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx


class ConnectorAuthError(Exception):
    """Raised when connector credentials are missing or invalid."""


class ConnectorRequestError(Exception):
    """Raised when the remote API returns a non-success response."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body[:200]}")


class BaseConnector(ABC):
    """
    Abstract base class for all platform connectors.

    Each connector:
    - Holds a pre-configured httpx.AsyncClient for the target service.
    - Shares tenant_id scoping to prevent cross-tenant token leakage.
    - Must implement `check_health()` to verify connectivity at startup.

    OAuth / API-key tokens are retrieved from the encrypted `oauth_tokens`
    store (Postgres) and never stored in plaintext on the connector object.
    """

    #: Each subclass declares its unique connector name (e.g. "slack")
    CONNECTOR_NAME: str = "base"

    def __init__(self, tenant_id: str, credentials: dict[str, Any]) -> None:
        self.tenant_id = tenant_id
        self._credentials = credentials          # Always encrypted-at-rest in DB
        self._client: httpx.AsyncClient | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Initialise the underlying HTTP client."""
        self._client = self._build_client()

    async def close(self) -> None:
        """Tear down the HTTP client gracefully."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_client(self) -> httpx.AsyncClient:
        """Override to customise headers, base URLs, or timeouts."""
        return httpx.AsyncClient(timeout=30)

    # ── Abstract interface ─────────────────────────────────────────────────

    @abstractmethod
    async def check_health(self) -> bool:
        """Verify the connector can reach its target service."""

    # ── Helpers ────────────────────────────────────────────────────────────

    def _require(self, key: str) -> str:
        """Fetch a required credential, raising ConnectorAuthError if absent."""
        val = self._credentials.get(key)
        if not val:
            raise ConnectorAuthError(
                f"Connector '{self.CONNECTOR_NAME}' missing required credential: '{key}'"
            )
        return str(val)

    async def _get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        assert self._client, "Call connect() first"
        resp = await self._client.get(url, **kwargs)
        if not resp.is_success:
            raise ConnectorRequestError(resp.status_code, resp.text)
        return resp.json()

    async def _post(self, url: str, **kwargs: Any) -> dict[str, Any]:
        assert self._client, "Call connect() first"
        resp = await self._client.post(url, **kwargs)
        if not resp.is_success:
            raise ConnectorRequestError(resp.status_code, resp.text)
        return resp.json()

    async def _patch(self, url: str, **kwargs: Any) -> dict[str, Any]:
        assert self._client, "Call connect() first"
        resp = await self._client.patch(url, **kwargs)
        if not resp.is_success:
            raise ConnectorRequestError(resp.status_code, resp.text)
        return resp.json()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} tenant={self.tenant_id}>"
