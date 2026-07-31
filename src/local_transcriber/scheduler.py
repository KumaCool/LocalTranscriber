from __future__ import annotations

import json
import multiprocessing
import os
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from pathlib import Path

import psutil

from local_transcriber.batches import BatchStore, StoredBatch
from local_transcriber.executor import ExecutionOutcome, ExecutorOptions, execute_job
from local_transcriber.jobs import JobStore


@dataclass(frozen=True)
class ResourceUsage:
    cpu_percent: float
    rss_bytes: int
    available_memory_bytes: int


@dataclass(frozen=True)
class SchedulerReport:
    batch_id: str
    status: str
    outcomes: dict[str, ExecutionOutcome]
    peak_running_workers: int
    peak_running_threads: int
    degradation_reasons: tuple[str, ...] = field(default_factory=tuple)


def sample_process_tree() -> ResourceUsage:
    root = psutil.Process()
    processes = [root, *root.children(recursive=True)]
    cpu_percent = 0.0
    rss_bytes = 0
    for process in processes:
        try:
            cpu_percent += process.cpu_percent(interval=None)
            rss_bytes += process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return ResourceUsage(
        cpu_percent=cpu_percent,
        rss_bytes=rss_bytes,
        available_memory_bytes=psutil.virtual_memory().available,
    )


def _run_worker(
    runner: Callable,
    job_id: str,
    runtime_dir: Path,
    options: ExecutorOptions,
    cancel_event,
) -> ExecutionOutcome:
    os.environ["OMP_NUM_THREADS"] = str(options.threads)
    os.environ["MKL_NUM_THREADS"] = str(options.threads)
    return runner(job_id, runtime_dir, options, cancel_event=cancel_event)


class BoundedScheduler:
    def __init__(
        self,
        runtime_dir: Path,
        *,
        runner: Callable = execute_job,
        executor_factory=ProcessPoolExecutor,
        resource_sampler: Callable[[], ResourceUsage] = sample_process_tree,
        overload_samples: int = 3,
        sample_interval: float = 0.1,
    ) -> None:
        if overload_samples < 1 or sample_interval < 0:
            raise ValueError("invalid scheduler sampling policy")
        self.runtime_dir = runtime_dir
        self.runner = runner
        self.executor_factory = executor_factory
        self.resource_sampler = resource_sampler
        self.overload_samples = overload_samples
        self.sample_interval = sample_interval
        self._manager = None
        self._cancel_events: dict[str, object] = {}
        self._degradation_log = runtime_dir / "scheduler-degradations.jsonl"

    def cancel_event(self, job_id: str):
        event = self._cancel_events.get(job_id)
        if event is None:
            if self.executor_factory is ProcessPoolExecutor:
                if self._manager is None:
                    self._manager = multiprocessing.Manager()
                event = self._manager.Event()
            else:
                event = threading.Event()
            self._cancel_events[job_id] = event
        return event

    @staticmethod
    def _budget(batch: StoredBatch) -> tuple[int, int, int, int]:
        values = batch.effective_budget
        workers = int(values.get("effective_workers", 0))
        threads = int(values.get("threads_per_worker", 0))
        cpu_threads = int(values.get("cpu_thread_limit", workers * threads))
        memory_budget = int(values.get("memory_budget_bytes", 0))
        if workers < 1 or threads < 1 or workers * threads > cpu_threads:
            raise ValueError("batch effective budget cannot safely start a worker")
        return workers, threads, int(values.get("cpu_limit_percent", 50)), memory_budget

    def _wait_until_safe(
        self,
        *,
        cpu_limit_percent: int,
        memory_budget_bytes: int,
        reasons: list[str],
    ) -> None:
        consecutive = 0
        while True:
            usage = self.resource_sampler()
            cpu_blocked = usage.cpu_percent > cpu_limit_percent
            memory_blocked = (
                memory_budget_bytes > 0 and usage.available_memory_bytes < memory_budget_bytes
            )
            if not cpu_blocked and not memory_blocked:
                return
            consecutive += 1
            if consecutive >= self.overload_samples:
                reason = (
                    "available memory fell below scheduling safety line"
                    if memory_blocked
                    else "CPU usage exceeded scheduling budget"
                )
                if reason not in reasons:
                    reasons.append(reason)
                    self._degradation_log.parent.mkdir(parents=True, exist_ok=True)
                    with self._degradation_log.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps({"reason": reason}) + "\n")
            time.sleep(self.sample_interval)

    def run_batch(self, batch_id: str, options: ExecutorOptions) -> SchedulerReport:
        job_store = JobStore(self.runtime_dir)
        batch_store = BatchStore(self.runtime_dir)
        batch = batch_store.load(batch_id)
        workers, threads, cpu_limit, memory_budget = self._budget(batch)
        options = replace(options, threads=threads)
        pending = list(batch.task_ids)
        outcomes: dict[str, ExecutionOutcome] = {}
        active = {}
        reasons: list[str] = []
        peak_workers = 0
        owner_id = f"scheduler-{os.getpid()}-{uuid.uuid4().hex[:8]}"

        pool_factory = (
            ThreadPoolExecutor
            if workers == 1 and self.executor_factory is ProcessPoolExecutor
            else self.executor_factory
        )
        with job_store.scheduler(owner_id), pool_factory(max_workers=workers) as pool:
            while pending or active:
                while pending and len(active) < workers:
                    self._wait_until_safe(
                        cpu_limit_percent=cpu_limit,
                        memory_budget_bytes=memory_budget,
                        reasons=reasons,
                    )
                    job_id = pending.pop(0)
                    future = pool.submit(
                        _run_worker,
                        self.runner,
                        job_id,
                        self.runtime_dir,
                        options,
                        self.cancel_event(job_id),
                    )
                    active[future] = job_id
                    peak_workers = max(peak_workers, len(active))
                if not active:
                    continue
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    job_id = active.pop(future)
                    try:
                        outcomes[job_id] = future.result()
                    except BaseException as exc:
                        current = job_store.load(job_id)
                        if current.status in {"queued", "running"}:
                            job_store.transition(job_id, "failed", error=str(exc))
                        outcomes[job_id] = ExecutionOutcome(job_id, "failed", 3, error=str(exc))
                batch_store.aggregate(
                    batch_id,
                    {task_id: job_store.load(task_id).status for task_id in batch.task_ids},
                )

        batch = batch_store.load(batch_id)
        return SchedulerReport(
            batch_id=batch_id,
            status=batch.status,
            outcomes=outcomes,
            peak_running_workers=peak_workers,
            peak_running_threads=peak_workers * threads,
            degradation_reasons=tuple(reasons),
        )
