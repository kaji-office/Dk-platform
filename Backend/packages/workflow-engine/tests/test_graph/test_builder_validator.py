import pytest
from workflow_engine.models import WorkflowDefinition, NodeDefinition, EdgeDefinition
from workflow_engine.graph import GraphBuilder, GraphValidator
from workflow_engine.errors import WorkflowValidationError


def make_workflow(nodes: list[str], edges: list[tuple[str, str]]) -> WorkflowDefinition:
    node_defs = {nid: NodeDefinition(id=nid, type="TriggerNode") for nid in nodes}
    edge_defs = [
        EdgeDefinition(id=f"{s}->{t}", source_node=s, target_node=t)
        for s, t in edges
    ]
    return WorkflowDefinition(id="wf-test", nodes=node_defs, edges=edge_defs)


class TestGraphBuilder:
    def test_build_adjacency_list_simple(self) -> None:
        wf = make_workflow(["a", "b", "c"], [("a", "b"), ("b", "c")])
        adj = GraphBuilder.build_adjacency_list(wf)
        assert adj == {"a": ["b"], "b": ["c"], "c": []}

    def test_build_adjacency_list_parallel(self) -> None:
        wf = make_workflow(["start", "left", "right"], [("start", "left"), ("start", "right")])
        adj = GraphBuilder.build_adjacency_list(wf)
        assert set(adj["start"]) == {"left", "right"}

    def test_topological_sort_linear(self) -> None:
        wf = make_workflow(["a", "b", "c"], [("a", "b"), ("b", "c")])
        order = GraphBuilder.topological_sort(wf)
        assert order.index("a") < order.index("b") < order.index("c")

    def test_topological_sort_parallel_branches(self) -> None:
        wf = make_workflow(
            ["start", "left", "right", "end"],
            [("start", "left"), ("start", "right"), ("left", "end"), ("right", "end")],
        )
        order = GraphBuilder.topological_sort(wf)
        assert order.index("start") < order.index("left")
        assert order.index("start") < order.index("right")
        assert order.index("left") < order.index("end")
        assert order.index("right") < order.index("end")

    def test_topological_sort_single_node(self) -> None:
        wf = make_workflow(["only"], [])
        order = GraphBuilder.topological_sort(wf)
        assert order == ["only"]


class TestGraphValidator:
    def test_valid_linear_graph(self) -> None:
        wf = make_workflow(["a", "b", "c"], [("a", "b"), ("b", "c")])
        # Should not raise
        GraphValidator.validate(wf)

    def test_cycle_detection_simple_cycle(self) -> None:
        wf = make_workflow(["a", "b"], [("a", "b"), ("b", "a")])
        with pytest.raises(WorkflowValidationError, match="Cycle detected"):
            GraphValidator.check_cycles(wf)

    def test_cycle_detection_self_loop(self) -> None:
        wf = make_workflow(["a"], [("a", "a")])
        with pytest.raises(WorkflowValidationError, match="Cycle detected"):
            GraphValidator.check_cycles(wf)

    def test_cycle_detection_longer_cycle(self) -> None:
        wf = make_workflow(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")])
        with pytest.raises(WorkflowValidationError, match="Cycle detected"):
            GraphValidator.check_cycles(wf)

    def test_invalid_edge_source(self) -> None:
        node_defs = {"a": NodeDefinition(id="a", type="TriggerNode")}
        edge_defs = [EdgeDefinition(id="e1", source_node="nonexistent", target_node="a")]
        wf = WorkflowDefinition(id="wf-test", nodes=node_defs, edges=edge_defs)
        with pytest.raises(WorkflowValidationError, match="non-existent source_node"):
            GraphValidator.validate_nodes_exist(wf)

    def test_invalid_edge_target(self) -> None:
        node_defs = {"a": NodeDefinition(id="a", type="TriggerNode")}
        edge_defs = [EdgeDefinition(id="e1", source_node="a", target_node="nonexistent")]
        wf = WorkflowDefinition(id="wf-test", nodes=node_defs, edges=edge_defs)
        with pytest.raises(WorkflowValidationError, match="non-existent target_node"):
            GraphValidator.validate_nodes_exist(wf)

    def test_dag_no_cycle(self) -> None:
        wf = make_workflow(
            ["trigger", "llm", "condition", "slack", "email"],
            [
                ("trigger", "llm"),
                ("llm", "condition"),
                ("condition", "slack"),
                ("condition", "email"),
            ],
        )
        # Should not raise
        GraphValidator.validate(wf)
