from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import threading
import uuid
from collections import deque
from pathlib import Path
from typing import TextIO

from local_transcriber.batches import BatchStore
from local_transcriber.executor import ExecutorOptions
from local_transcriber.ipc import UnixIPCServer, socket_path
from local_transcriber.jobs import JobStore
from local_transcriber.scheduler import BoundedScheduler


class ManagerAlreadyRunning(RuntimeError):
    pass


class BackgroundManager:
    def __init__(self, runtime_dir: Path, *, recover: bool = True) -> None:
        self.runtime_dir = runtime_dir
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.runtime_dir, 0o700)
        self._lock: TextIO = (runtime_dir / "manager.lock").open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._lock.close()
            raise ManagerAlreadyRunning("background manager already owns this runtime") from exc
        self._server = UnixIPCServer(runtime_dir, self.handle)
        self._stopping = threading.Event()
        self._workers: set[threading.Thread] = set()
        self._queue: deque[tuple[str, dict[str, object]]] = deque()
        self._queue_lock = threading.Lock()
        self._active = False
        self._current_batch_id: str | None = None
        self._scheduler = BoundedScheduler(self.runtime_dir)
        if recover:
            self._recover()

    def _start_batch(self, batch_id: str) -> None:
        batch = BatchStore(self.runtime_dir, create=False).load(batch_id)
        options = dict(batch.execution_options or {})
        with self._queue_lock:
            if self._current_batch_id == batch_id or any(
                item[0] == batch_id for item in self._queue
            ):
                return
            self._queue.append((batch_id, options))
            if self._active:
                return
            self._active = True
        worker = threading.Thread(
            target=self._drain_queue,
            name="background-batch-queue",
            daemon=False,
        )
        self._workers.add(worker)
        worker.start()

    def _drain_queue(self) -> None:
        try:
            while True:
                with self._queue_lock:
                    if not self._queue:
                        self._active = False
                        self._current_batch_id = None
                        return
                    batch_id, options = self._queue.popleft()
                    self._current_batch_id = batch_id
                try:
                    self._execute(batch_id, options)
                except Exception:
                    continue
                finally:
                    with self._queue_lock:
                        if self._current_batch_id == batch_id:
                            self._current_batch_id = None
        finally:
            self._workers.discard(threading.current_thread())

    def _recover(self) -> None:
        jobs = JobStore(self.runtime_dir, create=False)
        batches = BatchStore(self.runtime_dir, create=False)
        for job in jobs.list():
            if job.run_mode == "background" and job.status == "running":
                jobs.transition(job.id, "interrupted", error="background worker disappeared")
        for batch in batches.list():
            if batch.run_mode != "background":
                continue
            statuses = {task_id: jobs.load(task_id).status for task_id in batch.task_ids}
            has_queued = any(status == "queued" for status in statuses.values())
            if has_queued and batch.execution_options:
                batches.aggregate(batch.id, statuses)
                self._start_batch(batch.id)
            elif not has_queued:
                batches.aggregate(batch.id, statuses)

    def _execute(self, batch_id: str, request: dict[str, object]) -> None:
        options = ExecutorOptions(
            cache_dir=Path(str(request.get("cache_dir", "var/cache/models"))),
            threads=int(str(request.get("threads", 1))),
            speakers=(
                int(str(request["speakers"])) if request.get("speakers") is not None else None
            ),
            language=str(request.get("language", "auto")),
            keep_normalized=bool(request.get("keep_normalized", False)),
        )
        self._scheduler.run_batch(batch_id, options)

    def handle(self, request: dict[str, object]) -> dict[str, object]:
        action = request.get("action")
        if action == "ping":
            return {"ok": True, "running": True}
        if action == "stop":
            self._stopping.set()
            return {"ok": True}
        if action in {"cancel_job", "cancel_batch"}:
            return self._cancel(request, whole_batch=action == "cancel_batch")
        if action in {"retry_job", "retry_batch"}:
            return self._retry(request, whole_batch=action == "retry_batch")
        if action != "submit":
            return {"ok": False, "error": "unsupported manager action"}
        batch_id = request.get("batch_id")
        if not isinstance(batch_id, str):
            return {"ok": False, "error": "batch_id is required"}
        try:
            batch = BatchStore(self.runtime_dir, create=False).load(batch_id)
        except ValueError:
            return {"ok": False, "error": "unknown batch"}
        if batch.run_mode != "background":
            return {"ok": False, "error": "batch is not in background mode"}
        if batch.status != "queued":
            return {"ok": False, "error": "batch is not queued"}
        self._start_batch(batch_id)
        return {"ok": True, "batch_id": batch_id}

    def _cancel(self, request: dict[str, object], *, whole_batch: bool) -> dict[str, object]:
        jobs = JobStore(self.runtime_dir, create=False)
        batches = BatchStore(self.runtime_dir, create=False)
        try:
            if whole_batch:
                batch_id = str(request.get("batch_id", ""))
                task_ids = batches.load(batch_id).task_ids
            else:
                job_id = str(request.get("job_id", ""))
                job = jobs.load(job_id)
                batch_id = job.batch_id
                task_ids = (job_id,)
            for task_id in task_ids:
                current = jobs.load(task_id)
                if current.status == "queued":
                    jobs.transition(task_id, "cancelled")
                elif current.status == "running":
                    event = self._scheduler.cancel_event(task_id)
                    setter = getattr(event, "set", None)
                    if setter is not None:
                        setter()
            if batch_id:
                batch = batches.load(batch_id)
                batches.aggregate(
                    batch_id, {item: jobs.load(item).status for item in batch.task_ids}
                )
        except ValueError:
            return {"ok": False, "error": "unknown persisted item"}
        return {"ok": True, "status": "cancellation_requested"}

    def _retry(self, request: dict[str, object], *, whole_batch: bool) -> dict[str, object]:
        batches = BatchStore(self.runtime_dir, create=False)
        jobs = JobStore(self.runtime_dir, create=False)
        try:
            if whole_batch:
                original = batches.load(str(request.get("batch_id", "")))
                candidates = [jobs.load(item) for item in original.task_ids]
            else:
                source = jobs.load(str(request.get("job_id", "")))
                if not source.batch_id:
                    return {"ok": False, "error": "job has no batch"}
                original = batches.load(source.batch_id)
                candidates = [source]
        except ValueError:
            return {"ok": False, "error": "unknown persisted item"}
        retryable = [
            item for item in candidates if item.status in {"failed", "interrupted", "cancelled"}
        ]
        if not retryable:
            return {"ok": False, "error": "batch has no retryable tasks"}
        batch_id = f"batch-retry-{uuid.uuid4().hex[:12]}"
        task_ids: list[str] = []
        for source in retryable:
            task_id = f"job-retry-{uuid.uuid4().hex[:12]}"
            task_ids.append(task_id)
            jobs.create(
                task_id,
                source.input_path,
                Path(source.output_dir).parent / task_id,
                batch_id=batch_id,
                run_mode="background",
                input_order=source.input_order,
                effective_budget=original.effective_budget,
                attempt=source.attempt + 1,
                retry_of=source.id,
            )
        batches.create(
            batch_id,
            task_ids=tuple(task_ids),
            run_mode="background",
            effective_budget=original.effective_budget,
            output_dir=Path(original.output_dir),
            execution_options=original.execution_options,
            retry_of=original.id,
        )
        self._start_batch(batch_id)
        return {"ok": True, "batch_id": batch_id, "task_ids": task_ids}

    def run(self) -> None:
        while not self._stopping.is_set():
            self._server.serve_once()
        for worker in tuple(self._workers):
            worker.join()

    def close(self) -> None:
        for worker in tuple(self._workers):
            worker.join(timeout=2)
        self._server.close()
        socket_path(self.runtime_dir).unlink(missing_ok=True)
        try:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
        finally:
            self._lock.close()


def manager_status(runtime_dir: Path) -> dict[str, bool]:
    path = socket_path(runtime_dir)
    if not path.exists():
        return {"running": False}
    from local_transcriber.ipc import IPCError, UnixIPCClient

    try:
        response = UnixIPCClient(runtime_dir, timeout=0.2).request({"action": "ping"})
    except IPCError:
        return {"running": False}
    return {"running": response.get("ok") is True and response.get("running") is True}


def _service_name(runtime_dir: Path) -> str:
    import hashlib

    digest = hashlib.sha256(str(runtime_dir.resolve()).encode()).hexdigest()[:12]
    return f"local-transcriber-worker-{digest}"


def service_control(action: str, runtime_dir: Path) -> dict[str, object]:
    if action not in {"start", "status", "stop", "restart"}:
        return {"ok": False, "error": "unsupported worker action"}
    unit = _service_name(runtime_dir)
    try:
        if action == "start":
            command = [
                "systemd-run",
                "--user",
                f"--unit={unit}",
                "--collect",
                "--property=Restart=on-failure",
                "--property=CPUQuota=50%",
                "--property=MemoryHigh=80%",
                "--property=UMask=0077",
                sys.executable,
                "-m",
                "local_transcriber.daemon",
                "run",
                "--runtime-dir",
                str(runtime_dir.resolve()),
            ]
        elif action == "status":
            command = ["systemctl", "--user", "is-active", unit]
        else:
            command = ["systemctl", "--user", action, unit]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return {"ok": False, "running": False, "error": "user systemd is not available"}
    if action == "status":
        return {"ok": result.returncode == 0, "running": result.stdout.strip() == "active"}
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip() or "user systemd command failed"}
    return {"ok": True}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m local_transcriber.daemon")
    parser.add_argument("command", choices=("run",))
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    manager = BackgroundManager(args.runtime_dir)
    try:
        manager.run()
    finally:
        manager.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
