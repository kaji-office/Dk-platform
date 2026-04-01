"""CodeExecutionNode — Python sandbox with RestrictedPython + AST import scan."""
from __future__ import annotations

import ast
import asyncio
from typing import Any

from RestrictedPython import compile_restricted, safe_globals  # type: ignore[import-untyped]
from RestrictedPython.PrintCollector import PrintCollector  # type: ignore[import-untyped]

from workflow_engine.errors import NodeExecutionError, SandboxTimeoutError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices

_BLOCKED_MODULES = frozenset({"os", "sys", "subprocess", "socket", "shutil", "importlib", "ctypes"})


def _ast_scan_imports(code: str, node_id: str) -> None:
    """Static AST scan to block dangerous import statements before execution."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return  # will be caught later by compile_restricted
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_MODULES:
                    raise NodeExecutionError(node_id, f"Import of '{alias.name}' is not allowed in sandbox")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root in _BLOCKED_MODULES:
                raise NodeExecutionError(node_id, f"Import from '{module}' is not allowed in sandbox")


class CodeExecutionNode(BaseNodeType):
    """
    Executes user-supplied Python code in a RestrictedPython sandbox.
    Blocks: os, sys, subprocess, socket, shutil, importlib, ctypes.
    Performs static AST scan before execution.

    Config:
        code (str): Python code. Must assign result to `output`.
        timeout_seconds (int): Execution timeout (default 10).
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        code: str = str(config.get("code", ""))
        timeout_seconds: int = int(config.get("timeout_seconds", 10))

        if not code.strip():
            return NodeOutput(outputs={"output": None})

        # Static import scan
        _ast_scan_imports(code, context.node_id)

        try:
            byte_code = compile_restricted(code, filename="<CodeExecutionNode>", mode="exec")
        except SyntaxError as exc:
            raise NodeExecutionError(context.node_id, f"Syntax error: {exc}") from exc

        local_vars: dict[str, Any] = {
            "input": context.input_data,
            "output": None,
            "_print_": PrintCollector,
            "_getitem_": lambda obj, key: obj[key],
            "_getiter_": iter,
            "_getattr_": getattr,
        }
        restricted_globals: dict[str, Any] = {
            **safe_globals,
            "__builtins__": {
                k: v for k, v in (safe_globals.get("__builtins__") or {}).items()  # type: ignore[union-attr]
                if k not in _BLOCKED_MODULES
            },
            "__name__": "sandbox",
        }

        def _run() -> None:
            exec(byte_code, restricted_globals, local_vars)  # noqa: S102

        try:
            await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(None, _run),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise SandboxTimeoutError(f"CodeExecutionNode timed out after {timeout_seconds}s") from exc
        except Exception as exc:
            raise NodeExecutionError(context.node_id, str(exc)) from exc

        return NodeOutput(outputs={"output": local_vars.get("output")})
