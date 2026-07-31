from __future__ import annotations

import io
from pathlib import Path

from local_transcriber.batches import BatchStore
from local_transcriber.console import ForegroundConsole
from local_transcriber.jobs import JobStore


def _state(tmp_path: Path):
    runtime = tmp_path / "runtime"
    jobs = JobStore(runtime)
    budget = {"effective_workers": 1, "threads_per_worker": 2}
    jobs.create(
        "job-1",
        "/private/first.wav",
        tmp_path / "out-1",
        batch_id="batch-1",
        input_order=0,
        effective_budget=budget,
    )
    jobs.create(
        "job-2",
        "/private/second.wav",
        tmp_path / "out-2",
        batch_id="batch-1",
        input_order=1,
        effective_budget=budget,
    )
    BatchStore(runtime).create(
        "batch-1",
        task_ids=("job-1", "job-2"),
        run_mode="foreground",
        effective_budget=budget,
        output_dir=tmp_path / "out",
    )
    return runtime, jobs


def test_non_tty_console_emits_stable_progress_events_without_private_paths(tmp_path: Path) -> None:
    runtime, jobs = _state(tmp_path)
    stream = io.StringIO()
    console = ForegroundConsole(runtime, "batch-1", stream=stream, is_tty=False)

    console.refresh()
    jobs.transition("job-1", "running")
    jobs.update_progress(
        "job-1",
        stage="transcribing",
        progress_percent=50,
        eta_low_seconds=10,
        eta_high_seconds=20,
    )
    console.refresh()
    jobs.transition("job-1", "succeeded")
    console.refresh()
    console.finish()

    output = stream.getvalue()
    assert "batch=batch-1" in output
    assert "completed=0/2" in output
    assert "running=1" in output
    assert "progress=50.0%" in output
    assert "eta=10-20s" in output
    assert "completed=1/2" in output
    assert "/private/" not in output
    assert "\r" not in output


def test_tty_console_uses_carriage_return_and_finishes_with_newline(tmp_path: Path) -> None:
    runtime, _ = _state(tmp_path)
    stream = io.StringIO()
    console = ForegroundConsole(runtime, "batch-1", stream=stream, is_tty=True)

    console.refresh()
    console.finish()

    assert stream.getvalue().startswith("\r")
    assert stream.getvalue().endswith("\n")
