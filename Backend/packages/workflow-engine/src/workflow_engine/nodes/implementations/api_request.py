"""APIRequestNode — httpx async HTTP request with Jinja2 templates + OAuth injection."""
from __future__ import annotations

import base64
from typing import Any

from jinja2 import Template

from workflow_engine.errors import NodeExecutionError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices

_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


class APIRequestNode(BaseNodeType):
    """
    Makes an async HTTP request.

    Config:
        method, url (Jinja2), headers, body_template (Jinja2),
        auth_config {type: bearer|basic|oauth2, ...}, timeout_seconds
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        import httpx  # lazy

        method: str = str(config.get("method", "GET")).upper()
        if method not in _ALLOWED_METHODS:
            raise NodeExecutionError(context.node_id, f"Unsupported HTTP method: {method}")

        url: str = Template(str(config.get("url", ""))).render(**context.input_data)
        headers: dict[str, str] = dict(config.get("headers") or {})
        timeout: int = int(config.get("timeout_seconds", 30))

        body: str | None = None
        body_tpl: str = str(config.get("body_template") or "")
        if body_tpl:
            body = Template(body_tpl).render(**context.input_data)

        # Auth injection
        auth_config: dict[str, Any] = dict(config.get("auth_config") or {})
        auth_type = auth_config.get("type", "")
        if auth_type == "bearer":
            headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
        elif auth_type == "basic":
            creds = base64.b64encode(
                f"{auth_config.get('username','')}:{auth_config.get('password','')}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {creds}"
        elif auth_type == "oauth2":
            # Token supplied pre-resolved by the connector layer
            headers["Authorization"] = f"Bearer {auth_config.get('access_token', '')}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method, url=url, headers=headers,
                    content=body.encode() if body else None,
                )
        except httpx.TimeoutException as exc:
            raise NodeExecutionError(context.node_id, f"Request timed out: {url}") from exc
        except httpx.RequestError as exc:
            raise NodeExecutionError(context.node_id, f"Request failed: {exc}") from exc

        try:
            resp_body: Any = response.json()
        except Exception:
            resp_body = response.text

        return NodeOutput(
            outputs={"status_code": response.status_code, "body": resp_body, "headers": dict(response.headers)},
            metadata={"url": url, "method": method},
        )
