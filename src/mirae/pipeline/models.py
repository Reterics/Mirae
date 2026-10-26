"""Approved model downloads pinned to upstream revisions and content digests."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

import httpx

from mirae.api.accounts import AccountError
from mirae.pipeline.jobs import JobRunner

SSD_REV = "bb17b6c3eef36d80be441ae8e5339be66e8e3b7a"
VOC_LABELS = [
    "background",
    "aeroplane",
    "bicycle",
    "bird",
    "boat",
    "bottle",
    "bus",
    "car",
    "cat",
    "chair",
    "cow",
    "diningtable",
    "dog",
    "horse",
    "motorbike",
    "person",
    "pottedplant",
    "sheep",
    "sofa",
    "train",
    "tvmonitor",
]
CATALOG: dict[str, dict[str, Any]] = {
    "mobilenet-ssd": {
        "name": "MobileNet SSD · 20 object classes",
        "kind": "vision",
        "recommended": True,
        "source": "https://github.com/chuanqi305/MobileNet-SSD",
        "license": "MIT",
        "files": [
            ("deploy.prototxt", 44667, "88021a94bca5c22753a23664d388d4922b2186bb", "git"),
            (
                "mobilenet_iter_73000.caffemodel",
                23306119,
                "253e5012dd6a17666fd7ae16cfa14a6860280ff7",
                "git",
            ),
            ("LICENSE", 1067, "2e1b91c92dfedb16126e6d376ace80cda4e2204a", "git"),
        ],
        "base": f"https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/{SSD_REV}/",
    },
}
for _name, _revision, _size, _digest, _config_size, _config_hash in (
    (
        "tiny",
        "d90ca5fe260221311c53c58e660288d3deb8d356",
        75538270,
        "dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1",
        2249,
        "3baa18e2b321a2f489614607852a729fcd516480",
    ),
    (
        "base",
        "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        145217532,
        "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9",
        2309,
        "867cf1a0fece1394e01d55e287ba2f09a577c046",
    ),
    (
        "small",
        "536b0662742c02347bc0e980a01041f333bce120",
        483546902,
        "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
        2370,
        "e5047537059bd8f182d9ca64c470201585015187",
    ),
):
    CATALOG[f"whisper-{_name}"] = {
        "name": f"Whisper {_name} · multilingual",
        "kind": "speech",
        "recommended": _name == "base",
        "license": "MIT",
        "source": f"https://huggingface.co/Systran/faster-whisper-{_name}",
        "base": f"https://huggingface.co/Systran/faster-whisper-{_name}/resolve/{_revision}/",
        "files": [
            ("config.json", _config_size, _config_hash, "git"),
            ("model.bin", _size, _digest, "sha256"),
            ("tokenizer.json", 2203239, "7818adb6de9fa3064d3ff81226fdd675be1f6344", "git"),
            ("vocabulary.txt", 459861, "c9074644d9d1205686f16d411564729461324b75", "git"),
        ],
    }


class ModelLibrary:
    def __init__(self, root: Path, jobs: JobRunner) -> None:
        self.root = root.resolve()
        self.jobs = jobs

    def directory(self, model: str) -> Path:
        if model not in CATALOG:
            raise AccountError(404, "model not in the supported catalog")
        return self.root / model

    def listing(self) -> list[dict[str, Any]]:
        return [
            {
                "id": key,
                **{k: v for k, v in item.items() if k not in ("files", "base")},
                "bytes": sum(f[1] for f in item["files"]),
                "installed": self.installed(key),
            }
            for key, item in CATALOG.items()
        ]

    def installed(self, model: str) -> bool:
        directory = self.directory(model)
        return (directory / "installed.json").is_file() and all(
            (directory / filename).is_file() and (directory / filename).stat().st_size == size
            for filename, size, _, _ in CATALOG[model]["files"]
        )

    def download(self, job: str, model: str) -> dict[str, Any]:
        directory = self.directory(model)
        directory.mkdir(parents=True, exist_ok=True)
        info = CATALOG[model]
        total = sum(f[1] for f in info["files"])
        if shutil.disk_usage(directory).free < total + 50_000_000:
            raise RuntimeError("insufficient free space for the model")
        # A failed refresh may leave a mixture of old and new files. Only a
        # completely verified download may be activated, including after restart.
        (directory / "installed.json").unlink(missing_ok=True)
        completed = 0
        with httpx.Client(timeout=60, follow_redirects=True, trust_env=False) as client:
            for filename, size, expected, algorithm in info["files"]:
                self.jobs.check_cancelled()
                target = directory / filename
                partial = directory / (filename + ".partial")
                digest = hashlib.sha256() if algorithm == "sha256" else hashlib.sha1()
                if algorithm == "git":
                    digest.update(f"blob {size}\0".encode())
                downloaded = 0
                last_log = time.monotonic()
                self.jobs.log(job, f"Downloading {filename} ({size / 1e6:.1f} MB)")
                try:
                    with client.stream("GET", info["base"] + filename) as response:
                        if response.status_code != 200:
                            raise RuntimeError(f"model host returned HTTP {response.status_code}")
                        with partial.open("wb") as output:
                            for chunk in response.iter_bytes(256 * 1024):
                                self.jobs.check_cancelled()
                                downloaded += len(chunk)
                                if downloaded > size:
                                    raise RuntimeError("download exceeds the approved model size")
                                output.write(chunk)
                                digest.update(chunk)
                                if time.monotonic() - last_log > 0.5:
                                    self.jobs.log(
                                        job,
                                        f"{filename}: {downloaded / 1e6:.1f} / {size / 1e6:.1f} MB",
                                        (completed + downloaded) / total,
                                    )
                                    last_log = time.monotonic()
                    if downloaded != size or digest.hexdigest() != expected:
                        raise RuntimeError(f"content verification failed for {filename}")
                    partial.replace(target)
                except httpx.HTTPError as exc:
                    raise RuntimeError(
                        "model download failed; check the service network connection"
                    ) from exc
                finally:
                    partial.unlink(missing_ok=True)
                completed += size
                self.jobs.log(job, f"Verified {filename}", completed / total)
        if model == "mobilenet-ssd":
            (directory / "labels.txt").write_text("\n".join(VOC_LABELS), encoding="utf-8")
        (directory / "installed.json").write_text(
            json.dumps({"model": model, "at": time.time()}), encoding="utf-8"
        )
        return {"model": model, "path": str(directory)}

    def settings(self, model: str) -> tuple[str, dict[str, Any]]:
        if not self.installed(model):
            raise AccountError(422, "download this model before activating it")
        directory = self.directory(model)
        if CATALOG[model]["kind"] == "vision":
            return "vision", {
                "detector": "opencv_dnn",
                "model_path": str(directory / "mobilenet_iter_73000.caffemodel"),
                "model_config_path": str(directory / "deploy.prototxt"),
                "labels_path": str(directory / "labels.txt"),
                "input_width": 300,
                "input_height": 300,
                "input_scale": 1 / 127.5,
                "input_mean": (127.5, 127.5, 127.5),
                "swap_rb": False,
            }
        return "speech", {"stt": "faster_whisper", "stt_model": str(directory)}
