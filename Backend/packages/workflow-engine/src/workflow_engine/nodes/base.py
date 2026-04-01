"""
Node Framework Base — NodeOutput, NodeContext, NodeServices, BaseNodeType
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from workflow_engine.ports import CachePort, LLMPort, NotificationPort, StoragePort


@dataclass
class NodeOutput:
    """Result returned by every node execution."""
    outputs: dict[str, Any] = field(default_factory=dict)   # keyed by port name
    metadata: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
    route_to_port: str = "default"


@dataclass
class NodeContext:
    """Runtime context passed into a node during execution."""
    run_id: str
    node_id: str
    tenant_id: str
    input_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)   # shared run-scoped state (SetStateNode)


@dataclass
class NodeServices:
    """Injected platform service dependencies available to every node."""
    llm: LLMPort | None = None
    storage: StoragePort | None = None
    cache: CachePort | None = None
    notification: NotificationPort | None = None
    # Loosely-typed so Layer B never imports Layer C/D concretions
    http_client: Any | None = None        # httpx.AsyncClient factory (for APIRequestNode, WebSearchNode)
    mcp_registry: Any | None = None       # MCPClientRegistry instance (for MCPNode)
    mcp_node_enabled: bool = False        # Feature flag for MCPNode
    serp_api_key: str | None = None       # SerpAPI key (for WebSearchNode)


class BaseNodeType(abc.ABC):
    """Abstract base class that every DK Platform node type must implement."""

    # If False, execution engine skips this node (e.g. NoteNode)
    is_executable: bool = True

    @abc.abstractmethod
    async def execute(
        self,
        config: dict[str, Any],
        context: NodeContext,
        services: NodeServices,
    ) -> NodeOutput:
        """Execute the node logic and return a NodeOutput."""
        ...
