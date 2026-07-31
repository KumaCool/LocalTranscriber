from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path

from local_transcriber.batches import BatchStore
from local_transcriber.executor import ExecutionOutcome, ExecutorOptions
from local_transcriber.jobs import JobStore
from local_transcriber.scheduler import BoundedScheduler, ResourceUsage, sample_process_tree


def _batch(tmp_path: Path, count: int = 3, *, workers: int = 2, threads: int = 2):
    runtime = tmp_path / "runtime"
    job_store = JobStore(runtime)
    task_ids = tuple(f"job-{index}" for index in range(count))
    budget = {
        "effective_workers": workers,
        "threads_per_worker": threads,
        "cpu_thread_limit": workers * threads,
        "cpu_limit_percent": 50,
        "memory_budget_bytes": 10_000_000_000,
        "worker_peak_rss_bytes": 1_000,
    }
    for index, task_id in enumerate(task_ids):
        job_store.create(
            task_id,
            str(tmp_path / f"input-{index}.wav"),
            tmp_path / f"out-{index}",
            batch_id="batch-1",
            input_order=index,
            effective_budget=budget,
        )
    BatchStore(runtime).create(
        "batch-1",
        task_ids=task_ids,
        run_mode="foreground",
        effective_budget=budget,
        output_dir=tmp_path / "out",
    )
    return runtime, task_ids


def _process_runner(job_id, runtime_dir, options, *, cancel_event=None):
    store = JobStore(runtime_dir)
    store.transition(job_id, "running")
    store.transition(job_id, "succeeded")
    return ExecutionOutcome(job_id, "succeeded", 0, error=str(os.getpid()))


def test_default_single_worker_recycles_process_between_model_jobs(
    tmp_path: Path,
) -> None:
    runtime, _ = _batch(tmp_path, count=2, workers=1)

    report = BoundedScheduler(
        runtime,
        runner=_process_runner,
        resource_sampler=lambda: ResourceUsage(10, 100, 11_000),
    ).run_batch("batch-1", ExecutorOptions(cache_dir=tmp_path / "cache"))

    worker_pids = {outcome.error for outcome in report.outcomes.values()}
    assert report.status == "succeeded"
    assert len(worker_pids) == 2


def test_scheduler_never_exceeds_worker_or_total_thread_budget(tmp_path: Path) -> None:
    runtime, task_ids = _batch(tmp_path, count=4, workers=2, threads=3)
    lock = threading.Lock()
    active = 0
    peak_active = 0

    def runner(job_id, runtime_dir, options, *, cancel_event=None):
        nonlocal active, peak_active
        store = JobStore(runtime_dir)
        store.transition(job_id, "running")
        with lock:
            active += 1
            peak_active = max(peak_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        store.transition(job_id, "succeeded")
        return ExecutionOutcome(job_id, "succeeded", 0)

    report = BoundedScheduler(
        runtime,
        runner=runner,
        executor_factory=ThreadPoolExecutor,
        sample_interval=0.001,
    ).run_batch("batch-1", ExecutorOptions(cache_dir=tmp_path / "cache", threads=3))

    assert set(report.outcomes) == set(task_ids)
    assert peak_active == 2
    assert report.peak_running_workers == 2
    assert report.peak_running_threads == 6
    assert report.peak_running_threads <= 6


def test_scheduler_isolates_failure_and_aggregates_batch_terminal_state(tmp_path: Path) -> None:
    runtime, task_ids = _batch(tmp_path, workers=2)

    def runner(job_id, runtime_dir, options, *, cancel_event=None):
        store = JobStore(runtime_dir)
        store.transition(job_id, "running")
        if job_id == "job-1":
            store.transition(job_id, "failed", error="boom")
            return ExecutionOutcome(job_id, "failed", 3, error="boom")
        store.transition(job_id, "succeeded")
        return ExecutionOutcome(job_id, "succeeded", 0)

    report = BoundedScheduler(
        runtime, runner=runner, executor_factory=ThreadPoolExecutor
    ).run_batch("batch-1", ExecutorOptions(cache_dir=tmp_path / "cache"))

    assert report.outcomes["job-1"].status == "failed"
    assert report.outcomes["job-0"].status == "succeeded"
    assert report.outcomes["job-2"].status == "succeeded"
    batch = BatchStore(runtime).load("batch-1")
    assert batch.status == "failed"
    assert batch.completed_count == len(task_ids)


def test_scheduler_does_not_compare_live_available_memory_to_startup_budget(
    tmp_path: Path,
) -> None:
    runtime, _ = _batch(tmp_path, count=1, workers=1)
    started: list[str] = []

    def runner(job_id, runtime_dir, options, *, cancel_event=None):
        started.append(job_id)
        store = JobStore(runtime_dir)
        store.transition(job_id, "running")
        store.transition(job_id, "succeeded")
        return ExecutionOutcome(job_id, "succeeded", 0)

    report = BoundedScheduler(
        runtime,
        runner=runner,
        executor_factory=ThreadPoolExecutor,
        resource_sampler=lambda: ResourceUsage(
            cpu_percent=10,
            rss_bytes=100,
            available_memory_bytes=9_000,
        ),
        overload_samples=1,
        sample_interval=0,
    ).run_batch("batch-1", ExecutorOptions(cache_dir=tmp_path / "cache"))

    assert started == ["job-0"]
    assert report.status == "succeeded"


def test_scheduler_reserves_next_worker_peak_against_rss_and_available_memory(
    tmp_path: Path,
) -> None:
    runtime, _ = _batch(tmp_path, count=1, workers=1)
    samples = iter(
        [
            ResourceUsage(10, 9_999_999_500, 2_000),
            ResourceUsage(10, 100, 500),
            ResourceUsage(10, 100, 2_000),
        ]
    )
    started: list[str] = []

    def runner(job_id, runtime_dir, options, *, cancel_event=None):
        started.append(job_id)
        store = JobStore(runtime_dir)
        store.transition(job_id, "running")
        store.transition(job_id, "succeeded")
        return ExecutionOutcome(job_id, "succeeded", 0)

    report = BoundedScheduler(
        runtime,
        runner=runner,
        executor_factory=ThreadPoolExecutor,
        resource_sampler=lambda: next(samples, ResourceUsage(10, 100, 2_000)),
        overload_samples=1,
        sample_interval=0,
    ).run_batch("batch-1", ExecutorOptions(cache_dir=tmp_path / "cache"))

    assert started == ["job-0"]
    assert report.status == "succeeded"
    assert "worker memory reserve exceeded scheduling budget" in report.degradation_reasons
    assert "available memory cannot fit next worker" in report.degradation_reasons


def test_scheduler_accumulates_unrealized_reserve_for_active_workers(tmp_path: Path) -> None:
    runtime, _ = _batch(tmp_path, count=2, workers=2)
    batch_path = runtime / "batches" / "batch-1.json"
    payload = json.loads(batch_path.read_text())
    payload["effective_budget"]["memory_budget_bytes"] = 1_500
    payload["effective_budget"]["worker_peak_rss_bytes"] = 1_000
    batch_path.write_text(json.dumps(payload))
    release = threading.Event()
    started: list[str] = []
    samples = iter(
        [
            ResourceUsage(10, 100, 3_000),
            ResourceUsage(10, 100, 3_000),
            ResourceUsage(10, 100, 3_000),
            ResourceUsage(10, 100, 3_000),
            ResourceUsage(10, 100, 3_000),
            ResourceUsage(10, 100, 3_000),
        ]
    )

    def runner(job_id, runtime_dir, options, *, cancel_event=None):
        started.append(job_id)
        store = JobStore(runtime_dir)
        store.transition(job_id, "running")
        if job_id == "job-0":
            release.wait(timeout=0.2)
        store.transition(job_id, "succeeded")
        return ExecutionOutcome(job_id, "succeeded", 0)

    def sampler():
        usage = next(samples, ResourceUsage(10, 100, 3_000))
        if started == ["job-0"]:
            release.set()
        return usage

    report = BoundedScheduler(
        runtime,
        runner=runner,
        executor_factory=ThreadPoolExecutor,
        resource_sampler=sampler,
        overload_samples=1,
        sample_interval=0.001,
    ).run_batch("batch-1", ExecutorOptions(cache_dir=tmp_path / "cache"))

    assert report.status == "succeeded"
    assert "worker memory reserve exceeded scheduling budget" in report.degradation_reasons


def test_scheduler_pauses_new_work_while_resource_guard_is_blocked(tmp_path: Path) -> None:
    runtime, _ = _batch(tmp_path, count=2, workers=1)
    samples = iter(
        [
            ResourceUsage(cpu_percent=90, rss_bytes=100, available_memory_bytes=11_000),
            ResourceUsage(cpu_percent=90, rss_bytes=100, available_memory_bytes=11_000),
            ResourceUsage(cpu_percent=10, rss_bytes=100, available_memory_bytes=11_000),
        ]
    )
    started: list[str] = []

    def sampler():
        return next(samples, ResourceUsage(10, 100, 11_000))

    def runner(job_id, runtime_dir, options, *, cancel_event=None):
        started.append(job_id)
        store = JobStore(runtime_dir)
        store.transition(job_id, "running")
        store.transition(job_id, "succeeded")
        return ExecutionOutcome(job_id, "succeeded", 0)

    report = BoundedScheduler(
        runtime,
        runner=runner,
        executor_factory=ThreadPoolExecutor,
        resource_sampler=sampler,
        overload_samples=2,
        sample_interval=0,
    ).run_batch("batch-1", ExecutorOptions(cache_dir=tmp_path / "cache"))

    assert started == ["job-0", "job-1"]
    assert report.degradation_reasons == ("CPU usage exceeded scheduling budget",)
    log = (runtime / "scheduler-degradations.jsonl").read_text(encoding="utf-8")
    assert "CPU usage exceeded scheduling budget" in log


def test_resource_sampler_counts_descendant_process_rss() -> None:
    import psutil

    root = psutil.Process()
    expected = root.memory_info().rss
    for child in root.children(recursive=True):
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            expected += child.memory_info().rss

    usage = sample_process_tree()

    assert usage.rss_bytes >= expected
    assert usage.available_memory_bytes > 0
    assert usage.cpu_percent >= 0


def test_process_worker_applies_independent_thread_environment(tmp_path: Path) -> None:
    runtime, _ = _batch(tmp_path, count=1, workers=1, threads=3)
    observed: list[str] = []

    def runner(job_id, runtime_dir, options, *, cancel_event=None):
        observed.extend([os.environ.get("OMP_NUM_THREADS", ""), str(options.threads)])
        store = JobStore(runtime_dir)
        store.transition(job_id, "running")
        store.transition(job_id, "succeeded")
        return ExecutionOutcome(job_id, "succeeded", 0)

    BoundedScheduler(runtime, runner=runner, executor_factory=ThreadPoolExecutor).run_batch(
        "batch-1", ExecutorOptions(cache_dir=tmp_path / "cache", threads=99)
    )

    assert observed[-1] == "3"


def test_scheduler_reports_persisted_progress_while_batch_is_running(tmp_path: Path) -> None:
    runtime, _ = _batch(tmp_path, count=2, workers=1)
    snapshots: list[tuple[str, float]] = []

    def runner(job_id, runtime_dir, options, *, cancel_event=None):
        store = JobStore(runtime_dir)
        store.transition(job_id, "running")
        store.update_progress(job_id, stage="transcribing", progress_percent=50)
        time.sleep(0.02)
        store.transition(job_id, "succeeded")
        return ExecutionOutcome(job_id, "succeeded", 0)

    def progress(batch, jobs):
        running = next((job for job in jobs if job.status == "running"), None)
        if running is not None:
            snapshots.append((batch.status, running.progress_percent))

    BoundedScheduler(
        runtime,
        runner=runner,
        executor_factory=ThreadPoolExecutor,
        sample_interval=0.001,
    ).run_batch(
        "batch-1",
        ExecutorOptions(cache_dir=tmp_path / "cache"),
        progress_callback=progress,
    )

    assert ("running", 50.0) in snapshots
