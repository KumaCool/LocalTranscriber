from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_transcriber.jobs import JobBusyError, JobStore


def test_job_lifecycle_persists_transitions(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    job = store.create("job-1", "input.wav", tmp_path / "out")
    assert job.status == "queued"

    running = store.transition("job-1", "running")
    succeeded = store.transition("job-1", "succeeded")

    assert running.started_at is not None
    assert succeeded.finished_at is not None
    assert store.load("job-1").status == "succeeded"
    assert json.loads((tmp_path / "jobs" / "job-1.json").read_text())["status"] == "succeeded"


def test_single_worker_lock_rejects_second_running_job(tmp_path: Path) -> None:
    first = JobStore(tmp_path)
    second = JobStore(tmp_path)

    with first.worker("job-1"), pytest.raises(JobBusyError), second.worker("job-2"):
        pass


def test_failed_job_keeps_diagnostic_and_cancelled_job_is_structured(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    store.create("failed", "bad.mp3", tmp_path / "out")
    failed = store.transition("failed", "failed", error="decoder rejected input")
    store.create("cancelled", "input.wav", tmp_path / "out")
    cancelled = store.transition("cancelled", "cancelled")

    assert failed.error == "decoder rejected input"
    assert failed.finished_at is not None
    assert cancelled.status == "cancelled"
    assert cancelled.finished_at is not None


def test_invalid_state_transition_is_rejected(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    store.create("job-1", "input.wav", tmp_path / "out")

    with pytest.raises(ValueError, match="transition"):
        store.transition("job-1", "succeeded")


def test_job_progress_is_persisted_and_never_moves_backwards(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    store.create("job-1", "input.wav", tmp_path / "out")
    store.transition("job-1", "running")

    first = store.update_progress(
        "job-1",
        stage="transcribing",
        progress_percent=40.0,
        processed_units=4,
        total_units=10,
        eta_low_seconds=12,
        eta_high_seconds=20,
    )
    second = store.update_progress(
        "job-1",
        stage="transcribing",
        progress_percent=30.0,
        processed_units=3,
        total_units=10,
    )

    assert first.progress_percent == 40.0
    assert second.progress_percent == 40.0
    assert second.processed_units == 4
    assert second.eta_low_seconds == 12
    assert second.eta_high_seconds == 20
    assert second.updated_at != second.created_at


def test_old_job_record_loads_with_safe_progress_defaults(tmp_path: Path) -> None:
    jobs = tmp_path / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "legacy.json").write_text(
        json.dumps(
            {
                "id": "legacy",
                "input_path": "input.wav",
                "output_dir": "out",
                "status": "running",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    job = JobStore(tmp_path).load("legacy")

    assert job.stage == "probing"
    assert job.progress_percent == 0.0
    assert job.processed_units == 0
    assert job.total_units == 0
    assert job.eta_low_seconds is None
    assert job.eta_high_seconds is None
    assert job.updated_at == job.created_at


def test_terminal_job_keeps_last_trusted_progress_and_success_alone_reaches_100(
    tmp_path: Path,
) -> None:
    store = JobStore(tmp_path)
    store.create("failed", "input.wav", tmp_path / "out")
    store.transition("failed", "running")
    store.update_progress("failed", stage="transcribing", progress_percent=64)
    failed = store.transition("failed", "failed", error="boom")

    store.create("ok", "input.wav", tmp_path / "out")
    store.transition("ok", "running")
    store.update_progress("ok", stage="finalizing", progress_percent=99)
    succeeded = store.transition("ok", "succeeded")

    assert failed.progress_percent == 64
    assert failed.stage == "transcribing"
    assert succeeded.progress_percent == 100
    assert succeeded.stage == "finalizing"
