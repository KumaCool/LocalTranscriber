from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import TextIO

from local_transcriber.batches import BatchStore
from local_transcriber.executor import ExecutorOptions
from local_transcriber.ipc import UnixIPCServer, socket_path
from local_transcriber.scheduler import BoundedScheduler


class ManagerAlreadyRunning(RuntimeError):
    pass


class BackgroundManager:
    def __init__(self, runtime_dir: Path) -> None:
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

    def _execute(self, batch_id: str, request: dict[str, object]) -> None:
        try:
            options = ExecutorOptions(
                cache_dir=Path(str(request.get("cache_dir", "var/cache/models"))),
                threads=int(request.get("threads", 1)),
                speakers=(
                    int(str(request["speakers"])) if request.get("speakers") is not None else None
                ),
                language=str(request.get("language", "auto")),
                keep_normalized=bool(request.get("keep_normalized", False)),
            )
            BoundedScheduler(self.runtime_dir).run_batch(batch_id, options)
        finally:
            self._workers.discard(threading.current_thread())

    def handle(self, request: dict[str, object]) -> dict[str, object]:
        action = request.get("action")
        if action == "ping":
            return {"ok": True, "running": True}
        if action == "stop":
            self._stopping.set()
            return {"ok": True}
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
        worker = threading.Thread(
            target=self._execute,
            args=(batch_id, request),
            name=f"batch-{batch_id}",
            daemon=False,
        )
        self._workers.add(worker)
        worker.start()
        return {"ok": True, "batch_id": batch_id}

    def run(self) -> None:
        while not self._stopping.is_set():
            self._server.serve_once()
        for worker in tuple(self._workers):
            worker.join()

    def close(self) -> None:
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
