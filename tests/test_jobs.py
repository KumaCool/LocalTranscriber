from __future__ import annotations

import json
import multiprocessing
import time
from pathlib import Path

import pytest

from local_transcriber.jobs import JobBusyError, JobStore

_BATCH_BUDGET = {"effective_workers": 1, "threads_per_worker": 2}


def _hold_scheduler_lock(root: str, ready) -> None:
    with JobStore(Path(root)).scheduler("owner-1"):
        ready.set()
        time.sleep(2)


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


def test_job_persists_batch_mode_order_budget_retry_and_artifacts(tmp_path: Path) -> None:
    store = JobStore(tmp_path)

    job = store.create(
        "job-1",
        "input.wav",
        tmp_path / "out",
        batch_id="batch-1",
        run_mode="background",
        input_order=2,
        effective_budget=_BATCH_BUDGET,
        attempt=2,
        retry_of="job-original",
        artifact_paths={"result": "out/job-1/result.json"},
    )

    assert job.schema_version == 2
    assert job.batch_id == "batch-1"
    assert job.run_mode == "background"
    assert job.input_order == 2
    assert job.effective_budget == _BATCH_BUDGET
    assert job.attempt == 2
    assert job.retry_of == "job-original"
    assert job.artifact_paths["result"].endswith("result.json")
    assert job.revision == 0


def test_running_job_can_be_marked_interrupted_and_cannot_restart(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    store.create("job-1", "input.wav", tmp_path / "out")
    store.transition("job-1", "running")

    interrupted = store.transition("job-1", "interrupted", error="worker disappeared")

    assert interrupted.status == "interrupted"
    assert interrupted.finished_at is not None
    with pytest.raises(ValueError, match="transition"):
        store.transition("job-1", "running")


def test_transition_rejects_stale_expected_revision(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    created = store.create("job-1", "input.wav", tmp_path / "out")
    running = store.transition("job-1", "running", expected_revision=created.revision)

    with pytest.raises(ValueError, match="revision"):
        store.transition("job-1", "failed", expected_revision=created.revision)

    assert running.revision == 1


def test_old_job_record_loads_with_safe_batch_defaults(tmp_path: Path) -> None:
    jobs = tmp_path / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "legacy-batch.json").write_text(
        json.dumps(
            {
                "id": "legacy-batch",
                "input_path": "input.wav",
                "output_dir": "out",
                "status": "queued",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    job = JobStore(tmp_path).load("legacy-batch")

    assert job.schema_version == 1
    assert job.batch_id is None
    assert job.run_mode == "foreground"
    assert job.input_order == 0
    assert job.effective_budget == {}
    assert job.attempt == 1
    assert job.retry_of is None
    assert job.artifact_paths == {}
    assert job.revision == 0


def test_scheduler_lock_rejects_another_process_and_records_owner(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(target=_hold_scheduler_lock, args=(str(tmp_path), ready))
    process.start()
    try:
        assert ready.wait(timeout=5)
        owner = json.loads((tmp_path / "scheduler.lock").read_text(encoding="utf-8"))
        assert owner["owner_id"] == "owner-1"
        assert owner["pid"] == process.pid
        assert owner["process_started_at"] > 0
        with (
            pytest.raises(JobBusyError, match="scheduler"),
            JobStore(tmp_path).scheduler("owner-2"),
        ):
            pass
    finally:
        process.terminate()
        process.join(timeout=5)
