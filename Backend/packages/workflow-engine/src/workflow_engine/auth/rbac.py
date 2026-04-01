"""
RBAC — Role-Based Access Control guard for the DK Platform SDK.

Usage in service methods:
    from workflow_engine.auth.rbac import RBACGuard, Role

    def delete_workflow(self, user_roles: list[Role], ...):
        RBACGuard.require(user_roles, Role.EDITOR)   # raises if VIEWER
        ...

Or as a decorator on sync/async class methods:
    @require_role(Role.OWNER)
    async def purge_tenant(self, claims: TokenClaims, ...):
        ...
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from workflow_engine.auth.models import Role, TokenClaims
from workflow_engine.errors import InsufficientPermissionsError


class RBACGuard:
    """Stateless RBAC enforcement helper."""

    @staticmethod
    def check(user_roles: list[Role], required_role: Role) -> bool:
        """
        Return True if the user has at least the required role level.

        Privilege order (ascending):
            VIEWER < EDITOR < ADMIN < SUPERADMIN
        """
        return any(role >= required_role for role in user_roles)

    @staticmethod
    def require(user_roles: list[Role], required_role: Role, action: str = "") -> None:
        """
        Assert that user_roles satisfies required_role.

        Args:
            user_roles: Roles extracted from the authenticated token/session.
            required_role: Minimum role required.
            action: Optional human-readable action name for error messages.

        Raises:
            InsufficientPermissionsError: If the check fails.
        """
        if not RBACGuard.check(user_roles, required_role):
            highest = max(user_roles, default=None, key=lambda r: list(Role).index(r))
            msg = (
                f"Action '{action}' requires role '{required_role.value}', "
                f"but user only has '{highest.value if highest else 'none'}'."
            )
            raise InsufficientPermissionsError(msg)

    @staticmethod
    def require_from_claims(claims: TokenClaims, required_role: Role, action: str = "") -> None:
        """Convenience wrapper that takes a TokenClaims object."""
        RBACGuard.require(claims.roles, required_role, action)


def require_role(minimum: Role) -> Callable:
    """
    Decorator for SDK service methods — enforces minimum RBAC role.

    The decorated method MUST accept `claims: TokenClaims` as the first
    (non-self) argument. The decorator reads roles from claims automatically.

    Example:
        @require_role(Role.EDITOR)
        async def activate_workflow(self, claims: TokenClaims, workflow_id: str):
            ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def async_wrapper(self: Any, claims: TokenClaims, *args: Any, **kwargs: Any) -> Any:
            RBACGuard.require(claims.roles, minimum, action=fn.__name__)
            return await fn(self, claims, *args, **kwargs)

        @functools.wraps(fn)
        def sync_wrapper(self: Any, claims: TokenClaims, *args: Any, **kwargs: Any) -> Any:
            RBACGuard.require(claims.roles, minimum, action=fn.__name__)
            return fn(self, claims, *args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator
