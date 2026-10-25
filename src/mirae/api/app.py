"""HTTP + WebSocket API.

Movement commands expire. Without ``duration_s`` a command lasts
``safety.command_timeout_s`` (0.5 s by default), so a joystick-style client must
keep re-sending while the stick is held. ``duration_s`` is capped at
``safety.max_command_duration_s``. Obstacle and speed limits always apply.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import resources
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from mirae import __version__
from mirae.api.access_routes import access_router
from mirae.api.accounts import AccountError, AuthStore
from mirae.api.middleware import SecurityMiddleware
from mirae.api.pipeline_routes import pipeline_router
from mirae.api.security import ApiAuth
from mirae.behavior.intents import (
    ApproachPerson,
    Explore,
    FollowPerson,
    Intent,
    Move,
    Sleep,
    Turn,
)
from mirae.core.bus import Topics
from mirae.drive.kinematics import mix
from mirae.pipeline.manager import PipelineManager
from mirae.robot import Robot
from mirae.speech.speaker import Speaker
from mirae.story.store import MAX_CAST, Character, Episode, StoryState, StoryStore
from mirae.story.teller import StoryError, StoryTeller

Unit = Annotated[float, Field(ge=0.0, le=1.0)]
Signed = Annotated[float, Field(ge=-1.0, le=1.0)]
OptDuration = Annotated[float | None, Field(gt=0.0)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class MovementRequest(RequestModel):
    action: Literal["forward", "backward", "left", "right", "stop"]
    speed: Unit = 0.3
    duration_s: OptDuration = None


class DriveRequest(RequestModel):
    linear: Signed = 0.0
    angular: Signed = 0.0
    duration_s: OptDuration = None


class CommandRequest(RequestModel):
    text: Annotated[str, Field(min_length=1, max_length=500)]


class StoryStartRequest(RequestModel):
    premise: Annotated[str, Field(min_length=1, max_length=1000)]
    genre: Annotated[str, Field(min_length=1, max_length=60)]
    protagonist: Annotated[str, Field(min_length=1, max_length=40)]
    cast: Annotated[list[Character], Field(min_length=1, max_length=MAX_CAST)]


class SayRequest(RequestModel):
    text: Annotated[str, Field(min_length=1, max_length=5000)]


class StoryTellRequest(RequestModel):
    sleep: bool = False


class ActionToggleRequest(RequestModel):
    enabled: bool


# Optional things Mirae can do, each switched on or off from the dashboard.
ACTIONS = {
    "story": (
        "Story",
        "Tells one continuing story, a new episode each night, and remembers the cast.",
    ),
}


def episode_json(episode: Episode) -> dict[str, Any]:
    return {"night": episode.night, "text": episode.text, "created_at": episode.created_at}


def create_app(robot: Robot) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await robot.start()
        speaking = asyncio.create_task(speaker.run(), name="speaker")
        try:
            yield
        finally:
            speaking.cancel()
            await asyncio.gather(speaking, return_exceptions=True)
            await robot.stop()

    store = AuthStore(robot.config.api.database_path)
    auth = ApiAuth(store)
    app = FastAPI(
        title="Mirae",
        version=__version__,
        lifespan=lifespan,
        dependencies=[Depends(auth)],
        docs_url=None,
        redoc_url=None,
    )
    app.state.robot = robot
    app.state.accounts = store
    app.add_middleware(SecurityMiddleware)
    app.include_router(access_router(store, robot.config.api))
    manager = PipelineManager(store, robot)
    speaker = Speaker(
        robot.bus, lambda: robot.config.speech, lambda: manager.settings.secret("elevenlabs")
    )
    app.state.pipeline = manager
    app.include_router(pipeline_router(manager))
    static = str(resources.files("mirae").joinpath("admin"))
    app.mount("/admin/assets", StaticFiles(directory=static), name="admin-assets")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/admin")

    @app.get("/admin", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(str(resources.files("mirae").joinpath("admin/index.html")))

    @app.exception_handler(AccountError)
    async def account_error(_: Request, error: AccountError) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    planning = asyncio.Lock()
    stories = StoryStore(store)
    teller = StoryTeller(stories, lambda: robot._provider, lambda: robot.config.ai)

    def require_healthy() -> None:
        if not robot.healthy:
            raise HTTPException(503, "robot runtime is not healthy")

    def require_motors() -> None:
        require_healthy()
        if not robot.hardware_connected:
            raise HTTPException(503, "physical motor hardware is not available")

    def require_intent_hardware(value: Intent) -> None:
        if isinstance(value, Move | Turn | ApproachPerson | FollowPerson | Explore):
            require_motors()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        require_healthy()
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
            robot.halt()
        else:
            require_motors()
            robot.governor.command(*mix(linear, angular), req.duration_s)
        return {"accepted": True}

    @app.post("/api/drive")
    async def drive(req: DriveRequest) -> dict[str, Any]:
        require_healthy()
        if req.linear == req.angular == 0.0:
            robot.halt()
            return {"accepted": True}
        require_motors()
        robot.governor.command(*mix(req.linear, req.angular), req.duration_s)
        return {"accepted": True}

    @app.post("/api/stop")
    async def stop() -> dict[str, Any]:
        robot.halt()
        return {"accepted": True}

    @app.post("/api/estop")
    async def estop() -> dict[str, Any]:
        robot.halt(estop=True)
        return {"estop": True}

    @app.post("/api/estop/release")
    async def estop_release() -> dict[str, Any]:
        require_healthy()
        robot.governor.release()
        return {"estop": False}

    @app.post("/api/intent")
    async def intent(req: Intent) -> dict[str, Any]:
        require_healthy()
        require_intent_hardware(req)
        robot.behavior.handle(req)
        return {"intent": req.model_dump(), "behavior": robot.behavior.state.value}

    @app.post("/api/ai/command")
    async def ai_command(req: CommandRequest, request: Request) -> dict[str, Any]:
        require_healthy()
        if robot.planner is None:
            raise HTTPException(503, "no AI provider configured")
        if planning.locked():
            raise HTTPException(429, "another AI command is being planned")
        async with planning:
            revision = robot.governor.revision
            submitted_at = asyncio.get_running_loop().time()
            try:
                planned = await asyncio.wait_for(
                    robot.planner.plan(req.text),
                    timeout=min(robot.config.ai.timeout_s, robot.config.ai.command_ttl_s),
                )
            except TimeoutError as exc:
                raise HTTPException(504, "AI command expired") from exc
            require_healthy()
            # Permissions and revocation may have changed while the LLM waited.
            await auth.authorize(request)
            if asyncio.get_running_loop().time() - submitted_at >= robot.config.ai.command_ttl_s:
                raise HTTPException(504, "AI command expired")
            if robot.governor.revision != revision:
                raise HTTPException(409, "AI command superseded by a newer command or stop")
            if planned is None:
                raise HTTPException(422, "AI produced no valid intent")
            require_intent_hardware(planned)
            robot.behavior.handle(planned)
        return {"intent": planned.model_dump(), "behavior": robot.behavior.state.value}

    @app.get("/api/speech")
    async def speech() -> dict[str, Any]:
        return {**speaker.snapshot(), "tts": robot.config.speech.tts}

    @app.get("/api/speech/last.wav")
    async def last_speech() -> Response:
        audio = await asyncio.to_thread(speaker.wav)
        if audio is None:
            raise HTTPException(404, "nothing has been spoken yet")
        return Response(audio, media_type="audio/wav")

    @app.post("/api/speech/say")
    async def say(req: SayRequest) -> dict[str, bool]:
        robot.bus.publish(Topics.SAY, req.text)
        return {"accepted": True}

    @app.post("/api/speech/stop")
    async def stop_speech() -> dict[str, bool]:
        speaker.stop()
        return {"stopped": True}

    def action_enabled(name: str) -> bool:
        return bool(manager.settings.value(f"action:{name}", True))

    def require_action(name: str) -> None:
        if not action_enabled(name):
            raise HTTPException(409, f"the {ACTIONS[name][0]} action is turned off")

    def actions_json() -> list[dict[str, Any]]:
        return [
            {"id": name, "name": label, "description": text, "enabled": action_enabled(name)}
            for name, (label, text) in ACTIONS.items()
        ]

    @app.get("/api/actions")
    async def actions() -> dict[str, Any]:
        return {"actions": await asyncio.to_thread(actions_json)}

    @app.put("/api/actions/{name}")
    async def toggle_action(
        name: str, req: ActionToggleRequest, request: Request
    ) -> dict[str, Any]:
        if name not in ACTIONS:
            raise HTTPException(404, "unknown action")
        await asyncio.to_thread(
            manager.settings.set_value,
            f"action:{name}",
            req.enabled,
            request.state.principal.username,
        )
        if name == "story" and not req.enabled:
            speaker.stop()
        return {"actions": await asyncio.to_thread(actions_json)}

    @app.get("/api/story")
    async def story() -> dict[str, Any]:
        state = await asyncio.to_thread(stories.load)
        episodes = await asyncio.to_thread(stories.episodes)
        return {
            "story": state.model_dump() if state else None,
            "episodes": [episode_json(e) for e in episodes],
            "writing": teller.busy,
        }

    @app.put("/api/story")
    async def start_story(req: StoryStartRequest) -> dict[str, Any]:
        """Start a new story. This replaces the current one and its episodes."""
        require_action("story")
        if teller.busy:
            raise HTTPException(409, "an episode is being written")
        try:
            state = StoryState(
                premise=req.premise,
                genre=req.genre,
                protagonist=req.protagonist,
                cast=req.cast,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        await asyncio.to_thread(stories.reset, state)
        return {"story": state.model_dump(), "episodes": []}

    @app.post("/api/story/tell")
    async def tell_story(req: StoryTellRequest, request: Request) -> dict[str, Any]:
        """Write tonight's episode and say it. With ``sleep``, Mirae sleeps afterwards."""
        require_action("story")
        if req.sleep:
            require_healthy()
        try:
            result = await teller.tell()
        except StoryError as exc:
            raise HTTPException(exc.status, exc.detail) from exc
        # Permissions and revocation may have changed while the LLM wrote.
        await auth.authorize(request)
        robot.bus.publish(Topics.SAY, result.episode.text)
        # The episode is already saved; losing health meanwhile only skips sleeping.
        if req.sleep and robot.healthy:
            robot.behavior.handle(Sleep())
        return {
            "episode": episode_json(result.episode),
            "story": result.state.model_dump(),
            "continuity_updated": result.continuity_updated,
            "changes": result.notes,
            "behavior": robot.behavior.state.value,
        }

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
                        await auth.authorize(ws)
                        last_sent = message["time"]
                        await ws.send_json(message)
        except WebSocketDisconnect:
            pass

    return app
