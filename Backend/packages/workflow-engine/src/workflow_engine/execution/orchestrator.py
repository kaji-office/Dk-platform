"""Execution Run Orchestrator."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from workflow_engine.errors import NodeExecutionError, PIIBlockedError, SandboxTimeoutError
from workflow_engine.execution.context_manager import ContextManager
from workflow_engine.execution.pii_scanner import PIIScanner
from workflow_engine.execution.retry_timeout import RetryConfig, RetryHandler, TimeoutManager
from workflow_engine.execution.state_machine import StateMachine
from workflow_engine.graph.builder import GraphBuilder
from workflow_engine.models.execution import ExecutionRun, NodeExecutionState, RunStatus
from workflow_engine.models.tenant import TenantConfig
from workflow_engine.models.workflow import NodeDefinition, WorkflowDefinition
from workflow_engine.nodes import NodeContext, NodeServices, NodeTypeRegistry
from workflow_engine.nodes.registry import NodeType
from workflow_engine.observability.tracing import trace_workflow
from workflow_engine.ports import ExecutionRepository

logger = logging.getLogger(__name__)


class RunOrchestrator:
    """Orchestrates workflow execution, navigating the Graph and executing Nodes."""

    def __init__(self, repo: ExecutionRepository, services: NodeServices, config: TenantConfig):
        self.repo = repo
        self.services = services
        self.config = config

    @trace_workflow
    async def run(
        self,
        workflow_def: WorkflowDefinition,
        run_id: str,
        tenant_id: str,
        trigger_input: dict[str, Any],
        max_depth: int = 5,
        current_depth: int = 0
    ) -> ExecutionRun | None:
        """Main entrypoint for 26-step DAG traversal."""
        if current_depth > max_depth:
            raise NodeExecutionError("system", f"Max runtime depth {max_depth} exceeded")

        topo_sort = GraphBuilder.topological_sort(workflow_def)
        topo_layers = GraphBuilder.topological_layers(workflow_def)
        ctx_manager = ContextManager(run_id, self.services.storage)
        run = await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.RUNNING)

        entry_node = topo_sort[0] if topo_sort else None
        if not entry_node:
            await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.SUCCESS)
            return await self.repo.get(tenant_id, run_id)

        outputs: dict[str, dict[str, Any]] = {}

        async def _process_node(node_id: str) -> ExecutionRun | bool:
            """
            Process a single node. Returns:
            - ExecutionRun object if run should terminate early (error or terminal node).
            - False if skipped or cancelled.
            - True if completed successfully.
            """
            run_state = await self.repo.get(tenant_id, run_id)
            if not run_state or run_state.status == RunStatus.CANCELLED:
                logger.info(f"Run {run_id} cancelled.")
                return False

            node_def: NodeDefinition = self._get_node_def(workflow_def, node_id)
            node_cls = NodeTypeRegistry.get(NodeType(node_def.type))
            node_impl = node_cls()

            if not node_impl.is_executable:
                return False

            if node_id == entry_node and current_depth == 0:
                inputs = trigger_input
            else:
                inputs = await ctx_manager.resolve_inputs(tenant_id, node_id, workflow_def, outputs)

            # PII
            try:
                PIIScanner.scan_dict(inputs, self.config)
            except PIIBlockedError as exc:
                await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.FAILED)
                await StateMachine.transition_node(self.repo, tenant_id, run_id, node_id, RunStatus.FAILED, error={"message": str(exc)})
                return await self.repo.get(tenant_id, run_id) or False

            await StateMachine.transition_node(self.repo, tenant_id, run_id, node_id, RunStatus.RUNNING)

            async def _execute_loop() -> Any:
                context = NodeContext(run_id=run_id, node_id=node_id, tenant_id=tenant_id, input_data=inputs)
                out = await node_impl.execute(node_def.config, context, self.services)
                return out

            try:
                timeout = int(node_def.config.get("timeout_seconds", 30))
                retries = int(node_def.config.get("max_retries", 1))

                async def _attempt() -> Any:
                    return await TimeoutManager.wrap(_execute_loop(), timeout, node_id)

                rc = RetryConfig(max_attempts=retries)
                result = await RetryHandler.execute_with_retry(_attempt, rc)

                out_payload = result.outputs
                PIIScanner.scan_dict(out_payload, self.config)
                outputs[node_id] = out_payload

                await StateMachine.transition_node(self.repo, tenant_id, run_id, node_id, RunStatus.SUCCESS, outputs=out_payload)

                if result.metadata.get("terminal"):
                    run_state = await self.repo.get(tenant_id, run_id)
                    if run_state:
                        run_state.output_data = out_payload
                        await self.repo.update_state(tenant_id, run_id, run_state)
                    return await self.repo.get(tenant_id, run_id) or False

                # Handle WAITING_HUMAN correctly
                if result.metadata.get("status") == RunStatus.WAITING_HUMAN.value:
                    await StateMachine.transition_node(self.repo, tenant_id, run_id, node_id, RunStatus.WAITING_HUMAN, outputs=out_payload)
                    await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.WAITING_HUMAN)
                    return await self.repo.get(tenant_id, run_id) or False

            except SandboxTimeoutError as exc:
                await StateMachine.transition_node(self.repo, tenant_id, run_id, node_id, RunStatus.FAILED, error={"message": str(exc)})
                await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.FAILED)
                return await self.repo.get(tenant_id, run_id) or False
            except NodeExecutionError as exc:
                await StateMachine.transition_node(self.repo, tenant_id, run_id, node_id, RunStatus.FAILED, error={"message": str(exc)})
                await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.FAILED)
                return await self.repo.get(tenant_id, run_id) or False
            except Exception as exc:
                await StateMachine.transition_node(self.repo, tenant_id, run_id, node_id, RunStatus.FAILED, error={"message": str(exc)})
                await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.FAILED)
                return await self.repo.get(tenant_id, run_id) or False

            return True

        for layer in topo_layers:
            results = await asyncio.gather(*[_process_node(node_id) for node_id in layer])
            for res in results:
                if isinstance(res, ExecutionRun):
                    # A terminal node, failure, or wait_human occurred. Return immediately.
                    return res

        # Finished DAG natively
        final_run = await self.repo.get(tenant_id, run_id)
        if final_run and final_run.status == RunStatus.RUNNING:
            final_run.output_data = outputs.get(topo_sort[-1]) or {}
            await self.repo.update_state(tenant_id, run_id, final_run)
            await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.SUCCESS)

        return await self.repo.get(tenant_id, run_id)

    async def cancel(self, tenant_id: str, run_id: str) -> None:
        """Cancel a running workflow gracefully."""
        await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.CANCELLED)

    @trace_workflow
    async def resume(self, tenant_id: str, run_id: str, node_id: str, workflow_def: WorkflowDefinition, human_response: dict[str, Any]) -> ExecutionRun | None:
        """Resume execution from a human input gate natively via graph traversal."""
        run = await self.repo.get(tenant_id, run_id)
        if not run or run.status != RunStatus.WAITING_HUMAN:
            raise NodeExecutionError(node_id, f"Run {run_id} is not waiting for human input.")

        # Accept the human payload successfully
        await StateMachine.transition_node(self.repo, tenant_id, run_id, node_id, RunStatus.SUCCESS, outputs=human_response)
        await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.RUNNING)

        # Build a sub-workflow of all descendants from node_id
        # We recursively find descendants to run sequentially or concurrently
        adj = GraphBuilder.build_adjacency_list(workflow_def)
        visited = set()
        queue = [node_id]
        while queue:
            curr = queue.pop(0)
            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # Create a transient sub-workflow with just the remaining nodes
        nodes_to_run = list(visited)
        if not nodes_to_run:
            # Reached terminal state with no ongoing nodes
            run = await self.repo.get(tenant_id, run_id)
            if run:
                await StateMachine.transition_run(self.repo, tenant_id, run_id, RunStatus.SUCCESS)
            return run

        # We construct a limited graph
        remaining_nodes = {nid: workflow_def.nodes[nid] for nid in nodes_to_run}
        remaining_edges = [edge for edge in workflow_def.edges if edge.source_node in remaining_nodes and edge.target_node in remaining_nodes]
        sub_workflow = WorkflowDefinition(
            id=workflow_def.id,
            nodes=remaining_nodes,
            edges=remaining_edges
        )
        
        # Dispatch sub-workflow natively via recursion layer (avoid infinite recursion via current_depth)
        return await self.run(sub_workflow, run_id, tenant_id, {}, current_depth=1)

    def _get_node_def(self, definition: WorkflowDefinition, node_id: str) -> NodeDefinition:
        node = definition.nodes.get(node_id)
        if not node:
            raise NodeExecutionError(node_id, f"Node {node_id} omitted from workflow {definition.id}")
        return node
