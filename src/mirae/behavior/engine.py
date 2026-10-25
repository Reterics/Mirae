from __future__ import annotations

import logging
from enum import StrEnum

from mirae.behavior.intents import (
    ApproachPerson,
    Explore,
    FollowPerson,
    Intent,
    Move,
    Say,
    Sleep,
    Stop,
    Turn,
)
from mirae.core.bus import EventBus, Topics
from mirae.safety.governor import SafetyGovernor

log = logging.getLogger(__name__)


class BehaviorState(StrEnum):
    IDLE = "IDLE"
    EXPLORE = "EXPLORE"
    FOLLOW = "FOLLOW"
    APPROACH = "APPROACH"
    AVOID = "AVOID"
    LISTEN = "LISTEN"
    SPEAK = "SPEAK"
    SLEEP = "SLEEP"


class BehaviorEngine:
    """Deterministic state machine between intents and the safety governor.

    Simple intents (move, turn, stop) map straight to bounded governor commands.
    Perception-driven states (FOLLOW, APPROACH, EXPLORE) are driven by ``tick``,
    which until the vision pipeline lands (V0.3) falls back to IDLE.
    """

    def __init__(self, governor: SafetyGovernor, bus: EventBus) -> None:
        self._governor = governor
        self._bus = bus
        self.state = BehaviorState.IDLE

    def _set_state(self, state: BehaviorState) -> None:
        if state != self.state:
            log.info("behavior %s -> %s", self.state, state)
            self.state = state
            self._bus.publish(Topics.STATE, state)

    def handle(self, intent: Intent) -> None:
        self._governor.invalidate_pending()
        self._bus.publish(Topics.INTENT, intent)
        match intent:
            case Stop():
                self._governor.stop()
                self._set_state(BehaviorState.IDLE)
            case Move(direction=direction, speed=speed, duration_s=duration):
                v = speed if direction == "forward" else -speed
                self._governor.command(v, v, duration)
                self._set_state(BehaviorState.IDLE)
            case Turn(direction=direction, speed=speed, duration_s=duration):
                v = speed if direction == "left" else -speed
                self._governor.command(-v, v, duration)
                self._set_state(BehaviorState.IDLE)
            case ApproachPerson():
                self._set_state(BehaviorState.APPROACH)
            case FollowPerson():
                self._set_state(BehaviorState.FOLLOW)
            case Explore():
                self._set_state(BehaviorState.EXPLORE)
            case Say(text=text):
                self._bus.publish(Topics.SAY, text)
            case Sleep():
                self._governor.stop()
                self._set_state(BehaviorState.SLEEP)

    def tick(self) -> None:
        if self.state in (BehaviorState.FOLLOW, BehaviorState.APPROACH, BehaviorState.EXPLORE):
            # TODO(V0.3/V0.6): drive from vision.detections and range data.
            log.warning("%s needs the vision pipeline; returning to IDLE", self.state)
            self._governor.stop()
            self._set_state(BehaviorState.IDLE)
