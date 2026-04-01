"""ControlFlowNode — unified BRANCH, SWITCH, LOOP, MERGE sub-modes."""
from __future__ import annotations

from typing import Any, Callable

import jmespath  # type: ignore[import-untyped]

from workflow_engine.errors import NodeExecutionError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "contains": lambda a, b: b in a,
    "not_contains": lambda a, b: b not in a,
    "is_empty": lambda a, _: not a,
    "is_not_empty": lambda a, _: bool(a),
}


def _resolve(data: dict[str, Any], path: str) -> Any:
    keys = path.split(".")
    val: Any = data
    for k in keys:
        val = val.get(k) if isinstance(val, dict) else None
    return val


def _eval_condition(rule: dict[str, Any], data: dict[str, Any]) -> bool:
    op_fn = _OPS.get(str(rule.get("operator", "eq")))
    if op_fn is None:
        raise ValueError(f"Unknown operator: {rule.get('operator')}")
    return bool(op_fn(_resolve(data, str(rule.get("field", ""))), rule.get("value")))


class ControlFlowNode(BaseNodeType):
    """
    Unified control-flow node with four sub-modes:
    - BRANCH: if/else routing
    - SWITCH: multi-way routing
    - LOOP: fan-out over a list (jmespath)
    - MERGE: fan-in passthrough

    Config:
        mode (str): BRANCH | SWITCH | LOOP | MERGE
        --- BRANCH ---
        rules (list): [{field, operator, value, target_port}]
        default_branch (str): port if no rule matches
        --- SWITCH ---
        switch_field (str): field to match
        cases (dict): {value: port_name}
        default_case (str): port if no case matches
        --- LOOP ---
        iterate_over (str): jmespath expression
        max_iterations (int): safety cap (default 100)
        --- MERGE ---
        (no extra config — passes input through on 'merged' port)
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        mode: str = str(config.get("mode", "BRANCH")).upper()

        if mode == "BRANCH":
            return await self._branch(config, context)
        elif mode == "SWITCH":
            return await self._switch(config, context)
        elif mode == "LOOP":
            return await self._loop(config, context)
        elif mode == "MERGE":
            return NodeOutput(outputs=context.input_data, route_to_port="merged")
        else:
            raise NodeExecutionError(context.node_id, f"Unknown ControlFlowNode mode: {mode}")

    async def _branch(self, config: dict[str, Any], context: NodeContext) -> NodeOutput:
        rules: list[dict[str, Any]] = list(config.get("rules") or [])
        default_branch: str = str(config.get("default_branch", "false"))
        for rule in rules:
            try:
                if _eval_condition(rule, context.input_data):
                    return NodeOutput(
                        outputs=context.input_data,
                        route_to_port=str(rule.get("target_port", "true")),
                    )
            except Exception as exc:
                raise NodeExecutionError(context.node_id, f"Branch condition error: {exc}") from exc
        return NodeOutput(outputs=context.input_data, route_to_port=default_branch)

    async def _switch(self, config: dict[str, Any], context: NodeContext) -> NodeOutput:
        field_val = _resolve(context.input_data, str(config.get("switch_field", "")))
        cases: dict[str, str] = dict(config.get("cases") or {})
        default_case: str = str(config.get("default_case", "default"))
        port = cases.get(str(field_val), default_case)
        return NodeOutput(outputs=context.input_data, route_to_port=port)

    async def _loop(self, config: dict[str, Any], context: NodeContext) -> NodeOutput:
        iterate_over: str = str(config.get("iterate_over", "@"))
        max_iter: int = int(config.get("max_iterations", 100))
        try:
            items: Any = jmespath.search(iterate_over, context.input_data)
        except Exception as exc:
            raise NodeExecutionError(context.node_id, f"jmespath error: {exc}") from exc
        if items is None:
            items = []
        if not isinstance(items, list):
            raise NodeExecutionError(context.node_id, "LOOP iterate_over must resolve to a list")
        items = items[:max_iter]
        return NodeOutput(outputs={"items": items, "count": len(items)}, route_to_port="items")
