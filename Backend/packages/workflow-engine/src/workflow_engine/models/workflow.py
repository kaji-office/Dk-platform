from typing import Any

from pydantic import BaseModel, Field


class NodeDefinition(BaseModel):
    id: str = Field(..., description="Unique identifier for the node")
    type: str = Field(..., description="Type of the node (e.g., LLMNode, TransformNode)")
    config: dict[str, Any] = Field(default_factory=dict, description="Configuration parameters for the node")
    position: dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0},
        description="X/Y coordinates for the canvas"
    )

class EdgeDefinition(BaseModel):
    id: str = Field(..., description="Unique identifier for the edge")
    source_node: str = Field(..., description="Source node ID")
    target_node: str = Field(..., description="Target node ID")
    source_port: str = Field(default="default", description="Output port on the source node")
    target_port: str = Field(default="default", description="Input port on the target node")

class WorkflowDefinition(BaseModel):
    id: str = Field(..., description="Unique identifier for the workflow")
    name: str = Field(default="Untitled Workflow", description="Name of the workflow")
    description: str | None = Field(default=None, description="Human-readable description")
    nodes: dict[str, NodeDefinition] = Field(
        default_factory=dict,
        description="Map of node ID to NodeDefinition"
    )
    edges: list[EdgeDefinition] = Field(
        default_factory=list,
        description="List of edges connecting the nodes"
    )
    ui_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Frontend canvas layout states"
    )
