"""Persistent background operations with bounded, incremental console output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from mirae.api.accounts import AccountError, AuthStore
from mirae.pipeline.installation import (
    check_package_index,
    face_build_environment,
    installer_environment,
)

PACKAGES = {
    "opencv": ("opencv-python-headless==4.13.0.92", "cv2-enumerate-cameras==1.4.0"),
    "audio": ("sounddevice==0.5.6", "numpy>=1.26"),
    "whisper": ("faster-whisper==1.2.1", "sounddevice==0.5.6"),
    "piper": ("piper-tts==1.8.0", "sounddevice==0.5.6"),
    "faces": ("dlib==20.0.1", "face-recognition==1.3.0", "setuptools==80.9.0"),
    "gpio": ("gpiozero==2.0.1", "lgpio==0.2.2.0"),
    "tof": ("vl53l1x==0.0.5",),
}


class JobRunner:
    def __init__(self, store: AuthStore) -> None:
        self.store = store
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._active: str | None = None
        with store.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS pipeline_jobs "
                "(id TEXT PRIMARY KEY, kind TEXT, target TEXT, state TEXT, "
                "created REAL, updated REAL, progress REAL, result TEXT, error TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS pipeline_job_logs "
                "(job TEXT, seq INTEGER, line TEXT, PRIMARY KEY(job,seq))"
            )
            db.execute(
                "UPDATE pipeline_jobs SET state='failed',"
                "error='Service restarted during operation' "
                "WHERE state IN ('queued','running')"
            )

    def history(self) -> list[dict[str, Any]]:
        with self.store.connection() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM pipeline_jobs ORDER BY created DESC LIMIT 20")
            ]

    def snapshot(self, job: str, after: int = 0) -> dict[str, Any]:
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM pipeline_jobs WHERE id=?", (job,)).fetchone()
            if row is None:
                raise AccountError(404, "operation not found")
            logs = [
                dict(r)
                for r in db.execute(
                    "SELECT seq,line FROM pipeline_job_logs WHERE job=? AND seq>? "
                    "ORDER BY seq LIMIT 500",
                    (job, after),
                )
            ]
        return {**dict(row), "logs": logs, "cursor": logs[-1]["seq"] if logs else after}

    def log(self, job: str, line: str, progress: float | None = None) -> None:
        with self.store.connection() as db:
            seq = db.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM pipeline_job_logs WHERE job=?", (job,)
            ).fetchone()[0]
            db.execute("INSERT INTO pipeline_job_logs VALUES (?,?,?)", (job, seq, line[-4096:]))
            db.execute("DELETE FROM pipeline_job_logs WHERE job=? AND seq<?", (job, seq - 2000))
            db.execute(
                "UPDATE pipeline_jobs SET updated=?,progress=COALESCE(?,progress) WHERE id=?",
                (time.time(), progress, job),
            )

    def start(self, kind: str, target: str, actor: str, task: Callable[[str], Any]) -> str:
        with self._lock:
            if self._active:
                raise AccountError(409, "another installation or download is running")
            job = uuid.uuid4().hex
            self._active = job
            self._cancel.clear()
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO pipeline_jobs VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        job,
                        kind,
                        target,
                        "queued",
                        time.time(),
                        time.time(),
                        None,
                        None,
                        None,
                    ),
                )
                self.store.audit(db, actor, f"pipeline.{kind}.started", target)
            threading.Thread(
                target=self._run, args=(job, task), name="pipeline-operation", daemon=True
            ).start()
            return job

    def _run(self, job: str, task: Callable[[str], Any]) -> None:
        state, result, error = "succeeded", None, None
        try:
            with self.store.connection() as db:
                db.execute("UPDATE pipeline_jobs SET state='running' WHERE id=?", (job,))
            result = task(job)
            self.check_cancelled()
            self.log(job, "Operation completed.", 1.0)
        except Exception as exc:
            state = "cancelled" if self._cancel.is_set() else "failed"
            error = str(exc)
            self.log(job, f"{state.capitalize()}: {error}")
        finally:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE pipeline_jobs SET state=?,updated=?,result=?,error=? WHERE id=?",
                    (state, time.time(), json.dumps(result), error, job),
                )
            with self._lock:
                self._active = None

    def cancel(self, job: str) -> None:
        with self._lock:
            if self._active != job:
                raise AccountError(409, "operation is not running")
            self._cancel.set()

    def check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise RuntimeError("cancelled by administrator")

    def command(self, job: str, args: list[str], overrides: dict[str, str] | None = None) -> None:
        self.log(job, "Starting " + " ".join(args[1:]))
        env = installer_environment(os.environ, overrides)
        with subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if sys.platform == "win32"
            else 0,
        ) as process:
            finished = threading.Event()

            def supervise() -> None:
                deadline = time.monotonic() + 1200
                while not finished.wait(0.2):
                    if self._cancel.is_set() or time.monotonic() > deadline:
                        process.kill()
                        return

            guard = threading.Thread(target=supervise, daemon=True)
            guard.start()
            try:
                assert process.stdout is not None
                for line in process.stdout:
                    self.log(job, line.rstrip())
                code = process.wait()
                self.check_cancelled()
                if code:
                    raise RuntimeError(f"installer exited with code {code}; see console above")
            finally:
                finished.set()
                guard.join(timeout=1)

    def install(self, job: str, dependency: str) -> dict[str, Any]:
        import importlib
        import importlib.util

        packages = PACKAGES[dependency]
        if sys.prefix == sys.base_prefix:
            raise RuntimeError("Run Mirae in its virtual environment before installing packages.")
        self.log(job, "Checking HTTPS access to PyPI using the service network settings.")
        check_package_index()
        self.log(job, "PyPI is reachable.")
        overrides = None
        if dependency == "faces" and importlib.util.find_spec("dlib") is None:
            overrides = face_build_environment()
            self.log(job, "C++ compiler and CMake detected; preparing the native dlib build.")
        if importlib.util.find_spec("pip") is None:
            self.log(job, "Preparing pip in the service virtual environment.")
            self.command(job, [sys.executable, "-m", "ensurepip", "--upgrade"])
        self.command(
            job,
            [
                sys.executable,
                "-m",
                "pip",
                "--isolated",
                "install",
                "--no-input",
                "--disable-pip-version-check",
                "--progress-bar",
                "off",
                "--retries",
                "1",
                "--timeout",
                "15",
                "--verbose",
                "--index-url",
                "https://pypi.org/simple",
                *packages,
            ],
            overrides,
        )
        modules = {
            "opencv": "cv2, cv2_enumerate_cameras",
            "audio": "numpy, sounddevice",
            "whisper": "faster_whisper, sounddevice",
            "piper": "piper, sounddevice",
            "faces": "dlib, face_recognition",
            "gpio": "gpiozero",
            "tof": "VL53L1X",
        }
        self.log(job, "Verifying imports in a fresh Python process.")
        self.command(job, [sys.executable, "-c", "import " + modules[dependency]], overrides)
        importlib.invalidate_caches()
        self.log(job, "Installed into the Python environment used by this service.")
        return {"packages": list(packages)}
