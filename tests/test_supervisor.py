import asyncio

import pytest
import uvicorn
from fastapi import FastAPI

from mirae.cli import _serve
from mirae.config import load_config
from mirae.core.clock import MonotonicClock
from mirae.hardware.sim import build_sim
from mirae.robot import Robot


def test_runtime_failure_shuts_down_server_and_exits_with_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_config("local")
    hardware, world = build_sim(config.drive, MonotonicClock())
    robot = Robot(
        config.model_copy(
            update={"hardware": config.hardware.model_copy(update={"backend": "pi"})}
        ),
        hardware=hardware,
    )

    def broken_step() -> None:
        raise OSError("encoder disconnected")

    monkeypatch.setattr(robot.drive, "step", broken_step)
    monkeypatch.setattr("mirae.robot.Robot", lambda config: robot)

    class InProcessServer:
        def __init__(self, config: uvicorn.Config) -> None:
            assert isinstance(config.app, FastAPI)
            self.app = config.app
            self._exit = asyncio.Event()

        @property
        def should_exit(self) -> bool:
            return self._exit.is_set()

        @should_exit.setter
        def should_exit(self, value: bool) -> None:
            if value:
                self._exit.set()

        async def serve(self) -> None:
            async with self.app.router.lifespan_context(self.app):
                await asyncio.wait_for(self._exit.wait(), timeout=1.0)

    monkeypatch.setattr(uvicorn, "Server", InProcessServer)
    with pytest.raises(RuntimeError, match="control loop stopped"):
        asyncio.run(_serve(config, "info"))
    assert not robot.healthy
    assert world.speeds == (0.0, 0.0)
