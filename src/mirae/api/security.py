"""Database-backed authentication shared by REST and WebSockets."""

from __future__ import annotations

import asyncio
import hmac
from typing import Literal
from urllib.parse import urlsplit

from fastapi import HTTPException, WebSocket, WebSocketException
from starlette.requests import HTTPConnection

from mirae.api.accounts import AuthStore, Principal

COOKIE = "mirae_session"


def check_origin(connection: HTTPConnection) -> None:
    origin = connection.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        expected_scheme = "https" if connection.url.scheme in ("https", "wss") else "http"
        if parsed.scheme != expected_scheme or parsed.netloc != connection.headers.get("host"):
            if isinstance(connection, WebSocket):
                raise WebSocketException(code=1008, reason="cross-origin access denied")
            raise HTTPException(403, "cross-origin access denied")


class ApiAuth:
    def __init__(self, store: AuthStore) -> None:
        self.store = store

    async def __call__(self, connection: HTTPConnection) -> None:
        path = connection.url.path
        if not path.startswith(("/api/", "/ws/")):
            return
        if path in ("/api/auth/status", "/api/auth/login", "/api/auth/register"):
            check_origin(connection)
            return
        await self.authorize(connection)

    @staticmethod
    def permission(connection: HTTPConnection) -> set[str]:
        path = connection.url.path
        method = connection.scope.get("method", "GET")
        if path.startswith("/api/auth/"):
            return set()
        if path.startswith("/api/admin/"):
            section = path.split("/")[3]
            if section == "pipeline":
                return {"pipeline:manage"}
            if section == "permissions":
                return set()
            if method == "GET" and section in ("roles", "users"):
                return {"users:manage", "roles:manage", "tokens:manage"}
            permission = {
                "users": "users:manage",
                "roles": "roles:manage",
                "tokens": "tokens:manage",
                "audit": "audit:read",
            }.get(section, "audit:read")
            return {permission}
        if path == "/api/estop/release":
            return {"robot:release"}
        return {"robot:read" if method == "GET" else "robot:control"}

    async def authorize(self, connection: HTTPConnection) -> Principal:
        scheme, _, secret = connection.headers.get("authorization", "").partition(" ")
        kind: Literal["token", "session"] = "token" if scheme.lower() == "bearer" else "session"
        if connection.headers.get("authorization") and kind != "token":
            secret = ""
        elif kind == "session":
            secret = connection.cookies.get(COOKIE, "")
        principal = await asyncio.to_thread(self.store.authenticate, secret, kind)
        if principal is None:
            self.deny(connection, 401, "authentication required")
        assert principal is not None
        if principal.kind == "session":
            check_origin(connection)
            if connection.scope.get("method", "GET") not in ("GET", "HEAD", "OPTIONS"):
                csrf = connection.headers.get("x-csrf-token", "")
                if not hmac.compare_digest(csrf.encode(), principal.csrf.encode()):
                    self.deny(connection, 403, "CSRF token required")
        required = self.permission(connection)
        if required and not required & principal.permissions:
            self.deny(connection, 403, "permission denied")
        connection.state.principal = principal
        return principal

    @staticmethod
    def deny(connection: HTTPConnection, status: int, message: str) -> None:
        if isinstance(connection, WebSocket):
            raise WebSocketException(code=1008, reason=message)
        raise HTTPException(
            status, message, headers={"WWW-Authenticate": "Bearer"} if status == 401 else None
        )
