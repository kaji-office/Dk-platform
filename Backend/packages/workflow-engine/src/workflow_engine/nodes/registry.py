"""
NodeTypeRegistry — singleton mapping NodeType enum → handler class.
PortCompatibilityChecker — validates edge connections at save time.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from workflow_engine.errors import WorkflowValidationError
from workflow_engine.nodes.base import BaseNodeType


class NodeType(StrEnum):
    # AI & Reasoning
    PROMPT = "PromptNode"
    AGENT = "AgentNode"
    SEMANTIC_SEARCH = "SemanticSearchNode"
    # Execution & Data
    CODE_EXECUTION = "CodeExecutionNode"
    API_REQUEST = "APIRequestNode"
    TEMPLATING = "TemplatingNode"
    WEB_SEARCH = "WebSearchNode"
    MCP = "MCPNode"
    # Workflow Management
    SET_STATE = "SetStateNode"
    CUSTOM = "CustomNode"
    NOTE = "NoteNode"
    OUTPUT = "OutputNode"
    # Logic & Orchestration
    CONTROL_FLOW = "ControlFlowNode"
    SUBWORKFLOW = "SubworkflowNode"
    # Triggers
    MANUAL_TRIGGER = "ManualTriggerNode"
    SCHEDULED_TRIGGER = "ScheduledTriggerNode"
    INTEGRATION_TRIGGER = "IntegrationTriggerNode"


class NodeTypeRegistry:
    """Singleton registry mapping NodeType → handler class."""
    _registry: dict[NodeType, type[BaseNodeType]] = {}

    @classmethod
    def register(cls, node_type: NodeType, handler: type[BaseNodeType]) -> None:
        cls._registry[node_type] = handler

    @classmethod
    def get(cls, node_type: NodeType) -> type[BaseNodeType]:
        if node_type not in cls._registry:
            raise WorkflowValidationError(f"Unknown node type: {node_type}")
        return cls._registry[node_type]

    @classmethod
    def all_registered(cls) -> dict[NodeType, type[BaseNodeType]]:
        return dict(cls._registry)

    @classmethod
    def is_registered(cls, node_type: NodeType) -> bool:
        return node_type in cls._registry


# Port output type constants used by PortCompatibilityChecker
_PORT_OUTPUT_TYPES: dict[NodeType, list[str]] = {
    NodeType.PROMPT: ["text", "tokens_used"],
    NodeType.AGENT: ["result", "tool_calls"],
    NodeType.SEMANTIC_SEARCH: ["results", "scores"],
    NodeType.CODE_EXECUTION: ["output"],
    NodeType.API_REQUEST: ["status_code", "body", "headers"],
    NodeType.TEMPLATING: ["rendered"],
    NodeType.WEB_SEARCH: ["results"],
    NodeType.MCP: ["result"],
    NodeType.SET_STATE: ["state"],
    NodeType.CUSTOM: ["output"],
    NodeType.NOTE: [],
    NodeType.OUTPUT: ["value"],
    NodeType.CONTROL_FLOW: ["true", "false", "items", "merged"],
    NodeType.SUBWORKFLOW: ["output"],
    NodeType.MANUAL_TRIGGER: ["payload"],
    NodeType.SCHEDULED_TRIGGER: ["payload"],
    NodeType.INTEGRATION_TRIGGER: ["payload"],
}


class PortCompatibilityChecker:
    """Validates that edge connections between nodes are port-compatible."""

    @classmethod
    def check(cls, source_type: str, source_port: str, target_type: str, target_port: str) -> None:
        """
        Raises WorkflowValidationError if an edge connection is incompatible.
        NoteNode has no output ports and cannot be a source.
        """
        try:
            src = NodeType(source_type)
        except ValueError:
            raise WorkflowValidationError(f"Unknown source node type: {source_type}")

        available_ports = _PORT_OUTPUT_TYPES.get(src, [])

        # NoteNode is non-executable and has no output
        if src == NodeType.NOTE:
            raise WorkflowValidationError("NoteNode has no output ports and cannot be a source node")

        # If port list is declared and port is not in it, reject
        if available_ports and source_port not in available_ports and source_port != "default":
            raise WorkflowValidationError(
                f"Port '{source_port}' does not exist on {source_type}. "
                f"Available: {available_ports}"
            )

    @classmethod
    def get_output_ports(cls, node_type: str) -> list[str]:
        try:
            nt = NodeType(node_type)
        except ValueError:
            return []
        return list(_PORT_OUTPUT_TYPES.get(nt, []))
