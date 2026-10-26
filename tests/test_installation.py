import os
import sys
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from mirae.api.accounts import AuthStore
from mirae.pipeline import installation
from mirae.pipeline.jobs import JobRunner


def test_installer_ignores_pip_overrides_but_preserves_deployment_network_settings() -> None:
    result = installation.installer_environment(
        {
            "PATH": "service-path",
            "HTTP_PROXY": "http://proxy.invalid:8080",
            "HTTPS_PROXY": "http://proxy.invalid:8080",
            "NO_PROXY": "localhost",
            "SSL_CERT_FILE": "company.pem",
            "PIP_NO_INDEX": "1",
            "pip_target": "wrong",
            "UV_INDEX_URL": "https://wrong.invalid",
            "PIP_CONFIG_FILE": "wrong.ini",
        }
    )
    assert result["HTTP_PROXY"] == "http://proxy.invalid:8080"
    assert result["HTTPS_PROXY"] == "http://proxy.invalid:8080"
    assert result["NO_PROXY"] == "localhost"
    assert result["SSL_CERT_FILE"] == "company.pem"
    assert result["PIP_CONFIG_FILE"] == os.devnull
    assert result["PYTHONUTF8"] == "1"
    assert "PIP_NO_INDEX" not in result and "pip_target" not in result
    assert "UV_INDEX_URL" not in result


@pytest.mark.parametrize(
    "error,message",
    [
        (httpx.ProxyError("refused"), "configured HTTP/HTTPS proxy"),
        (httpx.ConnectError("certificate failed"), "verified HTTPS"),
        (httpx.ConnectTimeout("timed out"), "timed out"),
    ],
)
def test_network_failure_is_reported_as_network_failure(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    original = httpx.Client

    def fail(request: httpx.Request) -> httpx.Response:
        raise error

    monkeypatch.setattr(
        "mirae.pipeline.installation.httpx.Client",
        lambda **kw: original(
            transport=httpx.MockTransport(fail),
            **kw,
        ),
    )
    with pytest.raises(RuntimeError, match=message):
        installation.check_package_index()


def test_index_probe_does_not_download_the_entire_package_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = httpx.Client
    requests: list[httpx.Request] = []

    def serve(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    monkeypatch.setattr(
        "mirae.pipeline.installation.httpx.Client",
        lambda **kw: original(
            transport=httpx.MockTransport(serve),
            **kw,
        ),
    )
    installation.check_package_index()
    assert len(requests) == 1 and requests[0].method == "HEAD"
    assert str(requests[0].url) == "https://pypi.org/simple/"


def test_network_failure_stops_before_invoking_pip(
    monkeypatch: pytest.MonkeyPatch,
    account_store: AuthStore,
) -> None:
    runner = JobRunner(account_store)
    command = Mock()
    monkeypatch.setattr(runner, "command", command)
    monkeypatch.setattr(runner, "log", Mock())
    monkeypatch.setattr(
        "mirae.pipeline.jobs.check_package_index",
        Mock(
            side_effect=RuntimeError("proxy unavailable"),
        ),
    )
    with pytest.raises(RuntimeError, match="proxy unavailable"):
        runner.install("test", "faces")
    command.assert_not_called()


def test_windows_build_detects_cmake_bundled_with_visual_studio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "Visual Studio"
    cmake = root / "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
    cmake.parent.mkdir(parents=True)
    cmake.touch()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(installation, "windows_cpp_tools", lambda: root)
    monkeypatch.setattr("mirae.pipeline.installation.shutil.which", lambda command: None)
    environment = installation.face_build_environment()
    assert environment["PATH"].split(os.pathsep)[0] == str(cmake.parent)
    assert environment["DLIB_USE_CUDA"] == "OFF"


def test_windows_without_cpp_tools_gets_an_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(installation, "windows_cpp_tools", lambda: None)
    monkeypatch.setattr("mirae.pipeline.installation.shutil.which", lambda command: None)
    with pytest.raises(RuntimeError, match=r"Desktop development with C\+\+"):
        installation.face_build_environment()
