from __future__ import annotations

from pathlib import Path

from local_transcriber.config import ResourceConfig
from local_transcriber.resources import ResourceSnapshot, calculate_budget


def test_budget_uses_smallest_worker_limit_and_respects_total_thread_budget() -> None:
    config = ResourceConfig(
        cpu_limit_percent=50,
        memory_limit_percent=80,
        max_workers=4,
        threads_per_worker=2,
    )
    snapshot = ResourceSnapshot(
        logical_cpu=8,
        available_memory_bytes=10_000,
        total_memory_bytes=20_000,
    )

    budget = calculate_budget(config, snapshot, worker_peak_rss_bytes=3_000)

    assert budget.cpu_thread_limit == 4
    assert budget.cpu_worker_limit == 2
    assert budget.memory_worker_limit == 3
    assert budget.effective_workers == 2
    assert budget.effective_workers * budget.threads_per_worker <= budget.cpu_thread_limit
    assert budget.rejection_reason is None


def test_budget_rejects_when_memory_cannot_fit_one_worker() -> None:
    config = ResourceConfig(memory_limit_percent=50, max_workers=4, threads_per_worker=1)
    snapshot = ResourceSnapshot(
        logical_cpu=8,
        available_memory_bytes=1_000,
        total_memory_bytes=20_000,
    )

    budget = calculate_budget(config, snapshot, worker_peak_rss_bytes=2_000)

    assert budget.memory_worker_limit == 0
    assert budget.effective_workers == 0
    assert budget.rejection_reason == "insufficient memory for one worker"


def test_budget_separates_process_limit_from_current_available_memory() -> None:
    config = ResourceConfig(memory_limit_percent=70, max_workers=1, threads_per_worker=1)
    snapshot = ResourceSnapshot(
        logical_cpu=4,
        available_memory_bytes=2_000,
        total_memory_bytes=10_000,
    )

    budget = calculate_budget(config, snapshot, worker_peak_rss_bytes=2_000)

    assert budget.memory_budget_bytes == 7_000
    assert budget.memory_worker_limit == 1
    assert budget.effective_workers == 1


def test_budget_serializes_effective_policy_to_json_dictionary() -> None:
    config = ResourceConfig(max_workers=2, threads_per_worker=1)
    snapshot = ResourceSnapshot(
        logical_cpu=4,
        available_memory_bytes=8_000,
        total_memory_bytes=10_000,
    )

    payload = calculate_budget(config, snapshot, worker_peak_rss_bytes=2_000).to_dict()

    assert payload["cpu_limit_percent"] == 50
    assert payload["memory_limit_percent"] == 70
    assert payload["effective_workers"] == 2
    assert payload["threads_per_worker"] == 1
    assert payload["worker_peak_rss_bytes"] == 2_000


def test_zero_cpu_limit_uses_all_logical_cpus() -> None:
    config = ResourceConfig(
        cpu_limit_percent=0,
        memory_limit_percent=100,
        max_workers=4,
        threads_per_worker=2,
    )
    snapshot = ResourceSnapshot(
        logical_cpu=8,
        available_memory_bytes=20_000,
        total_memory_bytes=20_000,
    )

    budget = calculate_budget(config, snapshot, worker_peak_rss_bytes=2_000)

    assert budget.cpu_thread_limit == 8
    assert budget.cpu_worker_limit == 4
    assert budget.effective_workers == 4


def test_zero_cpu_limit_disables_runtime_cpu_usage_guard() -> None:
    from local_transcriber.scheduler import BoundedScheduler, ResourceUsage

    scheduler = BoundedScheduler(
        Path("unused"),
        resource_sampler=lambda: ResourceUsage(
            cpu_percent=999,
            rss_bytes=0,
            available_memory_bytes=10_000,
        ),
        sample_interval=0,
    )

    assert scheduler._wait_until_safe(
        cpu_limit_percent=0,
        memory_budget_bytes=0,
        worker_reserve_bytes=1,
        active_reserve_bytes=0,
        has_active_workers=False,
        reasons=[],
    )


def test_zero_memory_limit_uses_current_available_memory_without_percentage_cap() -> None:
    config = ResourceConfig(
        cpu_limit_percent=100,
        memory_limit_percent=0,
        max_workers=4,
        threads_per_worker=1,
    )
    snapshot = ResourceSnapshot(
        logical_cpu=8,
        available_memory_bytes=8_000,
        total_memory_bytes=10_000,
    )

    budget = calculate_budget(config, snapshot, worker_peak_rss_bytes=2_000)

    assert budget.memory_budget_bytes == 0
    assert budget.memory_worker_limit == 4
    assert budget.effective_workers == 4
