"""First-run setup, browser sessions and administrative access management."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from mirae.api.accounts import PERMISSIONS, AuthStore, Principal
from mirae.api.security import COOKIE
from mirae.config import ApiConfig

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Username = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$")]
Password = Annotated[str, Field(min_length=12, max_length=128)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Register(Input):
    username: Username
    display_name: Name
    password: Password


class Login(Input):
    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class CreateUser(Register):
    role_id: str = Field(min_length=1, max_length=64)


class UpdateUser(Input):
    display_name: Name | None = None
    role_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    active: bool | None = None
    password: Password | None = None


class RoleInput(Input):
    name: Name
    permissions: list[str] = Field(max_length=32)


class TokenInput(Input):
    user_id: str = Field(min_length=1, max_length=64)
    name: Name
    scopes: list[str] = Field(min_length=1, max_length=32)
    expires_days: int = Field(30, ge=1, le=365)


class PasswordChange(Input):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    password: Password


def access_router(store: AuthStore, cfg: ApiConfig) -> APIRouter:
    router = APIRouter()
    hashing = asyncio.Semaphore(2)

    def actor(request: Request) -> Principal:
        principal: Principal = request.state.principal
        return principal

    async def throttle(request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        await asyncio.to_thread(store.check_attempt, "auth:" + key)
        if hashing.locked():
            raise HTTPException(429, "authentication busy; try again shortly")

    async def session(username: str, password: str, response: Response) -> dict[str, Any]:
        secret, principal = await asyncio.to_thread(
            store.login, username, password, cfg.session_hours
        )
        response.set_cookie(
            COOKIE,
            secret,
            max_age=int(cfg.session_hours * 3600),
            httponly=True,
            secure=cfg.cookie_secure,
            samesite="strict",
            path="/",
        )
        return {"user": principal.public(), "csrf_token": principal.csrf}

    @router.get("/api/auth/status")
    async def status() -> dict[str, bool]:
        return {"registration_open": await asyncio.to_thread(store.registration_open)}

    @router.post("/api/auth/register", status_code=201)
    async def register(req: Register, request: Request, response: Response) -> dict[str, Any]:
        await throttle(request)
        async with hashing:
            await asyncio.to_thread(
                store.create_user,
                req.username,
                req.display_name,
                req.password,
                "admin",
                bootstrap=True,
            )
            return await session(req.username, req.password, response)

    @router.post("/api/auth/login")
    async def login(req: Login, request: Request, response: Response) -> dict[str, Any]:
        await throttle(request)
        async with hashing:
            return await session(req.username, req.password, response)

    @router.get("/api/auth/me")
    async def me(request: Request) -> dict[str, Any]:
        principal = actor(request)
        return {"user": principal.public(), "csrf_token": principal.csrf}

    @router.post("/api/auth/logout")
    async def logout(request: Request, response: Response) -> dict[str, bool]:
        await asyncio.to_thread(store.logout, actor(request))
        response.delete_cookie(
            COOKIE, path="/", secure=cfg.cookie_secure, httponly=True, samesite="strict"
        )
        return {"ok": True}

    @router.post("/api/auth/password")
    async def password(
        req: PasswordChange, request: Request, response: Response
    ) -> dict[str, bool]:
        await throttle(request)
        async with hashing:
            await asyncio.to_thread(
                store.change_password, actor(request), req.current_password, req.password
            )
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @router.get("/api/admin/permissions")
    async def permissions() -> dict[str, str]:
        return PERMISSIONS

    @router.get("/api/admin/users")
    async def users() -> list[dict[str, Any]]:
        return await asyncio.to_thread(store.users)

    @router.post("/api/admin/users", status_code=201)
    async def create_user(req: CreateUser, request: Request) -> dict[str, Any]:
        if hashing.locked():
            raise HTTPException(429, "password hashing busy; try again shortly")
        async with hashing:
            return await asyncio.to_thread(
                store.create_user,
                req.username,
                req.display_name,
                req.password,
                req.role_id,
                actor(request).username,
            )

    @router.patch("/api/admin/users/{user_id}")
    async def update_user(user_id: str, req: UpdateUser, request: Request) -> dict[str, Any]:
        if hashing.locked():
            raise HTTPException(429, "password hashing busy; try again shortly")
        async with hashing:
            return await asyncio.to_thread(
                store.update_user,
                user_id,
                req.model_dump(exclude_none=True),
                actor(request).username,
            )

    @router.delete("/api/admin/users/{user_id}")
    async def delete_user(user_id: str, request: Request) -> dict[str, bool]:
        await asyncio.to_thread(store.delete_user, user_id, actor(request).username)
        return {"ok": True}

    @router.get("/api/admin/roles")
    async def roles() -> list[dict[str, Any]]:
        return await asyncio.to_thread(store.roles)

    @router.post("/api/admin/roles", status_code=201)
    async def create_role(req: RoleInput, request: Request) -> dict[str, str]:
        role_id = await asyncio.to_thread(
            store.save_role, None, req.name, req.permissions, actor(request).username
        )
        return {"id": role_id}

    @router.put("/api/admin/roles/{role_id}")
    async def update_role(role_id: str, req: RoleInput, request: Request) -> dict[str, str]:
        await asyncio.to_thread(
            store.save_role, role_id, req.name, req.permissions, actor(request).username
        )
        return {"id": role_id}

    @router.delete("/api/admin/roles/{role_id}")
    async def delete_role(role_id: str, request: Request) -> dict[str, bool]:
        await asyncio.to_thread(store.delete_role, role_id, actor(request).username)
        return {"ok": True}

    @router.get("/api/admin/tokens")
    async def tokens() -> list[dict[str, Any]]:
        return await asyncio.to_thread(store.tokens)

    @router.post("/api/admin/tokens", status_code=201)
    async def token(req: TokenInput, request: Request) -> dict[str, Any]:
        return await asyncio.to_thread(
            store.issue_token, req.user_id, req.name, req.scopes, req.expires_days, actor(request)
        )

    @router.delete("/api/admin/tokens/{token_id}")
    async def revoke_token(token_id: str, request: Request) -> dict[str, bool]:
        await asyncio.to_thread(store.revoke_token, token_id, actor(request).username)
        return {"ok": True}

    @router.get("/api/admin/audit")
    async def audit() -> list[dict[str, Any]]:
        return await asyncio.to_thread(store.audit_log)

    return router
