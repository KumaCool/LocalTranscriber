from __future__ import annotations

import tomllib
from pathlib import Path


def test_intel_macos_compatibility_dependencies_remain_pinned() -> None:
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    dependencies = set(project["project"]["dependencies"])
    marker = "; sys_platform == 'darwin' and platform_machine == 'x86_64'"

    assert {
        f"cryptography==46.0.3{marker}",
        f"llvmlite==0.45.1{marker}",
        f"numba==0.62.1{marker}",
        f"numpy==1.26.4{marker}",
        f"torch==2.2.2{marker}",
        f"torchaudio==2.2.2{marker}",
        f"transformers==4.46.3{marker}",
    } <= dependencies
