from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import psutil

from local_transcriber.config import ResourceConfig
from local_transcriber.resources import ResourceSnapshot, calculate_budget


def _tool(name: str) -> dict[str, object]:
    path = shutil.which(name)
    if path is None:
        return {"available": False, "path": None, "version": None}
    completed = subprocess.run(
        [path, "-version"], capture_output=True, text=True, check=False, timeout=10
    )
    first_line = (completed.stdout or completed.stderr).splitlines()[0]
    return {"available": completed.returncode == 0, "path": path, "version": first_line}


def _cpu_flags() -> list[str]:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return []
    for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lower().startswith("flags"):
            return sorted(set(line.partition(":")[2].split()))
    return []


def collect_environment(path: Path | None = None) -> dict[str, object]:
    target = path or Path.cwd()
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = shutil.disk_usage(target)
    resource_snapshot = ResourceSnapshot(
        logical_cpu=psutil.cpu_count(logical=True) or 1,
        available_memory_bytes=memory.available,
        total_memory_bytes=memory.total,
    )
    # The measured Phase C peak was below this conservative scheduling allowance.
    budget = calculate_budget(
        ResourceConfig(), resource_snapshot, worker_peak_rss_bytes=3 * 1024**3
    )
    return {
        "schema_version": "1.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "host": {"hostname": platform.node(), "platform": platform.platform()},
        "cpu": {
            "architecture": platform.machine(),
            "logical_count": psutil.cpu_count(logical=True),
            "physical_count": psutil.cpu_count(logical=False),
            "flags": _cpu_flags(),
        },
        "memory": {
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "swap_total_bytes": swap.total,
            "swap_free_bytes": swap.free,
        },
        "disk": {"path": str(target.resolve()), "total_bytes": disk.total, "free_bytes": disk.free},
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "tools": {"ffmpeg": _tool("ffmpeg"), "ffprobe": _tool("ffprobe")},
        "accelerator": {"device": "cpu", "nvidia_smi": shutil.which("nvidia-smi")},
        "policy": {
            "worker_count": 1,
            "benchmark_threads": [2, 3],
            "resource_budget": budget.to_dict(),
        },
    }


def write_environment_report(destination: Path) -> dict[str, object]:
    report = collect_environment(destination.parent)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
