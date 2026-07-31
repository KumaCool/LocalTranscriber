from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MediaError(ValueError):
    pass


def estimate_transcription_seconds(duration_ms: int) -> tuple[int, int]:
    duration_seconds = max(duration_ms, 0) / 1000
    return round(35 + duration_seconds * 0.11), round(65 + duration_seconds * 0.15)


@dataclass(frozen=True)
class MediaInfo:
    duration_ms: int
    audio_stream_index: int
    codec_name: str
    sample_rate: int
    channels: int
    format_name: str

    def to_dict(self) -> dict[str, int | str]:
        return {
            "duration_ms": self.duration_ms,
            "audio_stream_index": self.audio_stream_index,
            "codec_name": self.codec_name,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "format_name": self.format_name,
        }


def _run(arguments: list[str], tool: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(arguments, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise MediaError(f"{tool} executable was not found") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "unknown error").strip().splitlines()[-1]
        raise MediaError(f"{tool} failed: {detail}") from exc


def probe_media(source: Path) -> MediaInfo:
    if not source.is_file():
        raise MediaError(f"input media does not exist: {source}")
    completed = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(source),
        ],
        "ffprobe",
    )
    try:
        payload: dict[str, Any] = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        stream = next(item for item in streams if item.get("codec_type") == "audio")
        duration = stream.get("duration") or payload.get("format", {}).get("duration")
        if duration is None:
            raise MediaError("ffprobe response has no duration")
        return MediaInfo(
            duration_ms=round(float(duration) * 1000),
            audio_stream_index=int(stream["index"]),
            codec_name=str(stream["codec_name"]),
            sample_rate=int(stream["sample_rate"]),
            channels=int(stream["channels"]),
            format_name=str(payload.get("format", {}).get("format_name", "unknown")),
        )
    except StopIteration as exc:
        raise MediaError("media has no audio stream") from exc
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, MediaError):
            raise
        raise MediaError(f"invalid ffprobe response: {exc}") from exc


def normalize_audio(source: Path, destination: Path, audio_stream_index: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            f"0:{audio_stream_index}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ],
        "ffmpeg",
    )
