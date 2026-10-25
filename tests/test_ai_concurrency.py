import asyncio

import httpx
import pytest

from mirae.ai.planner import IntentPlanner
from mirae.ai.providers import ChatMessage, FakeProvider
from mirae.api.accounts import AuthStore
from mirae.api.app import create_app
from mirae.config import AIConfig, MiraeConfig, SafetyConfig, load_config
from mirae.core.clock import MonotonicClock
from mirae.hardware.sim import build_sim
from mirae.robot import Robot


def attached_test_robot(config: MiraeConfig) -> Robot:
    hardware, _ = build_sim(config.drive, MonotonicClock())
    return Robot(
        config.model_copy(
            update={"hardware": config.hardware.model_copy(update={"backend": "pi"})}
        ),
        hardware=hardware,
    )


class DelayedProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        timeout_s: float | None = None,
    ) -> str:
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return '{"action":"move","direction":"forward"}'

    async def aclose(self) -> None:
        pass


@pytest.mark.parametrize("override", ["stop", "estop_release", "manual", "intent", "zero_drive"])
def test_newer_commands_invalidate_delayed_ai(override: str, test_token: str) -> None:
    async def scenario() -> None:
        config = load_config("local").model_copy(update={"safety": SafetyConfig(ramp_per_s=None)})
        robot = attached_test_robot(config)
        provider = DelayedProvider()
        robot.planner = IntentPlanner(provider)
        app = create_app(robot)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": f"Bearer {test_token}"},
            ) as client,
        ):
            await asyncio.sleep(0)  # let the runtime start before sending commands
            pending = asyncio.create_task(client.post("/api/ai/command", json={"text": "go"}))
            await asyncio.wait_for(provider.started.wait(), timeout=1.0)
            assert (await client.post("/api/ai/command", json={"text": "go"})).status_code == 429
            if override == "estop_release":
                assert (await client.post("/api/estop")).status_code == 200
                assert (await client.post("/api/estop/release")).status_code == 200
            elif override == "manual":
                assert (await client.post("/api/drive", json={"linear": -0.2})).status_code == 200
            elif override == "zero_drive":
                assert (await client.post("/api/drive", json={})).status_code == 200
            elif override == "intent":
                assert (
                    await client.post("/api/intent", json={"action": "sleep"})
                ).status_code == 200
            else:
                assert (await client.post("/api/stop")).status_code == 200
            provider.release.set()
            assert (await pending).status_code == 409
            assert robot.governor.output()[0].left == (-0.2 if override == "manual" else 0.0)

    asyncio.run(scenario())


def test_ai_timeout_releases_capacity_without_motion(test_token: str) -> None:
    async def scenario() -> None:
        config = load_config("local").model_copy(update={"ai": AIConfig(command_ttl_s=0.03)})
        robot = attached_test_robot(config)
        provider = DelayedProvider()
        robot.planner = IntentPlanner(provider)
        app = create_app(robot)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": f"Bearer {test_token}"},
            ) as client,
        ):
            await asyncio.sleep(0)
            result = await client.post("/api/ai/command", json={"text": "go"})
            assert result.status_code == 504
            assert provider.cancelled
            assert robot.governor.output()[0].left == 0.0
            robot.planner = IntentPlanner(FakeProvider())
            assert (await client.post("/api/ai/command", json={"text": "stop"})).status_code == 200

    asyncio.run(scenario())


def test_revoked_token_cannot_execute_a_pending_ai_result(
    test_token: str,
    account_store: AuthStore,
) -> None:
    async def scenario() -> None:
        config = load_config("local").model_copy(update={"safety": SafetyConfig(ramp_per_s=None)})
        robot = attached_test_robot(config)
        provider = DelayedProvider()
        robot.planner = IntentPlanner(provider)
        app = create_app(robot)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": f"Bearer {test_token}"},
            ) as client,
        ):
            await asyncio.sleep(0)
            pending = asyncio.create_task(client.post("/api/ai/command", json={"text": "go"}))
            await asyncio.wait_for(provider.started.wait(), timeout=1.0)
            token_id = account_store.tokens()[0]["id"]
            await asyncio.to_thread(account_store.revoke_token, token_id, "test")
            provider.release.set()
            assert (await pending).status_code == 401
            assert robot.governor.output()[0].left == 0.0

    asyncio.run(scenario())
