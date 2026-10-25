"""Administration of actual LLM connections and local/device pipeline settings."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from mirae.api.accounts import AccountError
from mirae.pipeline.manager import PipelineManager
from mirae.pipeline.settings import ConnectionInput


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: str | None


class SecretInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr | None = Field(None, exclude=True)


SECRETS = ("elevenlabs",)


class Enabled(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


def pipeline_router(manager: PipelineManager) -> APIRouter:
    router = APIRouter(prefix="/api/admin/pipeline")

    @router.get("")
    async def status() -> dict[str, Any]:
        return await asyncio.to_thread(manager.status)

    @router.get("/schema")
    async def schema() -> dict[str, Any]:
        return manager.schema()

    @router.get("/connections")
    async def connections() -> list[dict[str, Any]]:
        return await asyncio.to_thread(manager.settings.connections)

    @router.post("/connections", status_code=201)
    async def create_connection(req: ConnectionInput, request: Request) -> dict[str, str]:
        async with manager.change_lock:
            key = await asyncio.to_thread(
                manager.settings.save_connection, None, req, request.state.principal.username
            )
            return {"id": key}

    @router.put("/connections/{connection_id}")
    async def update_connection(
        connection_id: str, req: ConnectionInput, request: Request
    ) -> dict[str, str]:
        async with manager.change_lock:
            key = await asyncio.to_thread(
                manager.settings.save_connection,
                connection_id,
                req,
                request.state.principal.username,
            )
            return {"id": key}

    @router.delete("/connections/{connection_id}")
    async def delete_connection(connection_id: str, request: Request) -> dict[str, bool]:
        async with manager.change_lock:
            await asyncio.to_thread(
                manager.settings.delete_connection, connection_id, request.state.principal.username
            )
        return {"ok": True}

    @router.post("/connections/{connection_id}/check")
    async def check_connection(connection_id: str) -> dict[str, Any]:
        return await manager.check_connection(connection_id)

    @router.post("/selection")
    async def select_connection(req: Selection, request: Request) -> dict[str, bool]:
        await manager.select_connection(req.connection_id, request.state.principal.username)
        return {"ok": True}

    @router.put("/config/{section}")
    async def config(section: str, changes: dict[str, Any], request: Request) -> dict[str, Any]:
        async with manager.change_lock:
            try:
                return await asyncio.to_thread(
                    manager.save_config, section, changes, request.state.principal.username
                )
            except ValidationError as exc:
                raise AccountError(422, "; ".join(error["msg"] for error in exc.errors())) from exc

    @router.get("/secrets")
    async def secrets() -> dict[str, bool]:
        """Which service credentials are set. Values never leave the server."""
        return {
            name: await asyncio.to_thread(manager.settings.value, f"secret:{name}") is not None
            for name in SECRETS
        }

    @router.put("/secrets/{name}")
    async def set_secret(name: str, req: SecretInput, request: Request) -> dict[str, bool]:
        if name not in SECRETS:
            raise AccountError(404, "unknown credential")
        value = req.api_key.get_secret_value().strip() if req.api_key else None
        await asyncio.to_thread(
            manager.settings.set_secret, name, value or None, request.state.principal.username
        )
        return {"set": bool(value)}

    @router.post("/dependencies/check")
    async def check_dependencies() -> list[dict[str, Any]]:
        return await asyncio.to_thread(manager.inspect_dependencies)

    @router.post("/dependencies/{dependency}/install", status_code=202)
    async def install_dependency(dependency: str, request: Request) -> dict[str, str]:
        job = await asyncio.to_thread(
            manager.install_dependency, dependency, request.state.principal.username
        )
        return {"job_id": job}

    @router.get("/jobs/{job}")
    async def job_status(job: str, after: int = Query(0, ge=0)) -> dict[str, Any]:
        return await asyncio.to_thread(manager.jobs.snapshot, job, after)

    @router.post("/jobs/{job}/cancel")
    async def cancel_job(job: str) -> dict[str, bool]:
        manager.jobs.cancel(job)
        return {"ok": True}

    @router.post("/devices/refresh")
    async def refresh_devices() -> dict[str, Any]:
        return await asyncio.to_thread(manager.refresh_devices)

    @router.post("/models/{model}/download", status_code=202)
    async def download_model(model: str, request: Request) -> dict[str, str]:
        return {
            "job_id": await asyncio.to_thread(
                manager.download_model, model, request.state.principal.username
            )
        }

    @router.post("/models/{model}/activate")
    async def activate_model(model: str, request: Request) -> dict[str, bool]:
        await manager.activate_model(model, request.state.principal.username)
        return {"ok": True}

    @router.post("/local/{section}/enabled")
    async def local_enabled(section: str, req: Enabled, request: Request) -> dict[str, bool]:
        await manager.set_local_enabled(section, req.enabled, request.state.principal.username)
        return {"ok": True}

    @router.post("/local/apply")
    async def apply_local(request: Request) -> dict[str, bool]:
        await manager.apply_local(request.state.principal.username)
        return {"ok": True}

    @router.post("/camera/check")
    async def check_camera() -> dict[str, Any]:
        try:
            return await manager.capture_test()
        except AccountError:
            raise
        except Exception as exc:
            raise AccountError(422, f"{type(exc).__name__}: {exc}") from exc

    @router.get("/camera/frame")
    async def camera_frame() -> Response:
        return Response(manager.camera_frame(), media_type="image/jpeg")

    @router.get("/live/vision")
    async def live_vision() -> dict[str, Any]:
        return manager.live_vision()

    @router.get("/live/speech")
    async def live_speech(after: int = Query(0, ge=0)) -> dict[str, Any]:
        return manager.live_speech(after)

    @router.post("/audio/check")
    async def check_audio() -> dict[str, Any]:
        try:
            return await manager.test_audio()
        except AccountError:
            raise
        except Exception as exc:
            raise AccountError(422, f"{type(exc).__name__}: {exc}") from exc

    return router
