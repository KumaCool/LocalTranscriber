from __future__ import annotations

from pathlib import Path

import pytest

from local_transcriber.batches import BatchStore


def _create_batch(store: BatchStore, tmp_path: Path, *, mode: str = "foreground"):
    return store.create(
        "batch-1",
        task_ids=("job-1", "job-2", "job-3"),
        run_mode=mode,
        effective_budget={"effective_workers": 1, "threads_per_worker": 2},
        output_dir=tmp_path / "out",
    )


def test_batch_persists_mode_order_and_effective_budget(tmp_path: Path) -> None:
    store = BatchStore(tmp_path)

    batch = _create_batch(store, tmp_path)
    loaded = store.load(batch.id)

    assert loaded.run_mode == "foreground"
    assert loaded.task_ids == ("job-1", "job-2", "job-3")
    assert loaded.effective_budget == {"effective_workers": 1, "threads_per_worker": 2}
    assert loaded.status == "queued"


@pytest.mark.parametrize("mode", ["foreground", "background"])
def test_batch_accepts_only_explicit_run_modes(tmp_path: Path, mode: str) -> None:
    store = BatchStore(tmp_path)

    assert _create_batch(store, tmp_path, mode=mode).run_mode == mode


def test_batch_rejects_unknown_run_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="run mode"):
        _create_batch(BatchStore(tmp_path), tmp_path, mode="automatic")


def test_batch_aggregates_all_terminal_task_states(tmp_path: Path) -> None:
    store = BatchStore(tmp_path)
    _create_batch(store, tmp_path)

    aggregate = store.aggregate(
        "batch-1",
        {"job-1": "succeeded", "job-2": "failed", "job-3": "skipped"},
    )

    assert aggregate.status == "failed"
    assert aggregate.completed_count == 3
    assert aggregate.succeeded_count == 1
    assert aggregate.failed_count == 1
    assert aggregate.skipped_count == 1
    assert aggregate.finished_at is not None


def test_batch_remains_running_while_any_task_is_nonterminal(tmp_path: Path) -> None:
    store = BatchStore(tmp_path)
    _create_batch(store, tmp_path)

    aggregate = store.aggregate(
        "batch-1",
        {"job-1": "succeeded", "job-2": "running", "job-3": "queued"},
    )

    assert aggregate.status == "running"
    assert aggregate.completed_count == 1
    assert aggregate.finished_at is None


def test_batch_json_write_is_durable_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    store = BatchStore(tmp_path)

    _create_batch(store, tmp_path)

    payload = (tmp_path / "batches" / "batch-1.json").read_text(encoding="utf-8")
    assert '"id": "batch-1"' in payload
    assert list((tmp_path / "batches").glob("*.tmp")) == []
