from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from local_transcriber.batches import BatchStore
from local_transcriber.daemon import (
    BackgroundManager,
    ManagerAlreadyRunning,
    manager_status,
    service_control,
)
from local_transcriber.executor import ExecutionOutcome
from local_transcriber.ipc import UnixIPCClient
from local_transcriber.jobs import JobStore
from local_transcriber.scheduler import SchedulerReport


def _persist_background_batch(runtime: Path, output: Path) -> None:
    budget = {
        "effective_workers": 1,
        "threads_per_worker": 1,
        "cpu_thread_limit": 1,
        "cpu_limit_percent": 50,
        "memory_budget_bytes": 1,
    }
    JobStore(runtime).create(
        "job-1",
        "/private/meeting.wav",
        output,
        batch_id="batch-1",
        run_mode="background",
        effective_budget=budget,
    )
    BatchStore(runtime).create(
        "batch-1",
        task_ids=("job-1",),
        run_mode="background",
        effective_budget=budget,
        output_dir=output,
    )


def test_manager_acknowledges_before_shared_scheduler_runs(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    _persist_background_batch(runtime, tmp_path / "out")
    release = threading.Event()
    started = threading.Event()

    def run_batch(self, batch_id, options, *, progress_callback=None):
        started.set()
        release.wait(timeout=2)
        jobs = JobStore(self.runtime_dir)
        jobs.transition("job-1", "running")
        jobs.transition("job-1", "succeeded")
        BatchStore(self.runtime_dir).aggregate(batch_id, {"job-1": "succeeded"})
        return SchedulerReport(
            batch_id,
            "succeeded",
            {"job-1": ExecutionOutcome("job-1", "succeeded", 0)},
            1,
            1,
        )

    monkeypatch.setattr("local_transcriber.daemon.BoundedScheduler.run_batch", run_batch)
    manager = BackgroundManager(runtime)
    thread = threading.Thread(target=manager.run)
    thread.start()
    try:
        response = UnixIPCClient(runtime).request({"action": "submit", "batch_id": "batch-1"})
        assert response == {"ok": True, "batch_id": "batch-1"}
        assert started.wait(timeout=1)
        assert BatchStore(runtime).load("batch-1").run_mode == "background"
        release.set()
        assert UnixIPCClient(runtime).request({"action": "stop"})["ok"] is True
    finally:
        release.set()
        thread.join(timeout=2)
        manager.close()

    assert JobStore(runtime).load("job-1").status == "succeeded"


def test_manager_rejects_unknown_or_foreground_batch_without_leaking_paths(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    manager = BackgroundManager(runtime)

    unknown = manager.handle({"action": "submit", "batch_id": "missing"})
    assert unknown["ok"] is False
    assert "/private/" not in json.dumps(unknown)

    _persist_background_batch(runtime, tmp_path / "out")
    payload = json.loads((runtime / "batches" / "batch-1.json").read_text())
    payload["run_mode"] = "foreground"
    (runtime / "batches" / "batch-1.json").write_text(json.dumps(payload))
    foreground = manager.handle({"action": "submit", "batch_id": "batch-1"})
    assert foreground["ok"] is False
    assert "background" in str(foreground["error"])
    manager.close()


def test_same_runtime_allows_only_one_manager(tmp_path: Path) -> None:
    first = BackgroundManager(tmp_path)
    try:
        with pytest.raises(ManagerAlreadyRunning):
            BackgroundManager(tmp_path)
    finally:
        first.close()


def test_manager_status_is_read_only_and_reports_socket_availability(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert manager_status(missing) == {"running": False}
    assert not missing.exists()


def test_service_control_uses_user_systemd_not_shell_background(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[list[str]] = []

    def run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = "active\n"
            stderr = ""

        return Result()

    monkeypatch.setattr("local_transcriber.daemon.subprocess.run", run)
    runtime = tmp_path / "runtime with spaces"

    assert service_control("start", runtime) == {"ok": True}
    assert calls[0][0:2] == ["systemd-run", "--user"]
    assert calls[0][-3:] == ["run", "--runtime-dir", str(runtime.resolve())]
    assert all("nohup" not in argument and argument != "&" for argument in calls[0])


def test_service_control_status_is_read_only_when_systemd_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    def unavailable(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("local_transcriber.daemon.subprocess.run", unavailable)
    assert service_control("status", tmp_path) == {
        "ok": False,
        "running": False,
        "error": "user systemd is not available",
    }
