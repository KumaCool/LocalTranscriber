from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 1
_SPEAKER_PATTERN = re.compile(r"^SPEAKER_\d{2,}$")
_JOB_STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
SUPPORTED_LANGUAGES = {"auto", "zh", "en", "yue", "ja", "ko"}


@dataclass(frozen=True)
class SourceInfo:
    path: str
    size_bytes: int
    sha256: str
    duration_ms: int

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("source path must be non-empty")
        if self.size_bytes < 0 or self.duration_ms < 0:
            raise ValueError("source sizes and duration must be non-negative")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("source sha256 must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True)
class EngineInfo:
    funasr_version: str
    asr_model: str
    vad_model: str
    speaker_model: str
    device: str
    threads: int
    speakers: int | None
    language: str = "auto"

    def __post_init__(self) -> None:
        if self.threads < 1:
            raise ValueError("engine threads must be positive")
        if self.speakers is not None and self.speakers < 1:
            raise ValueError("speaker constraint must be positive")
        if self.language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {self.language}")


@dataclass(frozen=True)
class JobInfo:
    id: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _JOB_STATUSES:
            raise ValueError(f"unsupported job status: {self.status}")


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    speaker: str
    text: str

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("segment start must be non-negative")
        if self.end_ms <= self.start_ms:
            raise ValueError("segment end must be later than start")
        if not _SPEAKER_PATTERN.fullmatch(self.speaker):
            raise ValueError("speaker must be an anonymous SPEAKER_NN label")
        if not self.text.strip():
            raise ValueError("segment text must be non-empty")


@dataclass(frozen=True)
class CanonicalResult:
    schema_version: int
    source: SourceInfo
    engine: EngineInfo
    job: JobInfo
    segments: tuple[Segment, ...]

    def __post_init__(self) -> None:
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        previous_end = -1
        for segment in self.segments:
            if segment.start_ms < previous_end:
                raise ValueError("segments must be ordered and non-overlapping")
            previous_end = segment.end_ms

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def result_from_dict(payload: dict[str, Any]) -> CanonicalResult:
    try:
        version = payload["schema_version"]
        if version != _SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {version}")
        return CanonicalResult(
            schema_version=version,
            source=SourceInfo(**payload["source"]),
            engine=EngineInfo(**payload["engine"]),
            job=JobInfo(**payload["job"]),
            segments=tuple(Segment(**item) for item in payload["segments"]),
        )
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc.args[0]}") from exc
    except TypeError as exc:
        raise ValueError(f"invalid canonical result: {exc}") from exc


def write_result(destination: Path, result: CanonicalResult) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_result(source: Path) -> CanonicalResult:
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read canonical result: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("canonical result must be a JSON object")
    return result_from_dict(payload)
