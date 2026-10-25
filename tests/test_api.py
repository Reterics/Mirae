from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mirae.ai.planner import IntentPlanner
from mirae.ai.providers import FakeProvider
from mirae.api.app import create_app
from mirae.config import load_config
from mirae.core.clock import MonotonicClock
from mirae.hardware.sim import build_sim
from mirae.robot import Robot


@pytest.fixture
def robot() -> Robot:
    config = load_config("local")
    hardware, _ = build_sim(config.drive, MonotonicClock())
    robot = Robot(
        config.model_copy(
            update={
                "hardware": config.hardware.model_copy(update={"backend": "pi"}),
            }
        ),
        hardware=hardware,
    )
    robot.planner = IntentPlanner(FakeProvider())
    return robot


@pytest.fixture
def client(robot: Robot, test_token: str) -> Iterator[TestClient]:
    with TestClient(create_app(robot), headers={"Authorization": f"Bearer {test_token}"}) as c:
        yield c


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_status_reports_configured_backend(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["backend"] == "pi"
    assert body["behavior"] == "IDLE"


def test_movement_reaches_governor(client: TestClient, robot: Robot) -> None:
    response = client.post("/api/movement", json={"action": "forward", "speed": 0.3})
    assert response.status_code == 200
    assert robot.governor._target.left == pytest.approx(0.3)


def test_movement_rejects_bad_speed(client: TestClient) -> None:
    response = client.post("/api/movement", json={"action": "forward", "speed": 2})
    assert response.status_code == 422


def test_estop_blocks_motion(client: TestClient, robot: Robot) -> None:
    client.post("/api/estop")
    client.post("/api/movement", json={"action": "forward", "speed": 0.3})
    cmd, status = robot.governor.output()
    assert cmd.left == 0.0
    assert status.estop
    client.post("/api/estop/release")
    assert not robot.governor.estopped


def test_intent_endpoint(client: TestClient) -> None:
    response = client.post("/api/intent", json={"action": "explore"})
    assert response.status_code == 200
    assert response.json()["intent"]["action"] == "explore"


def test_ai_command_with_fake_provider(client: TestClient) -> None:
    response = client.post("/api/ai/command", json={"text": "stop right now"})
    assert response.status_code == 200
    assert response.json()["intent"]["action"] == "stop"


def test_simulation_endpoint_is_not_exposed(client: TestClient, robot: Robot) -> None:
    assert client.post("/api/sim/range", json={"distance_mm": 50}).status_code == 404


def test_telemetry_websocket(client: TestClient) -> None:
    with client.websocket_connect("/ws/telemetry") as ws:
        message = ws.receive_json()
    assert message["backend"] == "pi"
    assert "pose" in message


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/drive", '{"linear":"NaN"}'),
        ("/api/drive", '{"duration_s":"Infinity"}'),
        ("/api/drive", '{"liner":0.3}'),
        ("/api/movement", '{"action":"forward","speed":"Infinity"}'),
    ],
)
def test_api_rejects_nonfinite_values_and_unknown_fields(
    client: TestClient,
    path: str,
    body: str,
) -> None:
    assert (
        client.post(path, content=body, headers={"Content-Type": "application/json"}).status_code
        == 422
    )
