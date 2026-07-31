from __future__ import annotations

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
