from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RUN_MODES = {"foreground", "background"}
_TERMINAL_TASK_STATUSES = {"succeeded", "failed", "cancelled", "interrupted", "skipped"}
_TASK_STATUSES = _TERMINAL_TASK_STATUSES | {"queued", "running"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class StoredBatch:
    id: str
    task_ids: tuple[str, ...]
    run_mode: str
    effective_budget: dict[str, Any]
    output_dir: str
    status: str
    created_at: str
    updated_at: str
    finished_at: str | None = None
    completed_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    interrupted_count: int = 0
    skipped_count: int = 0


class BatchStore:
    def __init__(self, root: Path, *, create: bool = True) -> None:
        self.root = root
        self.batches_dir = root / "batches"
        if create:
            self.batches_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, batch_id: str) -> Path:
        if not batch_id or "/" in batch_id or "\\" in batch_id:
            raise ValueError("invalid batch id")
        return self.batches_dir / f"{batch_id}.json"

    def _write(self, batch: StoredBatch) -> None:
        _atomic_write(self._path(batch.id), asdict(batch))

    def create(
        self,
        batch_id: str,
        *,
        task_ids: tuple[str, ...],
        run_mode: str,
        effective_budget: dict[str, Any],
        output_dir: Path,
    ) -> StoredBatch:
        if run_mode not in _RUN_MODES:
            raise ValueError(f"unsupported run mode: {run_mode}")
        if not task_ids or len(set(task_ids)) != len(task_ids):
            raise ValueError("batch task ids must be non-empty and unique")
        path = self._path(batch_id)
        if path.exists():
            raise ValueError(f"batch already exists: {batch_id}")
        now = _now()
        batch = StoredBatch(
            id=batch_id,
            task_ids=task_ids,
            run_mode=run_mode,
            effective_budget=dict(effective_budget),
            output_dir=str(output_dir),
            status="queued",
            created_at=now,
            updated_at=now,
        )
        self._write(batch)
        return batch

    def load(self, batch_id: str) -> StoredBatch:
        try:
            payload = json.loads(self._path(batch_id).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError(f"unknown batch: {batch_id}") from exc
        payload["task_ids"] = tuple(payload["task_ids"])
        return StoredBatch(**payload)

    def aggregate(self, batch_id: str, task_statuses: dict[str, str]) -> StoredBatch:
        current = self.load(batch_id)
        if set(task_statuses) != set(current.task_ids):
            raise ValueError("task statuses must exactly match the batch")
        unknown = set(task_statuses.values()) - _TASK_STATUSES
        if unknown:
            raise ValueError(f"unsupported task status: {sorted(unknown)[0]}")
        counts = {status: list(task_statuses.values()).count(status) for status in _TASK_STATUSES}
        completed = sum(counts[status] for status in _TERMINAL_TASK_STATUSES)
        all_terminal = completed == len(current.task_ids)
        if not all_terminal:
            status = "running"
        elif counts["failed"] or counts["interrupted"]:
            status = "failed"
        elif counts["cancelled"]:
            status = "cancelled"
        else:
            status = "succeeded"
        values = asdict(current)
        values.update(
            status=status,
            updated_at=_now(),
            finished_at=_now() if all_terminal else None,
            completed_count=completed,
            succeeded_count=counts["succeeded"],
            failed_count=counts["failed"],
            cancelled_count=counts["cancelled"],
            interrupted_count=counts["interrupted"],
            skipped_count=counts["skipped"],
        )
        updated = StoredBatch(**values)
        self._write(updated)
        return updated
