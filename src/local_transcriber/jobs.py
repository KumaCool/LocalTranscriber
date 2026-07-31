from __future__ import annotations

import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO


class JobBusyError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredJob:
    id: str
    input_path: str
    output_dir: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None


_TRANSITIONS = {
    "queued": {"running", "failed", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.jobs_dir = root / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        if not job_id or "/" in job_id or "\\" in job_id:
            raise ValueError("invalid job id")
        return self.jobs_dir / f"{job_id}.json"

    def _write(self, job: StoredJob) -> None:
        path = self._path(job.id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(job), ensure_ascii=False, indent=2) + "\n")
        temporary.replace(path)

    def create(self, job_id: str, input_path: str, output_dir: Path) -> StoredJob:
        path = self._path(job_id)
        if path.exists():
            raise ValueError(f"job already exists: {job_id}")
        job = StoredJob(
            id=job_id,
            input_path=input_path,
            output_dir=str(output_dir),
            status="queued",
            created_at=_now(),
        )
        self._write(job)
        return job

    def load(self, job_id: str) -> StoredJob:
        try:
            return StoredJob(**json.loads(self._path(job_id).read_text(encoding="utf-8")))
        except FileNotFoundError as exc:
            raise ValueError(f"unknown job: {job_id}") from exc

    def transition(self, job_id: str, status: str, error: str | None = None) -> StoredJob:
        current = self.load(job_id)
        if status not in _TRANSITIONS[current.status]:
            raise ValueError(f"invalid job transition: {current.status} -> {status}")
        values = asdict(current)
        values["status"] = status
        if status == "running":
            values["started_at"] = _now()
        if status in {"succeeded", "failed", "cancelled"}:
            values["finished_at"] = _now()
        values["error"] = error
        updated = StoredJob(**values)
        self._write(updated)
        return updated

    @contextmanager
    def worker(self, job_id: str) -> Iterator[None]:
        lock_path = self.root / "worker.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle: TextIO = lock_path.open("a+", encoding="utf-8")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise JobBusyError("another transcription job is already running") from exc
            handle.seek(0)
            handle.truncate()
            handle.write(job_id)
            handle.flush()
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
