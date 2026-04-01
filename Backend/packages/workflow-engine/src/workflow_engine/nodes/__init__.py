"""
workflow_engine.nodes — public API for all node types.
All 17 nodes are registered in NodeTypeRegistry at import time.
"""
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices
from workflow_engine.nodes.registry import NodeType, NodeTypeRegistry, PortCompatibilityChecker

# AI & Reasoning
from workflow_engine.nodes.implementations.prompt import PromptNode
from workflow_engine.nodes.implementations.agent import AgentNode
from workflow_engine.nodes.implementations.semantic_search import SemanticSearchNode

# Execution & Data
from workflow_engine.nodes.implementations.code_execution import CodeExecutionNode
from workflow_engine.nodes.implementations.api_request import APIRequestNode
from workflow_engine.nodes.implementations.templating import TemplatingNode
from workflow_engine.nodes.implementations.web_search import WebSearchNode
from workflow_engine.nodes.implementations.mcp_node import MCPNode

# Workflow Management
from workflow_engine.nodes.implementations.set_state import SetStateNode
from workflow_engine.nodes.implementations.workflow_management import CustomNode, NoteNode, OutputNode

# Logic & Orchestration
from workflow_engine.nodes.implementations.control_flow import ControlFlowNode
from workflow_engine.nodes.implementations.subworkflow import SubworkflowNode

# Triggers
from workflow_engine.nodes.implementations.triggers import (
    ManualTriggerNode,
    ScheduledTriggerNode,
    IntegrationTriggerNode,
)

# ── Register all 17 nodes ─────────────────────────────────────────────────────
_REGISTRY: list[tuple[NodeType, type[BaseNodeType]]] = [
    (NodeType.PROMPT, PromptNode),
    (NodeType.AGENT, AgentNode),
    (NodeType.SEMANTIC_SEARCH, SemanticSearchNode),
    (NodeType.CODE_EXECUTION, CodeExecutionNode),
    (NodeType.API_REQUEST, APIRequestNode),
    (NodeType.TEMPLATING, TemplatingNode),
    (NodeType.WEB_SEARCH, WebSearchNode),
    (NodeType.MCP, MCPNode),
    (NodeType.SET_STATE, SetStateNode),
    (NodeType.CUSTOM, CustomNode),
    (NodeType.NOTE, NoteNode),
    (NodeType.OUTPUT, OutputNode),
    (NodeType.CONTROL_FLOW, ControlFlowNode),
    (NodeType.SUBWORKFLOW, SubworkflowNode),
    (NodeType.MANUAL_TRIGGER, ManualTriggerNode),
    (NodeType.SCHEDULED_TRIGGER, ScheduledTriggerNode),
    (NodeType.INTEGRATION_TRIGGER, IntegrationTriggerNode),
]

for _node_type, _handler in _REGISTRY:
    NodeTypeRegistry.register(_node_type, _handler)

__all__ = [
    # Base
    "BaseNodeType", "NodeContext", "NodeOutput", "NodeServices",
    # Registry
    "NodeType", "NodeTypeRegistry", "PortCompatibilityChecker",
    # AI & Reasoning
    "PromptNode", "AgentNode", "SemanticSearchNode",
    # Execution & Data
    "CodeExecutionNode", "APIRequestNode", "TemplatingNode", "WebSearchNode", "MCPNode",
    # Workflow Management
    "SetStateNode", "CustomNode", "NoteNode", "OutputNode",
    # Logic & Orchestration
    "ControlFlowNode", "SubworkflowNode",
    # Triggers
    "ManualTriggerNode", "ScheduledTriggerNode", "IntegrationTriggerNode",
]
