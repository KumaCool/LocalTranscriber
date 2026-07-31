from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from local_transcriber.media import (
    MediaError,
    estimate_transcription_seconds,
    normalize_audio,
    probe_media,
)


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True)


def test_estimate_transcription_time_accounts_for_startup_and_audio_duration() -> None:
    low, high = estimate_transcription_seconds(1_619_264)

    assert 210 <= low <= 270
    assert 270 <= high <= 330


def test_probe_and_normalize_wav(tmp_path: Path) -> None:
    source = tmp_path / "input.wav"
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            str(source),
        ]
    )

    metadata = probe_media(source)
    output = tmp_path / "nested" / "normalized.wav"
    normalize_audio(source, output, metadata.audio_stream_index)
    normalized = probe_media(output)

    assert metadata.duration_ms >= 190
    assert metadata.audio_stream_index == 0
    assert normalized.sample_rate == 16000
    assert normalized.channels == 1
    assert normalized.codec_name == "pcm_s16le"


def test_paths_with_shell_metacharacters_are_safe(tmp_path: Path) -> None:
    source = tmp_path / "input;$(touch PWNED).wav"
    _run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=0.1", str(source)])

    metadata = probe_media(source)
    normalize_audio(source, tmp_path / "out;still-safe.wav", metadata.audio_stream_index)

    assert not (tmp_path / "PWNED").exists()


def test_probe_rejects_media_without_audio(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=16x16:duration=0.1",
            "-an",
            str(source),
        ]
    )

    with pytest.raises(MediaError, match="audio stream"):
        probe_media(source)


def test_probe_rejects_corrupt_media(tmp_path: Path) -> None:
    source = tmp_path / "broken.mp3"
    source.write_bytes(b"not media")

    with pytest.raises(MediaError, match="ffprobe"):
        probe_media(source)
