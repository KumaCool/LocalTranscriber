from __future__ import annotations

import json
import subprocess
from pathlib import Path

from local_transcriber.executor import ExecutorOptions, execute_job
from local_transcriber.jobs import JobStore
from local_transcriber.schema import read_result


def _fixture(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.1",
            str(path),
        ],
        check=True,
    )


def test_executor_runs_one_persisted_job_and_writes_all_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)
    runtime = tmp_path / "runtime"
    output = tmp_path / "output"
    store = JobStore(runtime)
    store.create("job-1", str(source), output)

    class FakeEngine:
        def __init__(self, **kwargs):
            self.info = kwargs

        def transcribe(self, path: Path, progress_callback=None):
            assert path == runtime / "job-1" / "normalized.wav"
            assert progress_callback is not None
            progress_callback(1, 2)
            return [{"start_ms": 0, "end_ms": 90, "speaker": "SPEAKER_00", "text": "你好"}]

    monkeypatch.setattr("local_transcriber.executor.TranscriptionEngine", FakeEngine)

    outcome = execute_job(
        "job-1",
        runtime,
        ExecutorOptions(cache_dir=tmp_path / "cache", threads=2, language="zh"),
    )

    assert outcome.status == "succeeded"
    result = read_result(output / "result.json")
    assert result.job.status == "succeeded"
    assert result.engine.language == "zh"
    assert result.segments[0].text == "你好"
    assert {path.name for path in output.iterdir()} == {
        "media.json",
        "result.json",
        "transcript.md",
        "transcript.txt",
        "transcript.srt",
    }
    payload = json.loads((runtime / "jobs" / "job-1.json").read_text())
    assert payload["artifact_paths"]["result"] == str(output / "result.json")
    assert payload["processed_units"] == 1
    assert payload["total_units"] == 2
    assert not (runtime / "job-1").exists()


def test_executor_failure_is_persisted_without_raising_to_scheduler(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)
    runtime = tmp_path / "runtime"
    store = JobStore(runtime)
    store.create("job-1", str(source), tmp_path / "output")

    class BrokenEngine:
        def __init__(self, **kwargs):
            pass

        def transcribe(self, path: Path, progress_callback=None):
            raise RuntimeError("model failed")

    monkeypatch.setattr("local_transcriber.executor.TranscriptionEngine", BrokenEngine)

    outcome = execute_job("job-1", runtime, ExecutorOptions(cache_dir=tmp_path / "cache"))

    assert outcome.status == "failed"
    assert outcome.exit_code == 3
    assert "model failed" in (outcome.error or "")
    assert store.load("job-1").status == "failed"
