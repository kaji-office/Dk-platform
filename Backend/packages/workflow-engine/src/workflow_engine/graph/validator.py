from workflow_engine.errors import WorkflowValidationError
from workflow_engine.models import WorkflowDefinition

from .builder import GraphBuilder


class GraphValidator:
    @staticmethod
    def validate(workflow: WorkflowDefinition) -> None:
        """Runs all validations on the workflow graph."""
        GraphValidator.validate_nodes_exist(workflow)
        GraphValidator.check_cycles(workflow)
        # Port compatibility can be validated here or at runtime during execution

    @staticmethod
    def check_cycles(workflow: WorkflowDefinition) -> None:
        """Detects cycles using DFS. Raises WorkflowValidationError if cycle found."""
        adj = GraphBuilder.build_adjacency_list(workflow)
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for neighbor in adj.get(node_id, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node in workflow.nodes:
            if node not in visited and dfs(node):
                raise WorkflowValidationError(f"Cycle detected involving node {node}")

    @staticmethod
    def validate_nodes_exist(workflow: WorkflowDefinition) -> None:
        """Verifies that all edges reference valid node IDs."""
        for edge in workflow.edges:
            if edge.source_node not in workflow.nodes:
                raise WorkflowValidationError(f"Edge {edge.id} references non-existent source_node: {edge.source_node}")
            if edge.target_node not in workflow.nodes:
                raise WorkflowValidationError(f"Edge {edge.id} references non-existent target_node: {edge.target_node}")
