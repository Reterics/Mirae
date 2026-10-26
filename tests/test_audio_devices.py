"""Microphone selection is saved by identity, not by PortAudio list index."""

import sys
import types
from typing import Any

import pytest

from mirae.config import SpeechConfig
from mirae.pipeline import devices

HOSTS = [{"name": "MME"}, {"name": "Windows WASAPI"}]


def _device(name: str, host: int, inputs: int = 1) -> dict[str, Any]:
    return {
        "name": name,
        "hostapi": host,
        "max_input_channels": inputs,
        "default_samplerate": 44100.0,
    }


class FakeSoundDevice(types.ModuleType):
    """Just enough of sounddevice for device listing and selection."""

    PortAudioError = RuntimeError

    def __init__(self, listing: list[dict[str, Any]]) -> None:
        super().__init__("sounddevice")
        self.listing = listing
        self.opened: list[int | None] = []

    def _terminate(self) -> None:
        pass

    def _initialize(self) -> None:
        pass

    def query_hostapis(self) -> list[dict[str, str]]:
        return HOSTS

    def query_devices(self, device: int | None = None, kind: str | None = None) -> Any:
        if device is None and kind is None:
            return self.listing
        index = 0 if device is None else device
        return {**self.listing[index], "index": index}

    def check_input_settings(self, **_: Any) -> None:
        pass

    def RawInputStream(self, *, device: int | None, **_: Any) -> "FakeStream":
        self.opened.append(device)
        return FakeStream()


class FakeStream:
    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, *_: object) -> None:
        pass


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSoundDevice:
    fake = FakeSoundDevice(
        [
            _device("Speakers", 0, inputs=0),
            _device("Headset mic", 0),
            _device("Webcam mic", 0),
            _device("Webcam mic", 1),
        ]
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    return fake


def test_listing_gives_each_microphone_a_stable_id(sd: FakeSoundDevice) -> None:
    ids = [item["id"] for item in devices.audio_devices()["items"]]
    assert sorted(ids) == ["MME:Headset mic", "MME:Webcam mic", "Windows WASAPI:Webcam mic"]


def test_saved_microphone_follows_its_name_when_the_list_shifts(sd: FakeSoundDevice) -> None:
    sd.listing.insert(1, _device("Bluetooth mic", 0))  # everything after it moves down one
    assert devices._resolve_input("MME:Webcam mic") == 3
    assert devices._resolve_input("Windows WASAPI:Webcam mic") == 4
    assert devices._resolve_input(None) is None


def test_missing_microphone_fails_instead_of_using_another(sd: FakeSoundDevice) -> None:
    with pytest.raises(RuntimeError, match="no longer connected"):
        devices._resolve_input("MME:Unplugged mic")
    # An output-only device with a matching name is not a microphone.
    with pytest.raises(RuntimeError, match="no longer connected"):
        devices._resolve_input("MME:Speakers")


def test_open_input_opens_the_resolved_index(sd: FakeSoundDevice) -> None:
    sd.listing.insert(1, _device("Bluetooth mic", 0))
    with devices.open_input("MME:Headset mic") as (_stream, info, rate):
        assert info["name"] == "Headset mic"
        assert rate == 16000
    assert sd.opened == [2]
    assert devices._open_inputs == 0


def test_old_index_setting_resets_to_system_default() -> None:
    assert SpeechConfig.model_validate({"input_device": 3}).input_device is None
    assert SpeechConfig.model_validate({"input_device": "MME:Mic"}).input_device == "MME:Mic"


def test_missing_default_microphone_preserves_available_devices(
    sd: FakeSoundDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    sd.listing[0]["max_output_channels"] = 2
    original = sd.query_devices

    def query(device: int | None = None, kind: str | None = None) -> Any:
        if kind == "input":
            raise sd.PortAudioError("No default input device")
        return original(device, kind)

    monkeypatch.setattr(sd, "query_devices", query)
    result = devices.audio_devices()
    assert result["error"] is None
    assert result["default"] is None
    assert len(result["items"]) == 3
    assert result["outputs"][0]["name"] == "Speakers"
    assert not any(item["default"] for item in result["items"])
