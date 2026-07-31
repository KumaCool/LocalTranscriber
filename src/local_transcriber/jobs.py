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
    stage: str = "probing"
    progress_percent: float = 0.0
    processed_units: float = 0.0
    total_units: float = 0.0
    eta_low_seconds: int | None = None
    eta_high_seconds: int | None = None
    eta_confidence: str = "calculating"
    updated_at: str | None = None


_TRANSITIONS = {
    "queued": {"running", "failed", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}

_STAGES = {"probing", "normalizing", "loading", "vad", "transcribing", "finalizing"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JobStore:
    def __init__(self, root: Path, *, create: bool = True) -> None:
        self.root = root
        self.jobs_dir = root / "jobs"
        if create:
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
            payload = json.loads(self._path(job_id).read_text(encoding="utf-8"))
            payload.setdefault("stage", "probing")
            payload.setdefault("progress_percent", 0.0)
            payload.setdefault("processed_units", 0.0)
            payload.setdefault("total_units", 0.0)
            payload.setdefault("eta_low_seconds", None)
            payload.setdefault("eta_high_seconds", None)
            payload.setdefault("eta_confidence", "calculating")
            payload.setdefault("updated_at", payload["created_at"])
            return StoredJob(**payload)
        except FileNotFoundError as exc:
            raise ValueError(f"unknown job: {job_id}") from exc

    def update_progress(
        self,
        job_id: str,
        *,
        stage: str,
        progress_percent: float,
        processed_units: float | None = None,
        total_units: float | None = None,
        eta_low_seconds: int | None = None,
        eta_high_seconds: int | None = None,
        eta_confidence: str | None = None,
    ) -> StoredJob:
        current = self.load(job_id)
        if current.status not in {"queued", "running"}:
            raise ValueError(f"cannot update terminal job: {current.status}")
        if stage not in _STAGES:
            raise ValueError(f"unsupported progress stage: {stage}")
        if not 0 <= progress_percent <= 99:
            raise ValueError("running progress must be between 0 and 99")
        values = asdict(current)
        values["stage"] = stage
        values["progress_percent"] = max(current.progress_percent, float(progress_percent))
        if processed_units is not None and processed_units >= current.processed_units:
            values["processed_units"] = float(processed_units)
        if total_units is not None and total_units > 0:
            values["total_units"] = max(current.total_units, float(total_units))
        if eta_low_seconds is not None:
            values["eta_low_seconds"] = max(0, int(eta_low_seconds))
        if eta_high_seconds is not None:
            values["eta_high_seconds"] = max(values["eta_low_seconds"] or 0, int(eta_high_seconds))
        if eta_confidence is not None:
            if eta_confidence not in {"calculating", "normal", "low"}:
                raise ValueError(f"unsupported ETA confidence: {eta_confidence}")
            values["eta_confidence"] = eta_confidence
        values["updated_at"] = _now()
        updated = StoredJob(**values)
        self._write(updated)
        return updated

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
        if status == "succeeded":
            values["progress_percent"] = 100.0
            values["eta_low_seconds"] = 0
            values["eta_high_seconds"] = 0
            values["eta_confidence"] = "normal"
        values["updated_at"] = _now()
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
