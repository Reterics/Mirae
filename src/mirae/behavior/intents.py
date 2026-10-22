"""The complete vocabulary the AI layer may use. Anything else is rejected.

Speeds and durations are bounded here, and bounded again by the safety governor.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

Speed = Annotated[float, Field(ge=0.0, le=1.0)]
Duration = Annotated[float, Field(gt=0.0, le=5.0)]


class _Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Stop(_Intent):
    action: Literal["stop"] = "stop"


class Move(_Intent):
    action: Literal["move"] = "move"
    direction: Literal["forward", "backward"]
    speed: Speed = 0.3
    duration_s: Duration = 1.0


class Turn(_Intent):
    action: Literal["turn"] = "turn"
    direction: Literal["left", "right"]
    speed: Speed = 0.3
    duration_s: Duration = 0.5


class ApproachPerson(_Intent):
    action: Literal["approach_person"] = "approach_person"
    speed: Annotated[float, Field(ge=0.0, le=0.5)] = 0.25


class FollowPerson(_Intent):
    action: Literal["follow_person"] = "follow_person"
    speed: Annotated[float, Field(ge=0.0, le=0.5)] = 0.25


class Explore(_Intent):
    action: Literal["explore"] = "explore"


class Say(_Intent):
    action: Literal["say"] = "say"
    text: Annotated[str, Field(min_length=1, max_length=500)]


class Sleep(_Intent):
    action: Literal["sleep"] = "sleep"


Intent = Annotated[
    Stop | Move | Turn | ApproachPerson | FollowPerson | Explore | Say | Sleep,
    Field(discriminator="action"),
]

intent_adapter: TypeAdapter[Intent] = TypeAdapter(Intent)
