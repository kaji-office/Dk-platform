"""
Connector Registry & OAuth Token Manager.

Manages:
 - Instantiation of connectors by name
 - Encrypted OAuth token retrieval from Postgres
 - The adapter registry pattern for future connectors
"""
from __future__ import annotations

import logging
from typing import Any, Type

from workflow_engine.integrations.connectors.base import BaseConnector

logger = logging.getLogger("dk.integrations.registry")

# Registry maps connector name → class
_CONNECTOR_REGISTRY: dict[str, Type[BaseConnector]] = {}


def register_connector(cls: Type[BaseConnector]) -> Type[BaseConnector]:
    """Class decorator to register a connector by its CONNECTOR_NAME."""
    _CONNECTOR_REGISTRY[cls.CONNECTOR_NAME] = cls
    logger.debug(f"Registered connector: {cls.CONNECTOR_NAME}")
    return cls


def get_connector_class(name: str) -> Type[BaseConnector]:
    """Return the connector class for a given name, raising if unknown."""
    if name not in _CONNECTOR_REGISTRY:
        raise KeyError(f"No connector registered for '{name}'. Available: {list(_CONNECTOR_REGISTRY)}")
    return _CONNECTOR_REGISTRY[name]


def list_connectors() -> list[str]:
    """Return all registered connector names."""
    return list(_CONNECTOR_REGISTRY.keys())


class ConnectorFactory:
    """
    Builds and caches connector instances per (tenant_id, connector_name).

    In production, credentials are fetched from the encrypted `oauth_tokens`
    Postgres table where token values are AES-256 encrypted at rest.
    For tests, credentials are passed directly as a dict.
    """

    def __init__(self, credentials_store: Any | None = None) -> None:
        """
        Args:
            credentials_store: Optional async callable `(tenant_id, connector_name) -> dict`
                                that retrieves decrypted credentials from Postgres.
                                If None, credentials must be passed manually.
        """
        self._credentials_store = credentials_store
        self._cache: dict[tuple[str, str], BaseConnector] = {}

    async def get(
        self,
        tenant_id: str,
        connector_name: str,
        credentials: dict[str, Any] | None = None,
    ) -> BaseConnector:
        """Return a connected (and cached) connector instance."""
        cache_key = (tenant_id, connector_name)

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Fetch credentials if not provided
        if credentials is None:
            if self._credentials_store is None:
                raise ValueError("No credentials_store configured and no credentials provided.")
            credentials = await self._credentials_store(tenant_id, connector_name)

        cls = get_connector_class(connector_name)
        connector = cls(tenant_id=tenant_id, credentials=credentials)
        await connector.connect()

        self._cache[cache_key] = connector
        logger.info(f"Connector '{connector_name}' connected for tenant={tenant_id}")
        return connector

    async def close_all(self) -> None:
        """Gracefully close all cached connectors."""
        for connector in self._cache.values():
            await connector.close()
        self._cache.clear()
