from __future__ import annotations

import json
import threading
from contextlib import suppress
from pathlib import Path

from local_transcriber.batches import BatchStore
from local_transcriber.daemon import BackgroundManager
from local_transcriber.jobs import JobStore

BUDGET = {
    "effective_workers": 1,
    "threads_per_worker": 1,
    "cpu_thread_limit": 1,
    "cpu_limit_percent": 50,
    "memory_budget_bytes": 1024,
}
OPTIONS = {"cache_dir": "cache", "threads": 1, "language": "auto", "keep_normalized": False}


def _batch(runtime: Path, statuses: tuple[str, ...] = ("queued",)) -> None:
    jobs = JobStore(runtime)
    task_ids = []
    for index, status in enumerate(statuses):
        job_id = f"job-{index}"
        task_ids.append(job_id)
        jobs.create(
            job_id,
            f"/private/input-{index}.wav",
            runtime / "out" / job_id,
            batch_id="batch-1",
            run_mode="background",
            input_order=index,
            effective_budget=BUDGET,
        )
        if status == "running":
            jobs.transition(job_id, "running")
        elif status != "queued":
            if status in {"succeeded", "interrupted"}:
                jobs.transition(job_id, "running")
            jobs.transition(job_id, status)
    BatchStore(runtime).create(
        "batch-1",
        task_ids=tuple(task_ids),
        run_mode="background",
        effective_budget=BUDGET,
        execution_options=OPTIONS,
        output_dir=runtime / "out",
    )
    BatchStore(runtime).aggregate(
        "batch-1", {task_id: jobs.load(task_id).status for task_id in task_ids}
    )


def test_manager_startup_marks_orphan_running_interrupted_and_recovers_only_queued(
    tmp_path: Path, monkeypatch
) -> None:
    _batch(tmp_path, ("running", "queued", "succeeded"))
    calls: list[tuple[str, str]] = []
    release = threading.Event()

    def run_batch(self, batch_id, options, *, progress_callback=None):
        calls.append((batch_id, options.language))
        release.wait(timeout=2)

    monkeypatch.setattr("local_transcriber.daemon.BoundedScheduler.run_batch", run_batch)
    manager = BackgroundManager(tmp_path)
    try:
        assert JobStore(tmp_path).load("job-0").status == "interrupted"
        assert JobStore(tmp_path).load("job-1").status == "queued"
        assert JobStore(tmp_path).load("job-2").status == "succeeded"
        assert calls == [("batch-1", "auto")]
    finally:
        release.set()
        manager.close()


def test_retry_creates_new_evidence_and_never_overwrites_success(
    tmp_path: Path, monkeypatch
) -> None:
    _batch(tmp_path, ("failed", "interrupted", "cancelled", "succeeded"))
    started: list[str] = []
    monkeypatch.setattr(
        BackgroundManager, "_start_batch", lambda self, batch_id: started.append(batch_id)
    )
    manager = BackgroundManager(tmp_path, recover=False)
    try:
        response = manager.handle({"action": "retry_batch", "batch_id": "batch-1"})
    finally:
        manager.close()

    assert response["ok"] is True
    assert started == [response["batch_id"]]
    retry_batch = BatchStore(tmp_path).load(str(response["batch_id"]))
    assert len(retry_batch.task_ids) == 3
    retries = [JobStore(tmp_path).load(task_id) for task_id in retry_batch.task_ids]
    assert {job.retry_of for job in retries} == {"job-0", "job-1", "job-2"}
    assert all(job.attempt == 2 and job.status == "queued" for job in retries)
    assert all(
        job.output_dir != JobStore(tmp_path).load(job.retry_of or "").output_dir for job in retries
    )
    assert JobStore(tmp_path).load("job-3").status == "succeeded"


def test_durable_write_interruption_preserves_previous_job_record(
    tmp_path: Path, monkeypatch
) -> None:
    store = JobStore(tmp_path)
    store.create("job-1", "secret.wav", tmp_path / "out")

    def broken_replace(source, destination):
        raise OSError("crash during replace")

    monkeypatch.setattr("local_transcriber.jobs.os.replace", broken_replace)
    with suppress(OSError):
        store.transition("job-1", "cancelled")

    payload = json.loads((tmp_path / "jobs" / "job-1.json").read_text())
    assert payload["status"] == "queued"
    assert not list((tmp_path / "jobs").glob("*.tmp"))
