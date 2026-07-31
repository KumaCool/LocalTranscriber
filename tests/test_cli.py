from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from local_transcriber.cli import main
from local_transcriber.schema import read_result


def _fixture(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=0.1", str(path)],
        check=True,
    )


def test_transcribe_cli_writes_canonical_result_and_exports(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)

    received = {}

    class FakeEngine:
        def __init__(self, **kwargs):
            received.update(kwargs)
            self.info = kwargs

        def transcribe(self, path: Path):
            assert path.name == "normalized.wav"
            return [{"start_ms": 0, "end_ms": 90, "speaker": "SPEAKER_00", "text": "你好"}]

    monkeypatch.setattr("local_transcriber.cli.TranscriptionEngine", FakeEngine)
    output = tmp_path / "output"

    arguments = [
        "transcribe",
        str(source),
        "--output-dir",
        str(output),
        "--runtime-dir",
        str(tmp_path / "runtime"),
        "--language",
        "zh",
    ]
    assert main(arguments) == 0

    result_path = next(output.glob("*/result.json"))
    result = read_result(result_path)
    assert result.job.status == "succeeded"
    assert result.engine.language == "zh"
    assert received["language"] == "zh"
    assert result.segments[0].text == "你好"
    assert (result_path.parent / "transcript.md").is_file()
    assert (result_path.parent / "transcript.txt").is_file()
    assert (result_path.parent / "transcript.srt").is_file()


def test_transcribe_cli_records_input_error(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "transcribe",
            str(tmp_path / "missing.wav"),
            "--output-dir",
            str(tmp_path / "out"),
            "--runtime-dir",
            str(tmp_path / "runtime"),
        ]
    )

    assert code == 2
    assert "does not exist" in capsys.readouterr().err
    records = list((tmp_path / "runtime" / "jobs").glob("*.json"))
    assert json.loads(records[0].read_text())["status"] == "failed"


def test_transcribe_cli_records_model_error(tmp_path: Path, monkeypatch, capsys) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)

    class BrokenEngine:
        def __init__(self, **kwargs):
            pass

        def transcribe(self, path: Path):
            raise RuntimeError("model failed")

    monkeypatch.setattr("local_transcriber.cli.TranscriptionEngine", BrokenEngine)

    code = main(
        [
            "transcribe",
            str(source),
            "--output-dir",
            str(tmp_path / "out"),
            "--runtime-dir",
            str(tmp_path / "runtime"),
        ]
    )

    assert code == 3
    assert "model failed" in capsys.readouterr().err


def test_transcribe_rejects_nonpositive_speakers(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["transcribe", "input.wav", "--speakers", "0"])


def test_transcribe_rejects_unsupported_language() -> None:
    with pytest.raises(SystemExit):
        main(["transcribe", "input.wav", "--language", "fr"])


def test_transcribe_cli_reports_estimated_duration_before_engine_runs(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)

    class FakeEngine:
        def __init__(self, **kwargs):
            pass

        def transcribe(self, path: Path):
            return [{"start_ms": 0, "end_ms": 90, "speaker": "SPEAKER_00", "text": "你好"}]

    monkeypatch.setattr("local_transcriber.cli.TranscriptionEngine", FakeEngine)
    assert (
        main(
            [
                "transcribe",
                str(source),
                "--output-dir",
                str(tmp_path / "output"),
                "--runtime-dir",
                str(tmp_path / "runtime"),
            ]
        )
        == 0
    )

    assert "estimated completion:" in capsys.readouterr().err
