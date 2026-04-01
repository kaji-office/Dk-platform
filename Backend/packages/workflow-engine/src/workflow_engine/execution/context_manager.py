"""Manages resolving edge inputs and size limits (>64KB logic)."""
from __future__ import annotations

import json
from typing import Any

from workflow_engine.models import EdgeDefinition, WorkflowDefinition
from workflow_engine.ports import StoragePort


class ContextManager:
    """Manages passing input and output sizes, with offload logic for huge payloads."""

    MAX_INLINE_PAYLOAD_BYTES = 64 * 1024  # 64KB

    def __init__(self, run_id: str, storage: StoragePort | None = None):
        self.run_id = run_id
        self.storage = storage

    async def store_output(self, tenant_id: str, node_id: str, data: Any) -> Any:
        """Stores node output, offloading to StoragePort if it breaches the inline limit."""
        try:
            serialized = json.dumps(data)
        except TypeError:
            serialized = str(data)
            
        byte_len = len(serialized.encode("utf-8"))

        # If data is large and we have storage, store it externally
        if byte_len > self.MAX_INLINE_PAYLOAD_BYTES and self.storage is not None:
            path = f"contexts/{tenant_id}/{self.run_id}/{node_id}_output.json"
            await self.storage.upload(tenant_id, path, serialized.encode("utf-8"))
            return {"__blob": path}

        return data

    async def resolve_inputs(
        self, tenant_id: str, node_id: str, definition: WorkflowDefinition, run_state_outputs: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Gathers inputs required by node_id based on upstream port outputs.
        Looks at the edges array and resolves references.
        """
        inputs: dict[str, Any] = {}
        
        edges: list[EdgeDefinition] = [e for e in definition.edges if e.target_node == node_id]
        
        for edge in edges:
            source_data = run_state_outputs.get(edge.source_node, {})
            # Look at specific port if stated, else merge all outputs
            value = source_data.get(edge.source_port) if edge.source_port else source_data
            
            # De-reference blobs
            if isinstance(value, dict) and "__blob" in value and self.storage:
                raw_bytes = await self.storage.download(tenant_id, value["__blob"])
                value = json.loads(raw_bytes.decode("utf-8"))

            if edge.target_port and edge.target_port != "default":
                inputs[edge.target_port] = value
            else:
                if isinstance(value, dict):
                    inputs.update(value)
                else:
                    inputs["default"] = value

        return inputs
