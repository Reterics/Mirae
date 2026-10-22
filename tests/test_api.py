from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mirae.api.app import create_app
from mirae.config import load_config
from mirae.robot import Robot


@pytest.fixture
def robot() -> Robot:
    return Robot(load_config("sim"))


@pytest.fixture
def client(robot: Robot) -> Iterator[TestClient]:
    with TestClient(create_app(robot)) as c:
        yield c


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_status_reports_sim_backend(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["backend"] == "sim"
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


def test_sim_range_endpoint(client: TestClient, robot: Robot) -> None:
    client.post("/api/sim/range", json={"distance_mm": 50})
    assert robot.sim_world is not None
    assert robot.sim_world.range_mm == 50


def test_telemetry_websocket(client: TestClient) -> None:
    with client.websocket_connect("/ws/telemetry") as ws:
        message = ws.receive_json()
    assert message["backend"] == "sim"
    assert "pose" in message
