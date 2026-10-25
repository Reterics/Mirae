import hashlib
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from mirae.api.accounts import AccountError, AuthStore
from mirae.api.app import create_app
from mirae.config import load_config
from mirae.pipeline.jobs import JobRunner
from mirae.pipeline.models import CATALOG, ModelLibrary
from mirae.robot import Robot


def wait_job(runner: JobRunner, job: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        snapshot = runner.snapshot(job)
        if snapshot["state"] not in ("queued", "running"):
            return snapshot
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_job_console_is_incremental_and_survives_reopening(account_store: AuthStore) -> None:
    runner = JobRunner(account_store)
    gate = threading.Event()

    def operation(job: str) -> dict[str, bool]:
        runner.log(job, "first", 0.25)
        gate.wait(2)
        runner.log(job, "second", 0.75)
        return {"verified": True}

    job = runner.start("install", "test-package", "admin", operation)
    try:
        deadline = time.monotonic() + 1
        while not runner.snapshot(job)["logs"] and time.monotonic() < deadline:
            time.sleep(0.01)
        first = runner.snapshot(job)
        assert first["state"] == "running" and first["progress"] == 0.25
        assert first["logs"][0]["line"] == "first"
        with pytest.raises(AccountError, match="another installation"):
            runner.start("download", "other", "admin", operation)
    finally:
        gate.set()
    completed = wait_job(runner, job)
    assert completed["state"] == "succeeded"
    assert completed["progress"] == 1
    assert [line["line"] for line in runner.snapshot(job, first["cursor"])["logs"]] == [
        "second",
        "Operation completed.",
    ]
    assert JobRunner(account_store).snapshot(job)["state"] == "succeeded"


def test_cancelled_and_failed_jobs_never_claim_success(account_store: AuthStore) -> None:
    runner = JobRunner(account_store)
    gate = threading.Event()

    def operation(job: str) -> None:
        gate.wait(2)
        runner.check_cancelled()

    job = runner.start("download", "test", "admin", operation)
    runner.cancel(job)
    gate.set()
    assert wait_job(runner, job)["state"] == "cancelled"


@pytest.mark.parametrize("valid", [True, False])
def test_model_download_verifies_content_before_activation(
    account_store: AuthStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, valid: bool
) -> None:
    body = b"test-model-content"
    checksum = hashlib.sha256(body).hexdigest()
    monkeypatch.setitem(
        CATALOG,
        "test-model",
        {
            "name": "Fixture",
            "kind": "speech",
            "files": [("model.bin", len(body), checksum, "sha256")],
            "base": "https://fixture.invalid/",
        },
    )
    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=body if valid else b"wrong")
            ),
            **kwargs,
        ),
    )
    runner = JobRunner(account_store)
    library = ModelLibrary(tmp_path / "models", runner)
    job = runner.start(
        "download", "test-model", "admin", lambda job: library.download(job, "test-model")
    )
    status = wait_job(runner, job)
    assert library.installed("test-model") is valid
    assert status["state"] == ("succeeded" if valid else "failed")
    assert not (library.directory("test-model") / "model.bin.partial").exists()
    if valid:
        assert library.settings("test-model")[1]["stt"] == "faster_whisper"
    else:
        with pytest.raises(AccountError, match="download this model"):
            library.settings("test-model")


def test_install_and_download_routes_are_allowlisted_and_protected(test_token: str) -> None:
    with TestClient(create_app(Robot(load_config()))) as client:
        assert client.post("/api/admin/pipeline/dependencies/opencv/install").status_code == 401
        client.headers["Authorization"] = f"Bearer {test_token}"
        assert (
            client.post("/api/admin/pipeline/dependencies/arbitrary-package/install").status_code
            == 422
        )
        assert client.post("/api/admin/pipeline/models/arbitrary/download").status_code == 404
        assert client.post("/api/admin/pipeline/models/whisper-base/activate").status_code == 422
        assert client.get("/api/admin/pipeline/camera/frame").status_code == 404
        assert client.get("/api/admin/pipeline/jobs/missing").status_code == 404
        data = client.get("/api/admin/pipeline").json()
        assert all(not model["installed"] for model in data["models"])
        assert data["jobs"] == []


def test_camera_check_reuses_the_running_worker_without_opening_another_device(
    monkeypatch: pytest.MonkeyPatch, test_token: str
) -> None:
    robot = Robot(load_config())
    monkeypatch.setattr(type(robot.vision), "alive", property(lambda self: True))
    monkeypatch.setattr(robot.vision, "frame", lambda: b"actual-worker-frame")
    monkeypatch.setattr(robot.vision, "close", lambda: None)
    robot.vision.update(
        state="running", last_sample_at=time.time(), frame_width=640, frame_height=480
    )
    from unittest.mock import Mock

    build = Mock(side_effect=AssertionError("second camera opened"))
    monkeypatch.setattr("mirae.pipeline.manager.build_camera", build)
    with TestClient(create_app(robot), headers={"Authorization": f"Bearer {test_token}"}) as client:
        assert client.post("/api/admin/pipeline/camera/check").status_code == 200
        assert client.get("/api/admin/pipeline/camera/frame").content == b"actual-worker-frame"
    build.assert_not_called()
