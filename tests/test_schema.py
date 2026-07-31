from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_transcriber.schema import (
    CanonicalResult,
    EngineInfo,
    JobInfo,
    Segment,
    SourceInfo,
    read_result,
    write_result,
)


def valid_result() -> CanonicalResult:
    return CanonicalResult(
        schema_version=1,
        source=SourceInfo(path="meeting.wav", size_bytes=42, sha256="a" * 64, duration_ms=1200),
        engine=EngineInfo(
            funasr_version="1.3.30",
            asr_model="iic/SenseVoiceSmall",
            vad_model="fsmn-vad",
            speaker_model="cam++",
            device="cpu",
            threads=2,
            speakers=None,
            language="auto",
        ),
        job=JobInfo(id="job-1", status="succeeded", created_at="2026-07-31T00:00:00+00:00"),
        segments=(Segment(start_ms=10, end_ms=500, speaker="SPEAKER_00", text="你好"),),
    )


def test_result_json_round_trips_equivalently(tmp_path: Path) -> None:
    result = valid_result()
    destination = tmp_path / "result.json"

    write_result(destination, result)

    assert read_result(destination) == result
    assert json.loads(destination.read_text(encoding="utf-8"))["schema_version"] == 1


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"start_ms": -1}, "non-negative"),
        ({"start_ms": 5, "end_ms": 5}, "later"),
        ({"speaker": "Alice"}, "anonymous"),
        ({"text": "  "}, "non-empty"),
    ],
)
def test_segment_rejects_invalid_values(changes, message) -> None:
    values = {"start_ms": 0, "end_ms": 10, "speaker": "SPEAKER_00", "text": "ok"}
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        Segment(**values)


def test_read_result_rejects_unknown_schema_version(tmp_path: Path) -> None:
    payload = valid_result().to_dict()
    payload["schema_version"] = 99
    path = tmp_path / "result.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        read_result(path)


def test_engine_info_rejects_unsupported_language() -> None:
    with pytest.raises(ValueError, match="language"):
        EngineInfo(
            funasr_version="1.3.30",
            asr_model="asr",
            vad_model="vad",
            speaker_model="speaker",
            device="cpu",
            threads=2,
            speakers=None,
            language="fr",
        )
