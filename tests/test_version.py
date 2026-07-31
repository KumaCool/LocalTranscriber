from __future__ import annotations

import importlib.metadata
import re

import pytest

from local_transcriber import __version__
from local_transcriber.cli import main


def test_runtime_metadata_and_cli_share_semantic_version(capsys) -> None:
    metadata_version = importlib.metadata.version("local-transcriber")

    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"local-transcriber {metadata_version}"
    assert __version__ == metadata_version
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", metadata_version)
