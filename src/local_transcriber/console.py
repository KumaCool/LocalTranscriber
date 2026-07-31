from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from local_transcriber.batches import BatchStore
from local_transcriber.jobs import JobStore, StoredJob

_TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}


class ForegroundConsole:
    def __init__(
        self,
        runtime_dir: Path,
        batch_id: str,
        *,
        stream: TextIO | None = None,
        is_tty: bool | None = None,
    ) -> None:
        self.runtime_dir = runtime_dir
        self.batch_id = batch_id
        self.stream = stream or sys.stderr
        self.is_tty = self.stream.isatty() if is_tty is None else is_tty
        self._last_line: str | None = None
        self._tty_open = False

    @staticmethod
    def _eta(job: StoredJob | None) -> str:
        if job is None or job.eta_low_seconds is None or job.eta_high_seconds is None:
            return "calculating"
        return f"{job.eta_low_seconds}-{job.eta_high_seconds}s"

    def _line(self) -> str:
        batch = BatchStore(self.runtime_dir, create=False).load(self.batch_id)
        job_store = JobStore(self.runtime_dir, create=False)
        jobs = [job_store.load(task_id) for task_id in batch.task_ids]
        running = [job for job in jobs if job.status == "running"]
        completed = sum(job.status in _TERMINAL for job in jobs)
        failed = sum(job.status in {"failed", "interrupted"} for job in jobs)
        cancelled = sum(job.status == "cancelled" for job in jobs)
        current = (
            running[0] if running else next((job for job in jobs if job.status == "queued"), None)
        )
        current_id = current.id if current is not None else "none"
        stage = current.stage if current is not None else "done"
        progress = current.progress_percent if current is not None else 100.0
        return (
            f"batch={batch.id} completed={completed}/{len(jobs)} running={len(running)} "
            f"failed={failed} cancelled={cancelled} current={current_id} stage={stage} "
            f"progress={progress:.1f}% eta={self._eta(current)}"
        )

    def refresh(self) -> None:
        line = self._line()
        if line == self._last_line:
            return
        if self.is_tty:
            self.stream.write(f"\r{line}\x1b[K")
            self._tty_open = True
        else:
            self.stream.write(line + "\n")
        self.stream.flush()
        self._last_line = line

    def finish(self) -> None:
        self.refresh()
        if self.is_tty and self._tty_open:
            self.stream.write("\n")
            self.stream.flush()
            self._tty_open = False
