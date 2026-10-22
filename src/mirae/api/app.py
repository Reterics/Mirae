"""HTTP + WebSocket API.

Movement commands expire. Without ``duration_s`` a command lasts
``safety.command_timeout_s`` (0.5 s by default), so a joystick-style client must
keep re-sending while the stick is held. ``duration_s`` is capped at
``safety.max_command_duration_s``. Obstacle and speed limits always apply.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from mirae import __version__
from mirae.behavior.intents import Intent
from mirae.core.bus import Topics
from mirae.drive.kinematics import mix
from mirae.robot import Robot

Unit = Annotated[float, Field(ge=0.0, le=1.0)]
Signed = Annotated[float, Field(ge=-1.0, le=1.0)]
OptDuration = Annotated[float | None, Field(gt=0.0)]


class MovementRequest(BaseModel):
    action: Literal["forward", "backward", "left", "right", "stop"]
    speed: Unit = 0.3
    duration_s: OptDuration = None


class DriveRequest(BaseModel):
    linear: Signed = 0.0
    angular: Signed = 0.0
    duration_s: OptDuration = None


class CommandRequest(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=500)]


class SimRangeRequest(BaseModel):
    distance_mm: Annotated[float, Field(ge=0.0)] | None


def create_app(robot: Robot) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await robot.start()
        try:
            yield
        finally:
            await robot.stop()

    app = FastAPI(title="Mirae", version=__version__, lifespan=lifespan)
    app.state.robot = robot

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        if not robot.healthy:
            raise HTTPException(503, "runtime loop stopped")
        return {"status": "ok", "version": __version__}

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        return robot.telemetry()

    @app.post("/api/movement")
    async def movement(req: MovementRequest) -> dict[str, Any]:
        linear, angular = {
            "forward": (req.speed, 0.0),
            "backward": (-req.speed, 0.0),
            "left": (0.0, req.speed),
            "right": (0.0, -req.speed),
            "stop": (0.0, 0.0),
        }[req.action]
        if req.action == "stop":
            robot.governor.stop()
        else:
            robot.governor.command(*mix(linear, angular), req.duration_s)
        return {"accepted": True}

    @app.post("/api/drive")
    async def drive(req: DriveRequest) -> dict[str, Any]:
        robot.governor.command(*mix(req.linear, req.angular), req.duration_s)
        return {"accepted": True}

    @app.post("/api/stop")
    async def stop() -> dict[str, Any]:
        robot.governor.stop()
        return {"accepted": True}

    @app.post("/api/estop")
    async def estop() -> dict[str, Any]:
        robot.governor.estop()
        return {"estop": True}

    @app.post("/api/estop/release")
    async def estop_release() -> dict[str, Any]:
        robot.governor.release()
        return {"estop": False}

    @app.post("/api/intent")
    async def intent(req: Intent) -> dict[str, Any]:
        robot.behavior.handle(req)
        return {"intent": req.model_dump(), "behavior": robot.behavior.state.value}

    @app.post("/api/ai/command")
    async def ai_command(req: CommandRequest) -> dict[str, Any]:
        if robot.planner is None:
            raise HTTPException(503, "no AI provider configured")
        planned = await robot.planner.plan(req.text)
        if planned is None:
            raise HTTPException(422, "AI produced no valid intent")
        robot.behavior.handle(planned)
        return {"intent": planned.model_dump(), "behavior": robot.behavior.state.value}

    @app.post("/api/sim/range")
    async def sim_range(req: SimRangeRequest) -> dict[str, Any]:
        if robot.sim_world is None:
            raise HTTPException(404, "only available with the sim backend")
        robot.sim_world.range_mm = req.distance_mm
        return {"distance_mm": req.distance_mm}

    @app.websocket("/ws/telemetry")
    async def telemetry(ws: WebSocket) -> None:
        await ws.accept()
        min_interval = 1.0 / robot.config.api.telemetry_hz
        last_sent = float("-inf")
        try:
            async with robot.bus.subscribe(Topics.TELEMETRY, maxsize=1) as queue:
                while True:
                    message = await queue.get()
                    if message["time"] - last_sent >= min_interval:
                        last_sent = message["time"]
                        await ws.send_json(message)
        except WebSocketDisconnect:
            pass

    return app
