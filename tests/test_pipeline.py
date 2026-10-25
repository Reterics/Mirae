from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from mirae.api.accounts import AuthStore
from mirae.api.app import create_app
from mirae.config import load_config
from mirae.pipeline.settings import ConnectionInput, PipelineSettings, load_managed_config
from mirae.robot import Robot


@pytest.fixture
def pipeline_client(test_token: str) -> Iterator[TestClient]:
    with TestClient(
        create_app(Robot(load_config("local"))), headers={"Authorization": f"Bearer {test_token}"}
    ) as client:
        yield client


def connection(client: TestClient, **changes: Any) -> dict[str, Any]:
    data = {
        "name": "Test endpoint",
        "provider": "ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "local-test-model",
        **changes,
    }
    response = client.post("/api/admin/pipeline/connections", json=data)
    assert response.status_code == 201, response.text
    return {"id": response.json()["id"], **data}


def fake_endpoint(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_no_seeded_connections_and_no_readings_without_physical_hardware(
    pipeline_client: TestClient,
) -> None:
    client = pipeline_client
    assert client.get("/api/admin/pipeline/connections").json() == []
    data = client.get("/api/admin/pipeline").json()
    assert data["runtime_llm"]["provider"] == "none"
    assert data["runtime_llm"]["model"] is None
    assert data["hardware"]["physical"] is False
    assert data["hardware"]["backend"] == "none"
    assert data["hardware"]["motors"]["driver"] is None
    assert data["hardware"]["encoders"]["driver"] is None
    assert data["hardware"]["range"]["driver"] is None
    assert data["hardware"]["motors"]["output"] is None
    assert data["hardware"]["encoders"]["counts"] is None
    assert data["hardware"]["range"]["distance_mm"] is None
    assert data["local"]["vision"]["state"] == "disabled"
    assert data["local"]["speech"]["state"] == "disabled"
    assert data["host"]
    status = client.get("/api/status").json()
    assert status["runtime"]["healthy"] is True
    assert status["runtime"]["control_running"] is False
    assert status["runtime"]["max_tick_lateness_s"] is None
    assert status["runtime"]["missed_ticks"] is None
    assert all(status[field] is None for field in ("wheels", "encoders", "pose", "safety"))
    assert client.post("/api/drive", json={"linear": 0.2}).status_code == 503
    assert client.post("/api/intent", json={"action": "explore"}).status_code == 503
    assert client.post("/api/sim/range", json={"distance_mm": 50}).status_code == 404


def test_physical_initialization_failure_keeps_admin_available_without_inventing_readings(
    monkeypatch: pytest.MonkeyPatch, test_token: str
) -> None:
    monkeypatch.setattr(
        "mirae.hardware.pi.build_pi", Mock(side_effect=RuntimeError("GPIO unavailable"))
    )
    with TestClient(
        create_app(Robot(load_config("pi"))), headers={"Authorization": f"Bearer {test_token}"}
    ) as client:
        assert client.get("/api/health").status_code == 200
        data = client.get("/api/admin/pipeline").json()
        assert data["hardware"]["physical"] is False
        assert data["hardware"]["error"] == "RuntimeError: GPIO unavailable"
        assert data["hardware"]["motors"]["output"] is None
        assert data["hardware"]["encoders"]["counts"] is None
        assert data["hardware"]["range"]["distance_mm"] is None
        assert client.post("/api/drive", json={"linear": 0.2}).status_code == 503


def test_credentials_encrypted_and_never_returned(
    pipeline_client: TestClient, account_store: AuthStore
) -> None:
    item = connection(
        pipeline_client,
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="test-private-provider-secret",
    )
    listing = pipeline_client.get("/api/admin/pipeline/connections")
    assert "test-private-provider-secret" not in listing.text
    assert listing.json()[0]["has_api_key"] is True
    with account_store.connection() as db:
        row = db.execute(
            "SELECT config,secret FROM pipeline_connections WHERE id=?", (item["id"],)
        ).fetchone()
        assert "test-private-provider-secret" not in row["config"]
        assert b"test-private-provider-secret" not in row["secret"]
    cfg, key = PipelineSettings(account_store).connection(item["id"])
    assert key == "test-private-provider-secret"
    assert cfg.provider == "openai"
    assert account_store.path.with_suffix(".key").is_file()
    assert "test-private-provider-secret" not in pipeline_client.get("/api/admin/audit").text


def test_endpoint_change_does_not_forward_saved_credentials(
    pipeline_client: TestClient, account_store: AuthStore
) -> None:
    item = connection(pipeline_client, api_key="test-provider-key")
    item.pop("api_key")
    item["base_url"] = "http://localhost:1234/v1"
    item.pop("id")
    connection_id = pipeline_client.get("/api/admin/pipeline/connections").json()[0]["id"]
    assert (
        pipeline_client.put(
            f"/api/admin/pipeline/connections/{connection_id}", json=item
        ).status_code
        == 200
    )
    assert PipelineSettings(account_store).connection(connection_id)[1] is None


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:secret@localhost/v1",
        "http://169.254.169.254/v1",
        "http://localhost/v1?key=secret",
        "http://localhost/v1#fragment",
    ],
)
def test_invalid_connection_targets_are_rejected(pipeline_client: TestClient, url: str) -> None:
    response = pipeline_client.post(
        "/api/admin/pipeline/connections",
        json={
            "name": "Invalid",
            "provider": "openai_compat",
            "base_url": url,
        },
    )
    assert response.status_code == 422


def test_real_model_check_selection_and_disable(
    pipeline_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    account_store: AuthStore,
) -> None:
    requests: list[httpx.Request] = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "local-test-model"}]})
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"action":"stop"}'}}]}
        )

    fake_endpoint(monkeypatch, endpoint)
    item = connection(pipeline_client, api_key="test-local-provider-key")
    checked = pipeline_client.post(f"/api/admin/pipeline/connections/{item['id']}/check").json()
    assert checked["ok"] is True
    assert checked["models"] == ["local-test-model"]
    assert checked["http_status"] == 200 and checked["latency_ms"] >= 0
    assert (
        pipeline_client.post(
            "/api/admin/pipeline/selection", json={"connection_id": item["id"]}
        ).status_code
        == 200
    )
    assert (
        pipeline_client.get("/api/admin/pipeline").json()["runtime_llm"]["model"]
        == "local-test-model"
    )
    assert pipeline_client.post("/api/ai/command", json={"text": "stop"}).status_code == 200
    assert all(
        request.headers.get("authorization") == "Bearer test-local-provider-key"
        for request in requests
    )
    saved = PipelineSettings(account_store).desired_config(load_config("local"))
    assert saved.ai.api_key is not None
    assert saved.ai.api_key.get_secret_value() == "test-local-provider-key"
    assert "test-local-provider-key" not in saved.model_dump_json()
    assert (
        pipeline_client.delete(f"/api/admin/pipeline/connections/{item['id']}").status_code == 409
    )
    assert (
        pipeline_client.post(
            "/api/admin/pipeline/selection", json={"connection_id": None}
        ).status_code
        == 200
    )
    assert (
        pipeline_client.delete(f"/api/admin/pipeline/connections/{item['id']}").status_code == 200
    )


def test_failed_check_does_not_claim_connected_or_leak_response(
    pipeline_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_endpoint(
        monkeypatch, lambda req: httpx.Response(401, json={"secret": "sensitive-upstream-body"})
    )
    item = connection(pipeline_client)
    response = pipeline_client.post(f"/api/admin/pipeline/connections/{item['id']}/check")
    assert response.json()["ok"] is False
    assert response.json()["http_status"] == 401
    assert "sensitive-upstream-body" not in response.text
    assert (
        pipeline_client.post(
            "/api/admin/pipeline/selection", json={"connection_id": item["id"]}
        ).status_code
        == 422
    )
    assert pipeline_client.get("/api/admin/pipeline").json()["runtime_llm"]["provider"] == "none"


def test_config_is_staged_validated_and_loaded_on_restart(
    pipeline_client: TestClient, account_store: AuthStore
) -> None:
    client = pipeline_client
    assert (
        client.put("/api/admin/pipeline/config/drive", json={"wheel_diameter_mm": 45}).status_code
        == 200
    )
    data = client.get("/api/admin/pipeline").json()
    assert data["config"]["drive"]["wheel_diameter_mm"] == 45
    assert data["active_config"]["drive"]["wheel_diameter_mm"] == 42
    assert "drive" in data["pending_restart"]
    assert (
        client.put(
            "/api/admin/pipeline/config/hardware", json={"motor_pins": {"pwma": 17}}
        ).status_code
        == 422
    )
    assert (
        client.put("/api/admin/pipeline/config/safety", json={"stop_distance_mm": -1}).status_code
        == 422
    )
    assert client.put("/api/admin/pipeline/config/drive", json={"unknown": True}).status_code == 422
    cfg = load_config("local")
    cfg = cfg.model_copy(
        update={"api": cfg.api.model_copy(update={"database_path": str(account_store.path)})}
    )
    assert load_managed_config(cfg).drive.wheel_diameter_mm == 45


def test_pipeline_requires_explicit_permission(
    pipeline_client: TestClient, account_store: AuthStore
) -> None:
    user = account_store.create_user("observer", "Observer", "long-test-password", "viewer")
    principal = account_store.authenticate(
        pipeline_client.headers["authorization"].split()[1], "token"
    )
    assert principal is not None
    token = account_store.issue_token(user["id"], "read-only", ["robot:read"], 1, principal)
    headers = {"Authorization": f"Bearer {token['secret']}"}
    assert pipeline_client.get("/api/admin/pipeline", headers=headers).status_code == 403
    assert (
        pipeline_client.post("/api/admin/pipeline/dependencies/check", headers=headers).status_code
        == 403
    )


def test_dependency_check_reports_measured_environment(pipeline_client: TestClient) -> None:
    response = pipeline_client.post("/api/admin/pipeline/dependencies/check")
    assert response.status_code == 200
    for item in response.json():
        assert isinstance(item["installed"], bool)
        if not item["installed"]:
            assert item["version"] is None and item["import_checked"] is False


def test_local_settings_can_be_applied_without_restarting_motor_runtime(
    pipeline_client: TestClient,
) -> None:
    client = pipeline_client
    assert client.put("/api/admin/pipeline/config/vision", json={"max_fps": 4}).status_code == 200
    assert "vision" in client.get("/api/admin/pipeline").json()["pending_local"]
    assert client.post("/api/admin/pipeline/local/apply").status_code == 200
    status = client.get("/api/admin/pipeline").json()
    assert status["active_config"]["vision"]["source"] == "opencv"
    assert "vision" not in status["pending_local"]
    assert status["local"]["vision"]["state"] == "disabled"
    assert client.get("/api/health").status_code == 200


def test_camera_check_requires_a_configured_source(pipeline_client: TestClient) -> None:
    assert (
        pipeline_client.put(
            "/api/admin/pipeline/config/vision", json={"source": "none"}
        ).status_code
        == 200
    )
    assert pipeline_client.post("/api/admin/pipeline/camera/check").status_code == 422


def test_stale_connection_check_is_not_attached_to_new_settings(account_store: AuthStore) -> None:
    settings = PipelineSettings(account_store)
    connection_id = settings.save_connection(
        None,
        ConnectionInput(name="One", provider="ollama", base_url="http://localhost:11434/v1"),
        "admin",
    )
    _, _, revision = settings.connection_snapshot(connection_id)
    settings.save_connection(
        connection_id,
        ConnectionInput(name="Two", provider="ollama", base_url="http://localhost:1234/v1"),
        "admin",
    )
    assert not settings.save_check(connection_id, {"ok": True}, revision)
    assert settings.connections()[0]["check"] is None


def test_local_worker_failure_does_not_claim_a_sample_or_crash_movement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    from mirae.config import VisionConfig
    from mirae.pipeline.workers import VisionWorker

    monkeypatch.setattr(
        "mirae.pipeline.workers.build_camera",
        Mock(side_effect=ImportError("camera dependency missing")),
    )
    worker = VisionWorker(VisionConfig(enabled=True, source="opencv"))
    worker.start()
    try:
        deadline = time.monotonic() + 1
        while worker.snapshot()["state"] != "error" and time.monotonic() < deadline:
            time.sleep(0.01)
        status = worker.snapshot()
        assert status["state"] == "error"
        assert status["last_sample_at"] is None and status["samples"] == 0
        assert "dependency missing" in status["error"]
    finally:
        worker.close()


def test_live_vision_reports_no_frame_while_camera_is_stopped(
    pipeline_client: TestClient,
) -> None:
    response = pipeline_client.get("/api/admin/pipeline/live/vision")
    assert response.status_code == 200
    assert response.json()["state"] == "disabled"
    assert response.json()["frame"] is None


def test_live_speech_returns_transcripts_after_cursor(pipeline_client: TestClient) -> None:
    robot = pipeline_client.app.state.robot  # type: ignore[attr-defined]
    for index in (1, 2, 3):
        robot.speech._history.append(
            {"id": index, "at": 0.0, "text": f"chunk {index}", "processing_ms": 1.0, "peak": 0.1}
        )
    data = pipeline_client.get("/api/admin/pipeline/live/speech?after=1").json()
    assert [entry["text"] for entry in data["entries"]] == ["chunk 2", "chunk 3"]
    assert data["cursor"] == 3
    again = pipeline_client.get("/api/admin/pipeline/live/speech?after=3").json()
    assert again["entries"] == [] and again["cursor"] == 3


def test_live_frame_and_detections_come_from_the_same_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import base64
    import time

    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from mirae.config import VisionConfig
    from mirae.pipeline.workers import VisionWorker
    from mirae.vision.base import Detection

    camera = Mock()
    camera.read.return_value = np.zeros((48, 64, 3), dtype=np.uint8)
    monkeypatch.setattr("mirae.pipeline.workers.build_camera", Mock(return_value=camera))
    face = Detection("Ada", None, (0.1, 0.2, 0.3, 0.4), 0.4, kind="face")
    recognizer = Mock()
    recognizer.detect.return_value = [face]
    monkeypatch.setattr("mirae.pipeline.workers.FaceRecognizer", Mock(return_value=recognizer))
    worker = VisionWorker(
        VisionConfig(enabled=True, source="opencv", faces_enabled=True, max_fps=30)
    )
    worker.start()
    try:
        deadline = time.monotonic() + 2
        while worker.snapshot()["samples"] == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        snapshot, jpeg = worker.live()
        assert snapshot["state"] == "running" and jpeg is not None
        assert base64.b64encode(jpeg)
        assert snapshot["detections"] == [
            {
                "label": "Ada",
                "confidence": None,
                "box": (0.1, 0.2, 0.3, 0.4),
                "match_distance": 0.4,
                "kind": "face",
            }
        ]
    finally:
        worker.close()
