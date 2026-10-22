import pytest

from mirae.config import SafetyConfig
from mirae.core.clock import FakeClock
from mirae.safety.governor import SafetyGovernor


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def governor(clock: FakeClock) -> SafetyGovernor:
    gov = SafetyGovernor(SafetyConfig(), clock)
    gov.update_range(2000.0)
    return gov


def test_idle_outputs_zero(governor: SafetyGovernor) -> None:
    cmd, status = governor.output()
    assert (cmd.left, cmd.right) == (0.0, 0.0)
    assert status.limit is None


def test_command_passes_through(governor: SafetyGovernor) -> None:
    governor.command(0.3, 0.3)
    cmd, status = governor.output()
    assert (cmd.left, cmd.right) == (0.3, 0.3)
    assert status.limit is None


def test_deadman_expires_command(governor: SafetyGovernor, clock: FakeClock) -> None:
    governor.command(0.3, 0.3)
    clock.advance(0.49)
    governor.update_range(2000.0)
    assert governor.output()[0].left == 0.3
    clock.advance(0.02)
    assert governor.output()[0].left == 0.0


def test_duration_is_capped(governor: SafetyGovernor, clock: FakeClock) -> None:
    governor.command(0.3, 0.3, duration_s=60.0)
    clock.advance(5.01)
    governor.update_range(2000.0)
    assert governor.output()[0].left == 0.0


def test_speed_is_clamped(governor: SafetyGovernor) -> None:
    governor.command(1.0, -1.0)
    cmd, status = governor.output()
    assert (cmd.left, cmd.right) == (0.6, -0.6)
    assert status.limit == "max_speed"


def test_obstacle_blocks_forward_but_allows_turning(governor: SafetyGovernor) -> None:
    governor.update_range(100.0)
    governor.command(0.4, 0.4)
    cmd, status = governor.output()
    assert (cmd.left, cmd.right) == (0.0, 0.0)
    assert status.limit == "obstacle"

    governor.command(-0.3, 0.3)
    cmd, _ = governor.output()
    assert (cmd.left, cmd.right) == (-0.3, 0.3)

    governor.command(-0.3, -0.3)
    cmd, _ = governor.output()
    assert (cmd.left, cmd.right) == (-0.3, -0.3)


def test_slow_zone_scales_forward(governor: SafetyGovernor) -> None:
    governor.update_range(210.0)  # halfway between stop (120) and slow (300)
    governor.command(0.4, 0.4)
    cmd, status = governor.output()
    assert cmd.left == pytest.approx(0.2)
    assert cmd.right == pytest.approx(0.2)
    assert status.limit == "slow_zone"


def test_stale_range_blocks_forward(governor: SafetyGovernor, clock: FakeClock) -> None:
    clock.advance(1.0)
    governor.command(0.3, 0.3)
    cmd, status = governor.output()
    assert (cmd.left, cmd.right) == (0.0, 0.0)
    assert status.limit == "no_range"


def test_release_does_not_resume_motion(governor: SafetyGovernor) -> None:
    governor.command(0.3, 0.3, duration_s=5.0)
    governor.estop()
    governor.command(0.3, 0.3, duration_s=5.0)
    governor.release()
    assert governor.output()[0].left == 0.0


def test_estop_latches_until_released(governor: SafetyGovernor) -> None:
    governor.estop()
    governor.command(0.3, 0.3)
    assert governor.output()[0].left == 0.0
    governor.release()
    governor.command(0.3, 0.3)
    assert governor.output()[0].left == 0.3
