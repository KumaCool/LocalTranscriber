from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResourceConfig:
    cpu_limit_percent: int = 50
    memory_limit_percent: int = 70
    max_workers: int = 1
    threads_per_worker: int = 2
    nice: int = 10

    def __post_init__(self) -> None:
        if not 10 <= self.cpu_limit_percent <= 50:
            raise ValueError("cpu_limit_percent must be between 10 and 50")
        if not 10 <= self.memory_limit_percent <= 90:
            raise ValueError("memory_limit_percent must be between 10 and 90")
        if self.max_workers < 1:
            raise ValueError("max_workers must be positive")
        if self.threads_per_worker < 1:
            raise ValueError("threads_per_worker must be positive")
        if not 0 <= self.nice <= 19:
            raise ValueError("nice must be between 0 and 19")


def load_resource_config(
    path: Path | None = None, overrides: Mapping[str, Any] | None = None
) -> ResourceConfig:
    values: dict[str, Any] = {}
    if path is not None and path.exists():
        with path.open("rb") as handle:
            document = tomllib.load(handle)
        resources = document.get("resources", {})
        if not isinstance(resources, dict):
            raise ValueError("resources configuration must be a table")
        values.update(resources)
    if overrides:
        values.update({key: value for key, value in overrides.items() if value is not None})
    supported = {field.name for field in fields(ResourceConfig)}
    unknown = sorted(set(values) - supported)
    if unknown:
        raise ValueError(f"unknown resource configuration: {', '.join(unknown)}")
    return ResourceConfig(**values)
