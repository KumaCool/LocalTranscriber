from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import psutil

from local_transcriber.config import ResourceConfig


@dataclass(frozen=True)
class ResourceSnapshot:
    logical_cpu: int
    available_memory_bytes: int
    total_memory_bytes: int

    @classmethod
    def capture(cls) -> ResourceSnapshot:
        memory = psutil.virtual_memory()
        return cls(
            logical_cpu=psutil.cpu_count(logical=True) or 1,
            available_memory_bytes=memory.available,
            total_memory_bytes=memory.total,
        )


@dataclass(frozen=True)
class EffectiveBudget:
    cpu_limit_percent: int
    memory_limit_percent: int
    requested_workers: int
    threads_per_worker: int
    cpu_thread_limit: int
    cpu_worker_limit: int
    memory_budget_bytes: int
    worker_peak_rss_bytes: int
    memory_worker_limit: int
    effective_workers: int
    nice: int
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def calculate_budget(
    config: ResourceConfig,
    snapshot: ResourceSnapshot,
    *,
    worker_peak_rss_bytes: int,
) -> EffectiveBudget:
    if snapshot.logical_cpu < 1:
        raise ValueError("logical_cpu must be positive")
    if snapshot.available_memory_bytes < 0 or snapshot.total_memory_bytes < 1:
        raise ValueError("invalid memory snapshot")
    if worker_peak_rss_bytes < 1:
        raise ValueError("worker_peak_rss_bytes must be positive")

    cpu_thread_limit = max(1, math.floor(snapshot.logical_cpu * config.cpu_limit_percent / 100))
    cpu_worker_limit = cpu_thread_limit // config.threads_per_worker
    configured_memory_limit = math.floor(
        snapshot.total_memory_bytes * config.memory_limit_percent / 100
    )
    memory_budget_bytes = configured_memory_limit
    memory_worker_limit = min(
        memory_budget_bytes // worker_peak_rss_bytes,
        snapshot.available_memory_bytes // worker_peak_rss_bytes,
    )
    effective_workers = min(
        config.max_workers,
        cpu_worker_limit,
        memory_worker_limit,
    )
    rejection_reason = None
    if memory_worker_limit < 1:
        rejection_reason = "insufficient memory for one worker"
    elif cpu_worker_limit < 1:
        rejection_reason = "CPU budget cannot fit one worker"

    return EffectiveBudget(
        cpu_limit_percent=config.cpu_limit_percent,
        memory_limit_percent=config.memory_limit_percent,
        requested_workers=config.max_workers,
        threads_per_worker=config.threads_per_worker,
        cpu_thread_limit=cpu_thread_limit,
        cpu_worker_limit=cpu_worker_limit,
        memory_budget_bytes=memory_budget_bytes,
        worker_peak_rss_bytes=worker_peak_rss_bytes,
        memory_worker_limit=memory_worker_limit,
        effective_workers=effective_workers,
        nice=config.nice,
        rejection_reason=rejection_reason,
    )
