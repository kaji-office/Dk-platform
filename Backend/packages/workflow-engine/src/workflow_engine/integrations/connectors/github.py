"""
GitHub Connector — create_issue, create_pr, list_repos, push_file.
Uses GitHub REST API v3 with Personal Access Token.
"""
from __future__ import annotations
from typing import Any
import base64

from workflow_engine.integrations.connectors.base import BaseConnector

GITHUB_API = "https://api.github.com"


class GitHubConnector(BaseConnector):
    """Interact with GitHub repositories via REST API."""

    CONNECTOR_NAME = "github"

    def _build_client(self):
        import httpx
        token = self._require("personal_access_token")
        return httpx.AsyncClient(
            base_url=GITHUB_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    async def check_health(self) -> bool:
        try:
            data = await self._get("/user")
            return "login" in data
        except Exception:
            return False

    async def list_repos(self, per_page: int = 30) -> list[dict[str, Any]]:
        """List repos for the authenticated user."""
        return await self._get("/user/repos", params={"per_page": per_page, "sort": "updated"})

    async def create_issue(
        self, owner: str, repo: str, title: str, body: str, labels: list[str] | None = None
    ) -> dict[str, Any]:
        """Open a new GitHub issue."""
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        return await self._post(f"/repos/{owner}/{repo}/issues", json=payload)

    async def create_pr(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
        draft: bool = False,
    ) -> dict[str, Any]:
        """Open a pull request."""
        return await self._post(
            f"/repos/{owner}/{repo}/pulls",
            json={"title": title, "head": head, "base": base, "body": body, "draft": draft},
        )

    async def push_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a file in a GitHub repository."""
        encoded = base64.b64encode(content.encode()).decode()
        payload: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        return await self._put(f"/repos/{owner}/{repo}/contents/{path}", json=payload)

    async def _put(self, url: str, **kwargs: Any) -> dict[str, Any]:
        assert self._client
        resp = await self._client.put(url, **kwargs)
        if not resp.is_success:
            from workflow_engine.integrations.connectors.base import ConnectorRequestError
            raise ConnectorRequestError(resp.status_code, resp.text)
        return resp.json()
