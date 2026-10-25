"""Optional local detectors. No model download or synthetic recognition output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mirae.config import VisionConfig
from mirae.vision.base import Detection


class OpenCVDetector:
    def __init__(self, cfg: VisionConfig) -> None:
        import cv2

        if not cfg.model_path:
            raise ValueError("OpenCV DNN requires a model file")
        self._model = cv2.dnn.DetectionModel(cfg.model_path, cfg.model_config_path or "")
        self._model.setInputParams(
            size=(cfg.input_width, cfg.input_height),
            scale=cfg.input_scale,
            mean=cfg.input_mean,
            swapRB=cfg.swap_rb,
        )
        self._threshold = cfg.confidence_threshold
        self._labels = (
            Path(cfg.labels_path).read_text(encoding="utf-8").splitlines()
            if cfg.labels_path
            else []
        )

    def detect(self, frame: Any) -> list[Detection]:
        classes, scores, boxes = self._model.detect(
            frame, confThreshold=self._threshold, nmsThreshold=0.4
        )
        height, width = frame.shape[:2]
        detections = []
        for class_id, score, box in zip(classes, scores, boxes, strict=True):
            index = int(class_id)
            label = self._labels[index] if 0 <= index < len(self._labels) else f"class:{index}"
            x, y, w, h = (int(value) for value in box)
            detections.append(
                Detection(label, float(score), (x / width, y / height, w / width, h / height))
            )
        return detections


class FaceRecognizer:
    def __init__(self, cfg: VisionConfig) -> None:
        import face_recognition
        import numpy as np

        self._engine = face_recognition
        self._tolerance = cfg.face_tolerance
        self._encodings: Any = np.empty((0, 128))
        self._names: list[str] = []
        if cfg.known_faces_path:
            with np.load(cfg.known_faces_path, allow_pickle=False) as archive:
                encodings = archive["encodings"]
                names = archive["names"]
                if encodings.ndim != 2 or encodings.shape[1] != 128 or len(names) != len(encodings):
                    raise ValueError("known faces require an Nx128 encodings array and N names")
                if names.dtype.kind not in ("U", "S") or not np.isfinite(encodings).all():
                    raise ValueError("known faces contain invalid names or encodings")
                self._encodings = encodings.copy()
                self._names = [str(name) for name in names]

    def detect(self, frame: Any) -> list[Detection]:
        rgb = frame[:, :, ::-1].copy()
        locations = self._engine.face_locations(rgb, model="hog")
        encodings = self._engine.face_encodings(rgb, locations)
        height, width = frame.shape[:2]
        result = []
        for (top, right, bottom, left), encoding in zip(locations, encodings, strict=True):
            label, distance = "unidentified face", None
            if self._names:
                distances = self._engine.face_distance(self._encodings, encoding)
                index = int(distances.argmin())
                distance = float(distances[index])
                if distance <= self._tolerance:
                    label = self._names[index]
            # face_recognition supplies a distance, not a calibrated confidence.
            result.append(
                Detection(
                    label,
                    None,
                    (left / width, top / height, (right - left) / width, (bottom - top) / height),
                    distance,
                    kind="face",
                )
            )
        return result
