from __future__ import annotations

import json

from local_transcriber.environment import collect_environment, write_environment_report


def test_collect_environment_records_required_runtime_boundaries() -> None:
    report = collect_environment()

    assert report["cpu"]["logical_count"] >= 1
    assert isinstance(report["cpu"]["flags"], list)
    assert report["memory"]["total_bytes"] > 0
    assert report["memory"]["available_bytes"] > 0
    assert report["disk"]["free_bytes"] > 0
    assert report["python"]["version"]
    assert report["tools"]["ffmpeg"]["available"] is True
    assert report["tools"]["ffprobe"]["available"] is True
    assert report["accelerator"]["device"] == "cpu"
    assert report["policy"]["worker_count"] == 1
    assert report["policy"]["benchmark_threads"] == [2, 3]


def test_write_environment_report_can_be_read_back(tmp_path) -> None:
    destination = tmp_path / "environment.json"

    write_environment_report(destination)

    loaded = json.loads(destination.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "1.0"
    assert loaded["policy"]["worker_count"] == 1
