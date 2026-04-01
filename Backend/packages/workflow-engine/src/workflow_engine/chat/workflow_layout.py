from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict

class NodeCategory(str, Enum):
    AI_REASONING = "ai_reasoning"
    EXECUTION_DATA = "execution_data"
    WORKFLOW_MANAGEMENT = "workflow_management"
    LOGIC_ORCHESTRATION = "logic_orchestration"
    TRIGGERS = "triggers"

class NodeUIConfig(BaseModel):
    node_type_label: str
    icon: str
    color: str
    category: NodeCategory
    is_terminal: bool
    editable: bool
    
    model_config = ConfigDict(use_enum_values=True)

class NodeUIConfigFactory:
    """Pre-defined ui_config registry for all node types"""
    _config_map: dict[str, NodeUIConfig] = {
        "PromptNode": NodeUIConfig(node_type_label="AI Prompt", icon="sparkles", color="#6366f1", category=NodeCategory.AI_REASONING, is_terminal=False, editable=True),
        "AgentNode": NodeUIConfig(node_type_label="AI Agent", icon="cpu", color="#8b5cf6", category=NodeCategory.AI_REASONING, is_terminal=False, editable=True),
        "SemanticSearchNode": NodeUIConfig(node_type_label="Semantic Search", icon="search", color="#a855f7", category=NodeCategory.AI_REASONING, is_terminal=False, editable=True),
        "CodeExecutionNode": NodeUIConfig(node_type_label="Run Code", icon="code", color="#f59e0b", category=NodeCategory.EXECUTION_DATA, is_terminal=False, editable=True),
        "APIRequestNode": NodeUIConfig(node_type_label="HTTP Request", icon="globe", color="#3b82f6", category=NodeCategory.EXECUTION_DATA, is_terminal=False, editable=True),
        "TemplatingNode": NodeUIConfig(node_type_label="Template", icon="file-text", color="#06b6d4", category=NodeCategory.EXECUTION_DATA, is_terminal=False, editable=True),
        "WebSearchNode": NodeUIConfig(node_type_label="Web Search", icon="search-check", color="#0ea5e9", category=NodeCategory.EXECUTION_DATA, is_terminal=False, editable=True),
        "MCPNode": NodeUIConfig(node_type_label="MCP Tool", icon="plug", color="#64748b", category=NodeCategory.EXECUTION_DATA, is_terminal=False, editable=True),
        "SetStateNode": NodeUIConfig(node_type_label="Set State", icon="database", color="#10b981", category=NodeCategory.WORKFLOW_MANAGEMENT, is_terminal=False, editable=True),
        "CustomNode": NodeUIConfig(node_type_label="Custom", icon="wrench", color="#84cc16", category=NodeCategory.WORKFLOW_MANAGEMENT, is_terminal=False, editable=True),
        "NoteNode": NodeUIConfig(node_type_label="Note", icon="sticky-note", color="#e2e8f0", category=NodeCategory.WORKFLOW_MANAGEMENT, is_terminal=False, editable=False),
        "OutputNode": NodeUIConfig(node_type_label="Output", icon="arrow-right-circle", color="#14b8a6", category=NodeCategory.WORKFLOW_MANAGEMENT, is_terminal=True, editable=True),
        "ControlFlowNode": NodeUIConfig(node_type_label="Control Flow", icon="git-branch", color="#f97316", category=NodeCategory.LOGIC_ORCHESTRATION, is_terminal=False, editable=True),
        "SubworkflowNode": NodeUIConfig(node_type_label="Sub-Workflow", icon="layers", color="#ec4899", category=NodeCategory.LOGIC_ORCHESTRATION, is_terminal=False, editable=True),
        "ManualTriggerNode": NodeUIConfig(node_type_label="Manual Trigger", icon="play", color="#22c55e", category=NodeCategory.TRIGGERS, is_terminal=True, editable=True),
        "ScheduledTriggerNode": NodeUIConfig(node_type_label="Scheduled", icon="clock", color="#22c55e", category=NodeCategory.TRIGGERS, is_terminal=True, editable=True),
        "IntegrationTriggerNode": NodeUIConfig(node_type_label="Webhook", icon="zap", color="#22c55e", category=NodeCategory.TRIGGERS, is_terminal=True, editable=True),
    }

    @classmethod
    def for_type(cls, node_type: str) -> NodeUIConfig:
        return cls._config_map.get(
            node_type, 
            NodeUIConfig(node_type_label=node_type, icon="box", color="#cccccc", category=NodeCategory.WORKFLOW_MANAGEMENT, is_terminal=False, editable=True)
        )

from workflow_engine.models import WorkflowDefinition
from workflow_engine.graph.builder import GraphBuilder

class WorkflowLayoutEngine:
    """Layout engine providing strict BFS layer based assignments."""
    @staticmethod
    def auto_layout(workflow: WorkflowDefinition) -> WorkflowDefinition:
        """
        Assigns topological layered layout:
        Layer spacing: 280px horizontal, 150px vertical between siblings
        """
        # We need in-degree to find roots
        adj = GraphBuilder.build_adjacency_list(workflow)
        in_degree = dict.fromkeys(workflow.nodes, 0)

        for edge in workflow.edges:
            if edge.target_node in in_degree:
                in_degree[edge.target_node] += 1
                
        # BFS assigning layers
        queue = [node_id for node_id, deg in in_degree.items() if deg == 0]
        layer = {n: 0 for n in queue}
        
        while queue:
            node = queue.pop(0)
            for neighbor in adj.get(node, []):
                # Update layer to the max (pushing it rightest possible)
                if neighbor in layer:
                    layer[neighbor] = max(layer[neighbor], layer[node] + 1)
                else:
                    layer[neighbor] = layer[node] + 1
                    
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        # Map nodes to layers
        layer_to_nodes: dict[int, list[str]] = {}
        for n, l in layer.items():
            if l not in layer_to_nodes:
                layer_to_nodes[l] = []
            layer_to_nodes[l].append(n)
            
        # Draw positions
        for l, nodes in layer_to_nodes.items():
            base_x = l * 280.0
            
            # Center the vertical stack around y=0
            total = len(nodes)
            start_y = -((total - 1) * 150.0) / 2.0
            
            for idx, node_id in enumerate(nodes):
                workflow.nodes[node_id].position = {
                    "x": base_x,
                    "y": start_y + (idx * 150.0)
                }
                
        if not hasattr(workflow, "ui_metadata"):
            workflow.ui_metadata = {}
        workflow.ui_metadata["layout"] = "auto"
                
        return workflow
