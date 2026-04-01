# Adding New Connectors to the DK Platform

This guide explains how to extend the platform with new REST/API connectors
so they work seamlessly with the node registry, credential store, and
workflow execution engine.

---

## Architecture Overview

```
workflow_engine/
└── integrations/
    ├── connectors/
    │   ├── base.py          ← Abstract BaseConnector interface
    │   ├── registry.py      ← ConnectorFactory + register_connector()
    │   ├── slack.py         ← Example: Slack
    │   ├── email.py         ← Example: SendGrid Email
    │   └── github.py        ← Example: GitHub
    └── mcp/
        ├── client.py        ← MCPClient (http_sse + stdio)
        └── registry.py      ← Pooled MCPClientRegistry + caches
```

---

## Step-by-Step: Adding a New Connector

### 1. Create the connector file

Create `workflow_engine/integrations/connectors/<name>.py`:

```python
from workflow_engine.integrations.connectors.base import BaseConnector

class MyServiceConnector(BaseConnector):
    CONNECTOR_NAME = "my_service"

    def _build_client(self):
        import httpx
        api_key = self._require("api_key")   # fetched from encrypted oauth_tokens
        return httpx.AsyncClient(
            base_url="https://api.myservice.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )

    async def check_health(self) -> bool:
        try:
            data = await self._get("/ping")
            return data.get("status") == "ok"
        except Exception:
            return False

    async def create_record(self, payload: dict) -> dict:
        return await self._post("/records", json=payload)
```

### 2. Register the connector

In `workflow_engine/integrations/connectors/__init__.py`, add:

```python
from workflow_engine.integrations.connectors.my_service import MyServiceConnector
register_connector(MyServiceConnector)
```

That's it — the connector is now available platform-wide via `ConnectorFactory`.

### 3. Store credentials securely

Connector credentials must be stored in the `oauth_tokens` Postgres table:

```sql
CREATE TABLE oauth_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,
    connector   TEXT NOT NULL,    -- matches CONNECTOR_NAME
    token_data  BYTEA NOT NULL,   -- AES-256-GCM encrypted JSON blob
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ
);
```

At runtime, `ConnectorFactory` calls `credentials_store(tenant_id, connector_name)`
which decrypts and returns the credential dict. The connector receives it as
`self._credentials` — it never sees the raw encrypted bytes.

### 4. Write tests with mocked HTTP

Use `httpx.MockTransport` or `pytest-httpx` to mock all HTTP responses:

```python
import pytest
import httpx
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_my_service_health():
    connector = MyServiceConnector("t1", {"api_key": "test-key"})
    
    async def mock_transport(request):
        return httpx.Response(200, json={"status": "ok"})
    
    connector._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
    result = await connector.check_health()
    assert result is True
```

---

## Adding a New MCP Server

MCP servers are registered via `MCPClientRegistry.PLATFORM_SERVERS`:

```python
MCPClientRegistry.PLATFORM_SERVERS["my_mcp_server"] = {
    "transport": "http_sse",
    "url": "https://my-mcp-server.example.com/sse",
}
```

Or for stdio-based servers:

```python
MCPClientRegistry.PLATFORM_SERVERS["my_tool"] = {
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@my-org/my-mcp-server"],
}
```

---

## Supported Connectors (Built-in)

| Connector | Class | Actions |
|-----------|-------|---------|
| Slack | `SlackConnector` | `send_message`, `send_dm`, `create_channel` |
| Email | `EmailConnector` | `send_email`, `send_template` |
| GitHub | `GitHubConnector` | `create_issue`, `create_pr`, `list_repos`, `push_file` |

## Roadmap Connectors (Planned)

| Connector | Priority |
|-----------|----------|
| Discord | High |
| Teams | High |
| Google Sheets | High |
| Salesforce | Medium |
| MySQL | Medium |
| Redis | Medium |
| OneDrive | Low |

---

## Security Notes

- **OAuth tokens** are encrypted at rest using AES-256-GCM in Postgres.
- **Tenant isolation**: `ConnectorFactory` always scopes connections by `tenant_id`.
- **No plaintext secrets** should ever appear in logs — use `self._require()` which safely fetches from `self._credentials`.
- **Health checks** are run at node startup, not per-call, to avoid latency.
