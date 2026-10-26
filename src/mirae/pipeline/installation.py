"""Installer network diagnostics and local native-build prerequisites."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import httpx


def installer_environment(
    source: Mapping[str, str], overrides: Mapping[str, str] | None = None
) -> dict[str, str]:
    # Respect deployment proxy/certificate settings. Pip config cannot change the
    # allowlisted index or install target, including through a nested build's pip.
    env = {k: v for k, v in source.items() if not k.upper().startswith(("PIP_", "UV_"))}
    env.update(
        PIP_CONFIG_FILE=os.devnull,
        PYTHONUNBUFFERED="1",
        PYTHONUTF8="1",
    )
    if overrides:
        env.update(overrides)
    return env


def check_package_index() -> None:
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=True) as client:
            response = client.head("https://pypi.org/simple/")
            response.raise_for_status()
    except httpx.ProxyError as exc:
        raise RuntimeError(
            "Cannot reach the configured HTTP/HTTPS proxy. Check the service's proxy "
            "settings or restart it with working network access. Package availability "
            "has not been checked."
        ) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            "PyPI connection timed out; check the service network connection."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"PyPI access returned HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(
            "Cannot establish a verified HTTPS connection to PyPI. Check network, DNS "
            "and certificate settings; package availability has not been checked."
        ) from exc


def windows_cpp_tools() -> Path | None:
    locator = Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / (
        "Microsoft Visual Studio/Installer/vswhere.exe"
    )
    if not locator.is_file():
        return None
    result = subprocess.run(
        [
            str(locator),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
    )
    root = result.stdout.strip()
    return Path(root) if result.returncode == 0 and root and Path(root).is_dir() else None


def face_build_environment() -> dict[str, str]:
    path = os.environ.get("PATH", "")
    cmake = shutil.which("cmake")
    if sys.platform == "win32":
        visual_studio = windows_cpp_tools()
        if not visual_studio:
            raise RuntimeError(
                "dlib requires Microsoft C++ build tools. Install Visual Studio's "
                "Desktop development with C++ workload, Windows SDK and CMake tools, then retry."
            )
        bundled = visual_studio / "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
        if not cmake and bundled.is_file():
            cmake = str(bundled)
            path = str(bundled.parent) + os.pathsep + path
    elif not (shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")):
        raise RuntimeError(
            "dlib requires a C++ compiler. On macOS run xcode-select --install; "
            "on Debian/Ubuntu install build-essential."
        )
    if not cmake:
        raise RuntimeError(
            "dlib requires CMake. On macOS run brew install cmake; on Debian/Ubuntu "
            "install cmake; on Windows install Visual Studio's CMake tools, then retry."
        )
    return {
        "PATH": path,
        "CMAKE_BUILD_PARALLEL_LEVEL": "2",
        "DLIB_USE_CUDA": "OFF",
        "DLIB_NO_GUI_SUPPORT": "ON",
    }
