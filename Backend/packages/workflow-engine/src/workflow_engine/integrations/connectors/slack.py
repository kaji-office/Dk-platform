"""
Slack Connector — send_message, send_dm, create_channel.
Uses Slack Web API v2 with Bot Token (xoxb-...).
"""
from __future__ import annotations
from typing import Any

from workflow_engine.integrations.connectors.base import BaseConnector

SLACK_API_BASE = "https://slack.com/api"


class SlackConnector(BaseConnector):
    """Interact with Slack channels and users via Bot Token."""

    CONNECTOR_NAME = "slack"

    def _build_client(self):
        import httpx
        token = self._require("bot_token")
        return httpx.AsyncClient(
            base_url=SLACK_API_BASE,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )

    async def check_health(self) -> bool:
        """Verify token validity via auth.test."""
        data = await self._post("/auth.test")
        return data.get("ok", False)

    async def send_message(self, channel: str, text: str, blocks: list | None = None) -> dict[str, Any]:
        """Post a message to a public/private channel."""
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        return await self._post("/chat.postMessage", json=payload)

    async def send_dm(self, user_id: str, text: str) -> dict[str, Any]:
        """Open a DM and send a message to a specific user."""
        # Step 1: open conversation
        conv = await self._post("/conversations.open", json={"users": user_id})
        channel_id = conv["channel"]["id"]
        # Step 2: send the message
        return await self.send_message(channel_id, text)

    async def create_channel(self, name: str, is_private: bool = False) -> dict[str, Any]:
        """Create a new Slack channel."""
        return await self._post(
            "/conversations.create",
            json={"name": name, "is_private": is_private},
        )
