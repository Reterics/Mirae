import pytest

from mirae.config import SafetyConfig
from mirae.core.clock import FakeClock
from mirae.safety.governor import SafetyGovernor


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def governor(clock: FakeClock) -> SafetyGovernor:
    # The other rules are tested without the ramp; the ramp has its own tests below.
    gov = SafetyGovernor(SafetyConfig(ramp_per_s=None), clock)
    gov.update_range(2000.0)
    return gov


@pytest.fixture
def ramped(clock: FakeClock) -> SafetyGovernor:
    gov = SafetyGovernor(SafetyConfig(), clock)  # default ramp: 1.5 duty per second
    gov.update_range(2000.0)
    return gov


def _tick(gov: SafetyGovernor, clock: FakeClock, dt: float = 0.1) -> tuple[float, float]:
    clock.advance(dt)
    gov.update_range(2000.0)
    cmd, _ = gov.output()
    return cmd.left, cmd.right


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


def test_ramp_limits_speeding_up(ramped: SafetyGovernor, clock: FakeClock) -> None:
    ramped.command(0.6, 0.6, duration_s=5.0)
    cmd, status = ramped.output()
    assert (cmd.left, cmd.right) == (0.0, 0.0)
    assert status.limit == "ramp"
    assert _tick(ramped, clock) == pytest.approx((0.15, 0.15))
    assert _tick(ramped, clock) == pytest.approx((0.3, 0.3))
    _tick(ramped, clock)
    assert _tick(ramped, clock) == pytest.approx((0.6, 0.6))
    assert ramped.output()[1].limit is None


def test_ramp_holds_across_resent_commands(ramped: SafetyGovernor, clock: FakeClock) -> None:
    for expected in (0.15, 0.3, 0.45):
        ramped.command(0.6, 0.6)  # a joystick client re-sending every tick
        assert _tick(ramped, clock)[0] == pytest.approx(expected)


def test_ramp_never_delays_a_stop(ramped: SafetyGovernor, clock: FakeClock) -> None:
    ramped.command(0.6, 0.6, duration_s=5.0)
    for _ in range(4):
        _tick(ramped, clock)
    ramped.command(0.2, 0.2, duration_s=5.0)
    assert _tick(ramped, clock, 0.0) == pytest.approx((0.2, 0.2))  # slowing down: at once
    ramped.estop()
    assert _tick(ramped, clock, 0.0) == (0.0, 0.0)


def test_ramp_restarts_after_deadman(ramped: SafetyGovernor, clock: FakeClock) -> None:
    ramped.command(0.6, 0.6, duration_s=0.4)
    for _ in range(4):
        _tick(ramped, clock)
    assert _tick(ramped, clock) == (0.0, 0.0)  # expired: zero at once
    ramped.command(0.6, 0.6)
    assert _tick(ramped, clock) == pytest.approx((0.15, 0.15))


def test_ramp_reversal_starts_from_zero(ramped: SafetyGovernor, clock: FakeClock) -> None:
    ramped.command(0.3, 0.3, duration_s=5.0)
    _tick(ramped, clock)
    _tick(ramped, clock)
    ramped.command(-0.3, -0.3, duration_s=5.0)
    assert _tick(ramped, clock) == pytest.approx((-0.15, -0.15))


def test_ramp_step_is_capped_after_a_stall(ramped: SafetyGovernor, clock: FakeClock) -> None:
    ramped.command(0.6, 0.6, duration_s=5.0)
    assert _tick(ramped, clock, 2.0) == pytest.approx((0.15, 0.15))


@pytest.mark.parametrize("distance", [None, 50.0, 210.0])
@pytest.mark.parametrize("target", [(0.6, -0.2), (-0.2, 0.6), (0.6, 0.2), (-0.6, 0.6)])
def test_combined_ramp_and_range_never_exceed_safe_forward_component(
    ramped: SafetyGovernor,
    clock: FakeClock,
    distance: float | None,
    target: tuple[float, float],
) -> None:
    ramped.command(0.6, 0.6, duration_s=5.0)
    for _ in range(4):
        _tick(ramped, clock)
    ramped.command(*target, duration_s=5.0)
    permitted_forward = max(0.0, sum(target) / 2.0) * (0.5 if distance == 210.0 else 0.0)
    for _ in range(10):
        clock.advance(0.02)
        ramped.update_range(distance)
        cmd, _ = ramped.output()
        assert (cmd.left + cmd.right) / 2.0 <= permitted_forward + 1e-12
        assert abs(cmd.left) <= 0.6
        assert abs(cmd.right) <= 0.6


@pytest.mark.parametrize("distance", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_invalid_sensor_data_blocks_forward(governor: SafetyGovernor, distance: float) -> None:
    governor.update_range(distance)
    governor.command(0.3, 0.3)
    cmd, status = governor.output()
    assert (cmd.left, cmd.right) == (0.0, 0.0)
    assert status.limit == "no_range"
    assert status.range_mm is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_invalid_internal_command_clears_previous_motion(
    governor: SafetyGovernor,
    value: float,
) -> None:
    governor.command(0.3, 0.3)
    governor.command(value, 0.3)
    assert governor.output()[0].left == 0.0
    governor.command(0.3, 0.3, duration_s=value)
    assert governor.output()[0].left == 0.0


def test_worker_delivery_does_not_refresh_an_old_measurement(
    governor: SafetyGovernor,
    clock: FakeClock,
) -> None:
    clock.advance(1.0)
    governor.update_range(2000.0, observed_at=0.0)
    governor.command(0.3, 0.3)
    assert governor.output()[1].limit == "no_range"
