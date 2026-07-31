from __future__ import annotations

from pathlib import Path

import pytest

from local_transcriber.config import ResourceConfig, load_resource_config


def test_resource_config_defaults_to_half_cpu_budget() -> None:
    config = ResourceConfig()

    assert config.cpu_limit_percent == 50
    assert config.memory_limit_percent == 70
    assert config.max_workers == 1
    assert config.threads_per_worker == 2
    assert config.nice == 10


@pytest.mark.parametrize("value", [9, 51])
def test_resource_config_rejects_cpu_limit_outside_safe_range(value: int) -> None:
    with pytest.raises(ValueError, match="cpu_limit_percent"):
        ResourceConfig(cpu_limit_percent=value)


def test_cli_overrides_project_config_and_project_overrides_defaults(tmp_path: Path) -> None:
    path = tmp_path / "local-transcriber.toml"
    path.write_text(
        """[resources]
cpu_limit_percent = 30
memory_limit_percent = 60
max_workers = 3
threads_per_worker = 1
nice = 15
""",
        encoding="utf-8",
    )

    config = load_resource_config(path, {"cpu_limit_percent": 20, "max_workers": 2})

    assert config == ResourceConfig(
        cpu_limit_percent=20,
        memory_limit_percent=60,
        max_workers=2,
        threads_per_worker=1,
        nice=15,
    )


def test_project_config_cannot_raise_cpu_limit_above_safety_ceiling(tmp_path: Path) -> None:
    path = tmp_path / "local-transcriber.toml"
    path.write_text("[resources]\ncpu_limit_percent = 75\n", encoding="utf-8")

    with pytest.raises(ValueError, match="cpu_limit_percent"):
        load_resource_config(path)
