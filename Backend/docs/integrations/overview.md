# Integrations — Overview
## Built-in Connectors · Notifications · Observability

---

## 1. Connector Architecture

All connectors are implemented inside `engine/integrations/connectors/`. They are used by `APINode` (outbound HTTP calls from workflows) and `engine.notifications` (platform-level notifications).

Each connector:
- Extends `BaseConnector` abstract class
- Handles OAuth2 token refresh automatically
- Provides a typed `call()` method
- Defines its own `auth_schema` and `action_schemas`

```python
# engine/integrations/connectors/base.py

class BaseConnector(ABC):
    connector_id: str
    display_name: str
    icon: str
    auth_schema: dict        # JSON Schema for auth config (shown in Settings > Integrations)
    action_schemas: dict[str, dict]  # per-action input/output schemas

    @abstractmethod
    async def call(
        self,
        action: str,
        params: dict,
        auth_credentials: OAuthToken | APIKeyCredential,
    ) -> dict:
        """Execute the connector action. Returns response dict."""
        ...

    async def refresh_token_if_needed(self, credentials: OAuthToken) -> OAuthToken:
        """Called automatically before every action if token is expiring."""
        if credentials.expires_at < datetime.utcnow() + timedelta(minutes=5):
            return await self.oauth_manager.refresh(credentials)
        return credentials
```

---

## 2. Communication Connectors

### Slack

**Auth:** OAuth2 (Slack App — `chat:write`, `channels:read` scopes)
**Actions:**

| Action | Params | Returns |
|---|---|---|
| `send_message` | `channel`, `text`, `blocks` | `message_ts` |
| `send_dm` | `user_email`, `text` | `message_ts` |
| `create_channel` | `name`, `is_private` | `channel_id` |
| `get_channel_info` | `channel` | channel object |

```python
# Usage in APINode config:
{
  "connector": "slack",
  "action": "send_message",
  "params": {
    "channel": "#notifications",
    "text": "Workflow completed: {{input.run_id}}"
  }
}
```

---

### Email (SMTP / SendGrid)

**Auth:** SendGrid API Key or SMTP credentials
**Actions:**

| Action | Params | Returns |
|---|---|---|
| `send_email` | `to`, `subject`, `body_html`, `body_text`, `from` | `message_id` |
| `send_template` | `to`, `template_id`, `template_data` | `message_id` |

---

### Discord

**Auth:** Discord Webhook URL (no OAuth needed for basic posting)
**Actions:**

| Action | Params | Returns |
|---|---|---|
| `send_message` | `webhook_url`, `content`, `embeds` | status |
| `send_embed` | `webhook_url`, `title`, `description`, `color` | status |

---

### Microsoft Teams

**Auth:** OAuth2 (Azure AD — `ChannelMessage.Send` scope)
**Actions:**

| Action | Params | Returns |
|---|---|---|
| `send_message` | `team_id`, `channel_id`, `content` | `message_id` |
| `send_card` | `team_id`, `channel_id`, `adaptive_card` | `message_id` |

---

## 3. Data & Storage Connectors

### Google Sheets

**Auth:** OAuth2 (`https://www.googleapis.com/auth/spreadsheets`)
**Actions:**

| Action | Params | Returns |
|---|---|---|
| `read_range` | `spreadsheet_id`, `range` | `values[][]` |
| `append_row` | `spreadsheet_id`, `sheet`, `values[]` | `updated_range` |
| `update_range` | `spreadsheet_id`, `range`, `values[][]` | `updated_cells` |
| `clear_range` | `spreadsheet_id`, `range` | status |

---

### AWS S3

**Auth:** AWS IAM (IRSA — no static credentials stored)
**Actions:**

| Action | Params | Returns |
|---|---|---|
| `get_object` | `bucket`, `key` | `body` (base64 or text) |
| `put_object` | `bucket`, `key`, `body`, `content_type` | `etag` |
| `list_objects` | `bucket`, `prefix`, `max_keys` | `objects[]` |
| `delete_object` | `bucket`, `key` | status |
| `generate_presigned_url` | `bucket`, `key`, `expiry_seconds` | `url` |

---

### OneDrive

**Auth:** Microsoft OAuth2 (`Files.ReadWrite` scope)
**Actions:**

| Action | Params | Returns |
|---|---|---|
| `get_file` | `file_id` | file content |
| `upload_file` | `parent_id`, `filename`, `content` | `file_id` |
| `list_folder` | `folder_id` | `items[]` |
| `create_folder` | `parent_id`, `name` | `folder_id` |

---

## 4. Database Connectors

All database connectors use connection string credentials stored in AWS Secrets Manager (per tenant, per connection). Connections are **not** pooled across executions — a new connection is established per node execution (with connection timeout of 10s).

### PostgreSQL

```python
# Action: query
{
  "connector": "postgresql",
  "action": "query",
  "params": {
    "sql": "SELECT * FROM customers WHERE status = $1",
    "params": ["{{input.status}}"]
  }
}
```

**Actions:** `query` (SELECT), `execute` (INSERT/UPDATE/DELETE), `transaction` (multi-statement)

---

### MySQL

Same interface as PostgreSQL. Uses `aiomysql` driver.

---

### MongoDB

**Actions:**

| Action | Params |
|---|---|
| `find` | `collection`, `filter`, `projection`, `limit` |
| `find_one` | `collection`, `filter`, `projection` |
| `insert_one` | `collection`, `document` |
| `insert_many` | `collection`, `documents[]` |
| `update_one` | `collection`, `filter`, `update`, `upsert` |
| `delete_one` | `collection`, `filter` |
| `aggregate` | `collection`, `pipeline[]` |

---

### Redis

**Actions:** `get`, `set`, `delete`, `exists`, `hget`, `hset`, `lpush`, `lrange`, `publish`

---

## 5. Developer Tool Connectors

### GitHub

**Auth:** OAuth2 App or Personal Access Token
**Actions:**

| Action | Params |
|---|---|
| `create_issue` | `owner`, `repo`, `title`, `body`, `labels` |
| `list_issues` | `owner`, `repo`, `state`, `labels` |
| `create_pr` | `owner`, `repo`, `title`, `body`, `head`, `base` |
| `get_repo` | `owner`, `repo` |
| `create_file` | `owner`, `repo`, `path`, `content`, `message` |
| `trigger_workflow` | `owner`, `repo`, `workflow_id`, `ref`, `inputs` |

---

## 6. CRM Connector

### Salesforce

**Auth:** OAuth2 (`api`, `refresh_token` scopes)
**Actions:**

| Action | Params |
|---|---|
| `query` | `soql` (SOQL query string) |
| `create_record` | `sobject`, `data` |
| `update_record` | `sobject`, `record_id`, `data` |
| `get_record` | `sobject`, `record_id`, `fields` |
| `delete_record` | `sobject`, `record_id` |
| `upsert_record` | `sobject`, `external_id_field`, `data` |

---

## 7. Platform Notification Channels

These are used by `engine.notifications` — NOT available as workflow nodes. They fire automatically on workflow events (run complete, failure, human approval required).

### Email (SendGrid)

```python
# engine/notifications/channels/email.py

class EmailChannel:
    async def send(self, event: NotificationEvent, config: NotificationConfig) -> None:
        template = self.jinja_env.get_template(f"emails/{event.event_type}.html")
        html = template.render(event=event)

        await self.sendgrid_client.send(
            to=config.email_to,
            subject=self._subject(event),
            html_content=html,
        )
```

**Triggered on:**
- `RunCompleted` (SUCCESS) — if tenant has `on_success` notification config
- `RunFailed` — if tenant has `on_failure` notification config
- `HumanApprovalRequired` — always sent to the configured assignee

---

### In-App (WebSocket Push)

```python
# engine/notifications/channels/inapp.py

class InAppChannel:
    async def send(self, event: NotificationEvent, user_id: str) -> None:
        await self.redis.publish(
            f"notifications:{user_id}",
            NotificationPayload(
                id=str(uuid4()),
                type=event.event_type,
                title=self._title(event),
                body=self._body(event),
                link=f"/runs/{event.run_id}",
                created_at=datetime.utcnow().isoformat(),
            ).model_dump_json(),
        )
```

Frontend subscribes to `notifications:{user_id}` channel via the WebSocket hub. Notifications appear as a bell icon count + dropdown.

---

## 8. Observability — AWS CloudWatch

### Structured Logging

All services emit JSON-structured logs to CloudWatch Logs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "workflow-api",
  "request_id": "req_abc123",
  "tenant_id": "t_xyz789",
  "run_id": "run_def456",
  "node_id": "node-1",
  "event": "node_execution_completed",
  "duration_ms": 847,
  "node_type": "AI",
  "isolation_tier": 1,
  "cost_usd": 0.000675
}
```

PII fields are masked before logging using `engine.privacy.masker`.

### CloudWatch Metrics (Custom Namespace: `WorkflowPlatform`)

| Metric | Unit | Dimensions | Alarm |
|---|---|---|---|
| `ExecutionCount` | Count | tenant_id, status | — |
| `ExecutionDuration` | Milliseconds | node_type | p99 > 30s |
| `NodeExecutionCount` | Count | node_type, tier | — |
| `APILatency` | Milliseconds | route | p99 > 2s |
| `CeleryQueueDepth` | Count | queue | > 500 |
| `LLMTokensUsed` | Count | model, tenant_id | — |
| `SandboxStartupLatency` | Milliseconds | tier | p50 > 200ms |
| `ActiveRuns` | Count | — | — |
| `FailureRate` | Percent | — | > 1% |

### AWS X-Ray Distributed Tracing

Traces span from ALB → API → Celery → Worker → Node Execution:

```
[ALB] → [workflow-api: POST /executions]
              └─ [SDK: validation.validate()]
              └─ [SDK: versioning.pin()]
              └─ [Celery: orchestrate_run.delay()]
                        └─ [workflow-worker: RunOrchestrator.run()]
                                  └─ [Node: AINode.execute()]
                                            └─ [LLM API: anthropic.generate()]
```

Trace context propagated via `X-Amzn-Trace-Id` header and Celery task metadata.

### CloudWatch Alarms → SNS → On-Call

```
Alarm: API p99 latency > 2s       → SNS → PagerDuty/email
Alarm: Failure rate > 1%           → SNS → PagerDuty/email
Alarm: Celery queue depth > 500   → SNS → Slack #ops-alerts
Alarm: RDS CPU > 80%              → SNS → Slack #ops-alerts
Alarm: Redis memory > 80%         → SNS → Slack #ops-alerts
```
