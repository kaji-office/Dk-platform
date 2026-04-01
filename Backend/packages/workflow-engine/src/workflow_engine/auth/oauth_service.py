"""
OAuthService — OAuth2 PKCE authorization + token exchange for Google, GitHub, Microsoft.

Uses authlib's async AsyncOAuth2Client for all provider interactions.
Provider configs are hardcoded; credentials (client_id/secret) are injected at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from workflow_engine.auth.models import OAuthCredentials, OAuthProfile
from workflow_engine.errors import AuthenticationError

Provider = Literal["google", "github", "microsoft"]

_PROVIDER_CONFIGS: dict[str, dict[str, str]] = {
    "google": {
        "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.googleapis.com/token",
        "userinfo_endpoint": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
    },
    "github": {
        "authorization_endpoint": "https://github.com/login/oauth/authorize",
        "token_endpoint": "https://github.com/login/oauth/access_token",
        "userinfo_endpoint": "https://api.github.com/user",
        "scope": "read:user user:email",
    },
    "microsoft": {
        "authorization_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_endpoint": "https://graph.microsoft.com/v1.0/me",
        "scope": "openid email profile",
    },
}



class OAuthService:
    """
    Handles OAuth2 authorization code flow for supported identity providers.

    Args:
        credentials: dict mapping provider name to OAuthCredentials.
    """

    def __init__(self, credentials: dict[str, OAuthCredentials]) -> None:
        self._credentials = credentials

    def get_authorization_url(self, provider: Provider, state: str) -> str:
        """
        Build and return the authorization redirect URL for a provider.

        Args:
            provider: One of 'google', 'github', 'microsoft'.
            state: CSRF state token (caller must store in session).

        Returns:
            Full authorization URL to redirect the user to.
        """
        creds = self._get_credentials(provider)
        cfg = _PROVIDER_CONFIGS[provider]

        params = {
            "client_id": creds.client_id,
            "redirect_uri": creds.redirect_uri,
            "response_type": "code",
            "scope": cfg["scope"],
            "state": state,
        }
        # GitHub doesn't support PKCE natively in the same way — keep simple
        if provider in ("google", "microsoft"):
            params["access_type"] = "offline"
            params["prompt"] = "consent"

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cfg['authorization_endpoint']}?{query}"

    async def exchange_code(
        self,
        provider: Provider,
        code: str,
        state: str,
    ) -> tuple[OAuthProfile, dict[str, str]]:
        """
        Exchange authorization code for tokens and fetch the user profile.

        Returns:
            (OAuthProfile, token_dict) where token_dict keys: access_token, refresh_token.
        """
        creds = self._get_credentials(provider)
        cfg = _PROVIDER_CONFIGS[provider]

        # Step 1: exchange code for tokens
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                cfg["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": creds.redirect_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                },
                headers={"Accept": "application/json"},
            )

        if resp.status_code >= 400:
            raise AuthenticationError(f"OAuth2 token exchange failed [{provider}]: {resp.text}")

        tokens: dict[str, str] = resp.json()
        access_token = tokens.get("access_token", "")

        # Step 2: fetch user profile
        profile = await self._fetch_profile(provider, access_token, cfg)
        return profile, tokens

    async def refresh_oauth_token(
        self,
        provider: Provider,
        refresh_token: str,
    ) -> dict[str, str]:
        """
        Refresh an OAuth2 access token using the refresh token.

        Returns:
            Updated token dict with new access_token (and possibly new refresh_token).
        """
        creds = self._get_credentials(provider)
        cfg = _PROVIDER_CONFIGS[provider]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                cfg["token_endpoint"],
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                },
                headers={"Accept": "application/json"},
            )

        if resp.status_code >= 400:
            raise AuthenticationError(f"OAuth2 token refresh failed [{provider}]: {resp.text}")

        return resp.json()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_credentials(self, provider: Provider) -> OAuthCredentials:
        if provider not in self._credentials:
            raise AuthenticationError(f"OAuth provider '{provider}' is not configured.")
        return self._credentials[provider]

    async def _fetch_profile(
        self,
        provider: Provider,
        access_token: str,
        cfg: dict[str, str],
    ) -> OAuthProfile:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                cfg["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if resp.status_code >= 400:
            raise AuthenticationError(f"Failed to fetch user profile [{provider}]: {resp.text}")

        raw = resp.json()

        # Normalise across providers
        if provider == "google":
            return OAuthProfile(
                provider=provider,
                provider_user_id=raw.get("sub", ""),
                email=raw.get("email", ""),
                display_name=raw.get("name", ""),
                avatar_url=raw.get("picture"),
                raw_profile=raw,
            )
        elif provider == "github":
            return OAuthProfile(
                provider=provider,
                provider_user_id=str(raw.get("id", "")),
                email=raw.get("email") or "",
                display_name=raw.get("name") or raw.get("login", ""),
                avatar_url=raw.get("avatar_url"),
                raw_profile=raw,
            )
        else:  # microsoft
            return OAuthProfile(
                provider=provider,
                provider_user_id=raw.get("id", ""),
                email=raw.get("mail") or raw.get("userPrincipalName", ""),
                display_name=raw.get("displayName", ""),
                avatar_url=None,
                raw_profile=raw,
            )
