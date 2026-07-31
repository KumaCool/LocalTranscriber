from __future__ import annotations

import json
from pathlib import Path

from local_transcriber.batches import BatchStore
from local_transcriber.cli import main
from local_transcriber.daemon import BackgroundManager
from local_transcriber.jobs import JobStore

BUDGET = {"effective_workers": 1, "threads_per_worker": 1}


def _persist(runtime: Path, status: str = "queued") -> None:
    jobs = JobStore(runtime)
    jobs.create(
        "job-1",
        "/private/meeting.wav",
        runtime / "private-output",
        batch_id="batch-1",
        run_mode="background",
        effective_budget=BUDGET,
    )
    if status == "running":
        jobs.transition("job-1", "running")
    elif status != "queued":
        if status in {"succeeded", "interrupted"}:
            jobs.transition("job-1", "running")
        jobs.transition("job-1", status)
    BatchStore(runtime).create(
        "batch-1",
        task_ids=("job-1",),
        run_mode="background",
        effective_budget=BUDGET,
        output_dir=runtime / "private-output",
    )
    BatchStore(runtime).aggregate("batch-1", {"job-1": jobs.load("job-1").status})


def test_batch_status_is_read_only_machine_readable_and_redacted(tmp_path: Path, capsys) -> None:
    _persist(tmp_path)
    assert main(["batch", "status", "batch-1", "--runtime-dir", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == "batch-1"
    assert payload["status"] == "running"
    assert "output_dir" not in payload
    assert "execution_options" not in payload
    assert "/private/" not in json.dumps(payload)


def test_job_cancel_uses_ipc_and_manager_cancel_is_idempotent(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _persist(tmp_path)
    manager = BackgroundManager(tmp_path, recover=False)
    monkeypatch.setattr(
        "local_transcriber.cli.UnixIPCClient.request", lambda self, request: manager.handle(request)
    )
    try:
        args = ["job", "cancel", "job-1", "--runtime-dir", str(tmp_path), "--json"]
        assert main(args) == 0
        assert json.loads(capsys.readouterr().out)["ok"] is True
        assert JobStore(tmp_path).load("job-1").status == "cancelled"
        assert main(args) == 0
        assert json.loads(capsys.readouterr().out)["ok"] is True
    finally:
        manager.close()


def test_control_never_reports_success_when_manager_is_unavailable(tmp_path: Path, capsys) -> None:
    _persist(tmp_path, "failed")
    assert main(["batch", "retry", "batch-1", "--runtime-dir", str(tmp_path)]) == 4
    assert "manager action failed" in capsys.readouterr().err
