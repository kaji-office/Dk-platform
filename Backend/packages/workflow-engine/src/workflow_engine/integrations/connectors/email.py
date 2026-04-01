"""
SendGrid Email Connector — send_email, send_template.
Uses SendGrid v3 REST API.
"""
from __future__ import annotations
from typing import Any

from workflow_engine.integrations.connectors.base import BaseConnector

SENDGRID_BASE = "https://api.sendgrid.com/v3"


class EmailConnector(BaseConnector):
    """Send transactional emails via SendGrid."""

    CONNECTOR_NAME = "email"

    def _build_client(self):
        import httpx
        api_key = self._require("api_key")
        return httpx.AsyncClient(
            base_url=SENDGRID_BASE,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30,
        )

    async def check_health(self) -> bool:
        try:
            await self._get("/scopes")
            return True
        except Exception:
            return False

    async def send_email(
        self,
        to: str,
        from_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
    ) -> dict[str, Any]:
        """Send a plain email."""
        content = [{"type": "text/html", "value": body_html}]
        if body_text:
            content.insert(0, {"type": "text/plain", "value": body_text})
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": content,
        }
        return await self._post("/mail/send", json=payload)

    async def send_template(
        self,
        to: str,
        from_email: str,
        template_id: str,
        dynamic_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a SendGrid dynamic template email."""
        payload = {
            "personalizations": [
                {"to": [{"email": to}], "dynamic_template_data": dynamic_data}
            ],
            "from": {"email": from_email},
            "template_id": template_id,
        }
        return await self._post("/mail/send", json=payload)
