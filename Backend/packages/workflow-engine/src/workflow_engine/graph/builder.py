from workflow_engine.models import WorkflowDefinition
from workflow_engine.nodes.registry import PortCompatibilityChecker
from workflow_engine.errors import WorkflowValidationError
class GraphBuilder:
    @staticmethod
    def build_adjacency_list(workflow: WorkflowDefinition) -> dict[str, list[str]]:
        """Returns adjacency list of node_id -> list of target_node_ids"""
        adj: dict[str, list[str]] = {node_id: [] for node_id in workflow.nodes}
        for edge in workflow.edges:
            if edge.source_node in adj:
                adj[edge.source_node].append(edge.target_node)
        return adj

    @staticmethod
    def topological_sort(workflow: WorkflowDefinition) -> list[str]:
        """
        Returns a topologically sorted list of node IDs.
        Raises ValueError if a cycle is detected (though validator should catch this).
        """
        adj = GraphBuilder.build_adjacency_list(workflow)
        in_degree = dict.fromkeys(workflow.nodes, 0)

        for edge in workflow.edges:
            if edge.target_node in in_degree:
                in_degree[edge.target_node] += 1

        queue = [node_id for node_id, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj.get(node, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        if len(result) != len(workflow.nodes):
            raise ValueError("Graph contains a cycle or invalid nodes")

        return result

    @staticmethod
    def topological_layers(workflow: WorkflowDefinition) -> list[list[str]]:
        """
        Groups nodes by topological layer for concurrent execution.
        Returns a list of lists of node IDs, e.g., [[root1, root2], [child1], [child2]].
        """
        adj = GraphBuilder.build_adjacency_list(workflow)
        in_degree = dict.fromkeys(workflow.nodes, 0)
        
        for edge in workflow.edges:
            if edge.target_node in in_degree:
                in_degree[edge.target_node] += 1
                
        layers = []
        queue = [n for n, d in in_degree.items() if d == 0]
        
        while queue:
            layers.append(queue)
            next_queue = []
            for node in queue:
                for neighbor in adj.get(node, []):
                    if neighbor in in_degree:
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            next_queue.append(neighbor)
            queue = next_queue
            
        return layers

    @staticmethod
    def validate(workflow: WorkflowDefinition) -> None:
        """
        Validates a workflow schema.
        Raises WorkflowValidationError if issues like cycles or port mismatches are found.
        """
        # Validate acyclic property
        try:
            GraphBuilder.topological_sort(workflow)
        except ValueError:
            raise WorkflowValidationError("Workflow graph contains a cycle.")
            
        # Validate node port compatibility
        for edge in workflow.edges:
            if edge.source_node not in workflow.nodes:
                raise WorkflowValidationError(f"Edge references invalid source node: {edge.source_node}")
            if edge.target_node not in workflow.nodes:
                raise WorkflowValidationError(f"Edge references invalid target node: {edge.target_node}")
                
            source_type = workflow.nodes[edge.source_node].type
            target_type = workflow.nodes[edge.target_node].type
            
            PortCompatibilityChecker.check(
                source_type=source_type,
                source_port=edge.source_port,
                target_type=target_type,
                target_port=edge.target_port
            )

