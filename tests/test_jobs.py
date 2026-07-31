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
