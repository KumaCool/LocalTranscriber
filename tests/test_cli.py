from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from local_transcriber.batches import BatchStore
from local_transcriber.cli import main
from local_transcriber.executor import ExecutionOutcome
from local_transcriber.jobs import JobStore
from local_transcriber.scheduler import SchedulerReport
from local_transcriber.schema import read_result


def _fixture(path: Path, *, frequency: int = 440) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration=0.1",
            str(path),
        ],
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

        def transcribe(self, path: Path, progress_callback=None):
            assert path.name == "normalized.wav"
            return [{"start_ms": 0, "end_ms": 90, "speaker": "SPEAKER_00", "text": "你好"}]

    monkeypatch.setattr("local_transcriber.executor.TranscriptionEngine", FakeEngine)
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

        def transcribe(self, path: Path, progress_callback=None):
            raise RuntimeError("model failed")

    monkeypatch.setattr("local_transcriber.executor.TranscriptionEngine", BrokenEngine)

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


def test_transcribe_cli_does_not_succeed_before_all_exports_are_written(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)

    class FakeEngine:
        def __init__(self, **kwargs):
            self.info = kwargs

        def transcribe(self, path: Path, progress_callback=None):
            return [{"start_ms": 0, "end_ms": 90, "speaker": "SPEAKER_00", "text": "你好"}]

    def broken_export(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("local_transcriber.executor.TranscriptionEngine", FakeEngine)
    monkeypatch.setattr("local_transcriber.executor.export_result", broken_export)
    runtime = tmp_path / "runtime"

    code = main(
        [
            "transcribe",
            str(source),
            "--output-dir",
            str(tmp_path / "out"),
            "--runtime-dir",
            str(runtime),
        ]
    )

    payload = json.loads(next((runtime / "jobs").glob("*.json")).read_text())
    assert code == 3
    assert payload["status"] == "failed"
    assert payload["progress_percent"] < 100


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

        def transcribe(self, path: Path, progress_callback=None):
            return [{"start_ms": 0, "end_ms": 90, "speaker": "SPEAKER_00", "text": "你好"}]

    monkeypatch.setattr("local_transcriber.executor.TranscriptionEngine", FakeEngine)
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


def test_job_status_command_returns_machine_readable_progress(tmp_path: Path, capsys) -> None:
    runtime = tmp_path / "runtime"
    from local_transcriber.jobs import JobStore

    store = JobStore(runtime)
    store.create("job-1", "/private/meeting.wav", tmp_path / "out")
    store.transition("job-1", "running")
    store.update_progress(
        "job-1",
        stage="transcribing",
        progress_percent=47,
        processed_units=4,
        total_units=10,
        eta_low_seconds=20,
        eta_high_seconds=35,
    )

    assert main(["job", "status", "job-1", "--runtime-dir", str(runtime), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == "job-1"
    assert payload["stage"] == "transcribing"
    assert payload["progress_percent"] == 47
    assert payload["eta_low_seconds"] == 20
    assert payload["eta_high_seconds"] == 35
    assert "input_path" not in payload


def test_job_status_unknown_runtime_is_strictly_read_only(tmp_path: Path, capsys) -> None:
    runtime = tmp_path / "missing-runtime"

    assert main(["job", "status", "missing", "--runtime-dir", str(runtime), "--json"]) == 2
    assert "unknown job" in capsys.readouterr().err
    assert not runtime.exists()


def test_transcribe_accepts_multiple_inputs_in_user_order(tmp_path: Path, monkeypatch) -> None:
    first = tmp_path / "b.wav"
    second = tmp_path / "a.wav"
    _fixture(first, frequency=330)
    _fixture(second, frequency=550)

    def run_batch(self, batch_id, options, *, progress_callback=None):
        batch = BatchStore(self.runtime_dir).load(batch_id)
        jobs = JobStore(self.runtime_dir)
        outcomes = {}
        for job_id in batch.task_ids:
            jobs.transition(job_id, "running")
            jobs.transition(job_id, "succeeded")
            outcomes[job_id] = ExecutionOutcome(job_id, "succeeded", 0)
        BatchStore(self.runtime_dir).aggregate(
            batch_id, {job_id: "succeeded" for job_id in batch.task_ids}
        )
        return SchedulerReport(batch_id, "succeeded", outcomes, 1, options.threads)

    monkeypatch.setattr("local_transcriber.cli.BoundedScheduler.run_batch", run_batch)

    code = main(
        [
            "transcribe",
            str(first),
            str(second),
            "--output-dir",
            str(tmp_path / "output"),
            "--runtime-dir",
            str(tmp_path / "runtime"),
        ]
    )

    assert code == 0
    records = sorted(
        (json.loads(path.read_text()) for path in (tmp_path / "runtime" / "jobs").glob("*.json")),
        key=lambda payload: payload["input_order"],
    )
    assert [Path(record["input_path"]) for record in records] == [first.resolve(), second.resolve()]
    assert [Path(record["output_dir"]).name.rsplit("-", 2)[0] for record in records] == ["b", "a"]
    assert len({record["output_dir"] for record in records}) == 2


def test_transcribe_dir_dry_run_is_read_only_and_does_not_load_model(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "input"
    top = source / "top.wav"
    nested = source / "nested" / "nested.wav"
    source.mkdir()
    _fixture(top, frequency=330)
    nested.parent.mkdir()
    _fixture(nested, frequency=550)

    class ForbiddenEngine:
        def __init__(self, **kwargs):
            raise AssertionError("dry-run must not load the model")

    monkeypatch.setattr("local_transcriber.executor.TranscriptionEngine", ForbiddenEngine)
    runtime = tmp_path / "runtime"
    output = tmp_path / "output"

    assert (
        main(
            [
                "transcribe-dir",
                str(source),
                "--recursive",
                "--dry-run",
                "--json",
                "--output-dir",
                str(output),
                "--runtime-dir",
                str(runtime),
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert [item["relative_path"] for item in payload["accepted"]] == [
        "nested/nested.wav",
        "top.wav",
    ]
    assert not runtime.exists()
    assert not output.exists()


def test_transcribe_cli_persists_event_driven_progress(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)

    class FakeEngine:
        def __init__(self, **kwargs):
            self.info = kwargs

        def transcribe(self, path: Path, progress_callback=None):
            assert progress_callback is not None
            progress_callback(1, 4)
            progress_callback(3, 4)
            return [{"start_ms": 0, "end_ms": 90, "speaker": "SPEAKER_00", "text": "你好"}]

    monkeypatch.setattr("local_transcriber.executor.TranscriptionEngine", FakeEngine)
    runtime = tmp_path / "runtime"
    assert (
        main(
            [
                "transcribe",
                str(source),
                "--output-dir",
                str(tmp_path / "output"),
                "--runtime-dir",
                str(runtime),
            ]
        )
        == 0
    )

    payload = json.loads(next((runtime / "jobs").glob("*.json")).read_text())
    assert payload["status"] == "succeeded"
    assert payload["stage"] == "finalizing"
    assert payload["progress_percent"] == 100
    assert payload["processed_units"] == 3
    assert payload["total_units"] == 4


def test_foreground_batch_emits_summary_and_returns_execution_failure_code(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    _fixture(first, frequency=330)
    _fixture(second, frequency=550)

    def run_batch(self, batch_id, options, *, progress_callback=None):
        batch = BatchStore(self.runtime_dir).load(batch_id)
        jobs = JobStore(self.runtime_dir)
        outcomes = {}
        for index, job_id in enumerate(batch.task_ids):
            jobs.transition(job_id, "running")
            if index == 0:
                jobs.transition(job_id, "succeeded")
                outcomes[job_id] = ExecutionOutcome(job_id, "succeeded", 0)
            else:
                jobs.transition(job_id, "failed", error="model failed")
                outcomes[job_id] = ExecutionOutcome(job_id, "failed", 3, error="model failed")
            if progress_callback is not None:
                BatchStore(self.runtime_dir).aggregate(
                    batch_id,
                    {task_id: jobs.load(task_id).status for task_id in batch.task_ids},
                )
                progress_callback(
                    BatchStore(self.runtime_dir).load(batch_id),
                    tuple(jobs.load(task_id) for task_id in batch.task_ids),
                )
        return SchedulerReport(batch_id, "failed", outcomes, 1, options.threads)

    from local_transcriber.batches import BatchStore
    from local_transcriber.jobs import JobStore

    monkeypatch.setattr("local_transcriber.cli.BoundedScheduler.run_batch", run_batch)

    code = main(
        [
            "transcribe",
            str(first),
            str(second),
            "--output-dir",
            str(tmp_path / "out"),
            "--runtime-dir",
            str(tmp_path / "runtime"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 3
    assert "summary" in captured.err
    assert "succeeded=1" in captured.err
    assert "failed=1" in captured.err
    assert str(first) not in captured.err


def test_foreground_keyboard_interrupt_cancels_all_nonterminal_tasks(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)

    def interrupt(self, batch_id, options, *, progress_callback=None):
        raise KeyboardInterrupt

    monkeypatch.setattr("local_transcriber.cli.BoundedScheduler.run_batch", interrupt)
    runtime = tmp_path / "runtime"

    assert (
        main(
            [
                "transcribe",
                str(source),
                "--output-dir",
                str(tmp_path / "out"),
                "--runtime-dir",
                str(runtime),
            ]
        )
        == 130
    )
    payload = json.loads(next((runtime / "jobs").glob("*.json")).read_text())
    assert payload["status"] == "cancelled"
    assert "cancelled" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        ([0, 0], 0),
        ([0, 2], 2),
        ([2, 3], 3),
        ([3, 130], 130),
        ([4, 3], 4),
    ],
)
def test_batch_exit_code_has_stable_severity(codes: list[int], expected: int) -> None:
    from local_transcriber.cli import _batch_exit_code

    assert _batch_exit_code(codes) == expected


def test_explicit_bg_persists_background_batch_and_returns_ids_without_running_engine(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)
    submitted: dict[str, object] = {}

    def request(self, payload):
        submitted.update(payload)
        return {"ok": True, "batch_id": payload["batch_id"]}

    monkeypatch.setattr("local_transcriber.cli.UnixIPCClient.request", request)
    monkeypatch.setattr(
        "local_transcriber.cli.BoundedScheduler.run_batch",
        lambda *args, **kwargs: pytest.fail("background submission must not run the engine"),
    )
    runtime = tmp_path / "runtime"

    assert (
        main(
            [
                "transcribe",
                str(source),
                "--bg",
                "--json",
                "--output-dir",
                str(tmp_path / "out"),
                "--runtime-dir",
                str(runtime),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    batch = json.loads(next((runtime / "batches").glob("*.json")).read_text())
    job = json.loads(next((runtime / "jobs").glob("*.json")).read_text())
    assert payload["mode"] == "background"
    assert payload["batch_id"] == batch["id"] == submitted["batch_id"]
    assert payload["task_ids"] == [job["id"]]
    assert batch["run_mode"] == job["run_mode"] == "background"
    assert payload["status_command"] == f"local-transcriber batch status {batch['id']}"


def test_bg_manager_failure_is_reported_without_false_submission(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)

    def unavailable(self, payload):
        from local_transcriber.ipc import IPCError

        raise IPCError("background manager is not available")

    monkeypatch.setattr("local_transcriber.cli.UnixIPCClient.request", unavailable)
    monkeypatch.setattr(
        "local_transcriber.cli.service_control",
        lambda action, runtime: {"ok": False, "error": "user systemd is not available"},
    )
    runtime = tmp_path / "runtime"
    code = main(
        [
            "transcribe",
            str(source),
            "--bg",
            "--output-dir",
            str(tmp_path / "out"),
            "--runtime-dir",
            str(runtime),
        ]
    )
    assert code == 4
    assert "not submitted" in capsys.readouterr().err
    assert json.loads(next((runtime / "batches").glob("*.json")).read_text())["status"] == "queued"


def test_bg_starts_user_manager_then_retries_submission(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "meeting.wav"
    _fixture(source)
    requests = 0
    starts: list[tuple[str, Path]] = []

    def request(self, payload):
        nonlocal requests
        requests += 1
        if requests == 1:
            from local_transcriber.ipc import IPCError

            raise IPCError("background manager is not available")
        return {"ok": True, "batch_id": payload["batch_id"]}

    def control(action, runtime):
        starts.append((action, runtime))
        return {"ok": True}

    monkeypatch.setattr("local_transcriber.cli.UnixIPCClient.request", request)
    monkeypatch.setattr("local_transcriber.cli.service_control", control)
    runtime = tmp_path / "runtime"
    assert (
        main(
            [
                "transcribe",
                str(source),
                "--bg",
                "--output-dir",
                str(tmp_path / "out"),
                "--runtime-dir",
                str(runtime),
            ]
        )
        == 0
    )
    assert starts == [("start", runtime)]
    assert requests == 2


@pytest.mark.parametrize("flag", ["--background", "—bg"])
def test_transcribe_rejects_bg_aliases(flag: str, tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "transcribe",
                str(tmp_path / "input.wav"),
                flag,
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )


def test_worker_cli_exposes_run_and_lifecycle_commands(tmp_path: Path, monkeypatch, capsys) -> None:
    calls: list[tuple[str, Path]] = []

    def control(action, runtime):
        calls.append((action, runtime))
        return {"ok": True, "running": action in {"start", "restart", "status"}}

    monkeypatch.setattr("local_transcriber.cli.service_control", control)
    runtime = tmp_path / "runtime"
    for action in ("start", "status", "stop", "restart"):
        assert main(["worker", action, "--runtime-dir", str(runtime), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["ok"] is True
    assert calls == [(action, runtime) for action in ("start", "status", "stop", "restart")]


def test_worker_run_owns_manager_in_current_process(tmp_path: Path, monkeypatch) -> None:
    events: list[str] = []

    class FakeManager:
        def __init__(self, runtime):
            events.append(f"init:{runtime}")

        def run(self):
            events.append("run")

        def close(self):
            events.append("close")

    monkeypatch.setattr("local_transcriber.cli.BackgroundManager", FakeManager)
    runtime = tmp_path / "runtime"
    assert main(["worker", "run", "--runtime-dir", str(runtime)]) == 0
    assert events == [f"init:{runtime}", "run", "close"]
