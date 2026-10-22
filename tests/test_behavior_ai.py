import asyncio
import json

import pytest
from pydantic import ValidationError

from mirae.ai.planner import IntentPlanner
from mirae.ai.providers import ChatMessage, FakeProvider
from mirae.behavior.engine import BehaviorEngine, BehaviorState
from mirae.behavior.intents import Move, Turn, intent_adapter
from mirae.config import SafetyConfig
from mirae.core.bus import EventBus, Topics
from mirae.core.clock import FakeClock
from mirae.safety.governor import SafetyGovernor


def test_intent_parsing_and_bounds() -> None:
    intent = intent_adapter.validate_python({"action": "move", "direction": "forward"})
    assert isinstance(intent, Move)
    with pytest.raises(ValidationError):
        intent_adapter.validate_python({"action": "move", "direction": "up"})
    with pytest.raises(ValidationError):
        intent_adapter.validate_python({"action": "move", "direction": "forward", "speed": 5})
    with pytest.raises(ValidationError):
        intent_adapter.validate_python({"action": "set_gpio", "pin": 4})


def test_engine_turn_commands_governor() -> None:
    clock = FakeClock()
    governor = SafetyGovernor(SafetyConfig(), clock)
    governor.update_range(2000.0)
    engine = BehaviorEngine(governor, EventBus())

    engine.handle(Turn(direction="left", speed=0.4, duration_s=1.0))
    cmd, _ = governor.output()
    assert (cmd.left, cmd.right) == (-0.4, 0.4)


def test_engine_perception_states_fall_back_without_vision() -> None:
    bus = EventBus()
    engine = BehaviorEngine(SafetyGovernor(SafetyConfig(), FakeClock()), bus)
    engine.handle(intent_adapter.validate_python({"action": "follow_person"}))
    assert bus.latest(Topics.STATE) == BehaviorState.FOLLOW
    engine.tick()
    assert engine.state == BehaviorState.IDLE
    assert bus.latest(Topics.STATE) == BehaviorState.IDLE


def test_planner_with_fake_provider() -> None:
    planner = IntentPlanner(FakeProvider())
    intent = asyncio.run(planner.plan("please turn left"))
    assert isinstance(intent, Turn)
    assert intent.direction == "left"


class _BadProvider:
    async def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        return json.dumps({"action": "move", "direction": "forward", "speed": 99})

    async def aclose(self) -> None:
        pass


def test_planner_rejects_out_of_bounds_output() -> None:
    assert asyncio.run(IntentPlanner(_BadProvider()).plan("go fast")) is None


def test_bus_delivers_and_drops_oldest() -> None:
    async def scenario() -> list[int]:
        bus = EventBus()
        async with bus.subscribe("t", maxsize=2) as queue:
            for i in range(3):
                bus.publish("t", i)
            return [queue.get_nowait(), queue.get_nowait()]

    assert asyncio.run(scenario()) == [1, 2]
