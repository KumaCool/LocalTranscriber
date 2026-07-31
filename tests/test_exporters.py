from __future__ import annotations

import re
from pathlib import Path

from test_schema import valid_result

from local_transcriber.exporters import export_result, render_markdown, render_srt, render_text


def test_exporters_render_golden_content() -> None:
    result = valid_result()

    assert "SPEAKER_00" in render_markdown(result)
    assert "00:00:00.010 - 00:00:00.500" in render_text(result)
    assert render_srt(result) == "1\n00:00:00,010 --> 00:00:00,500\n[SPEAKER_00] 你好\n"


def test_export_result_reads_canonical_json(tmp_path: Path) -> None:
    from local_transcriber.schema import write_result

    source = tmp_path / "result.json"
    destination = tmp_path / "transcript.srt"
    write_result(source, valid_result())

    export_result(source, destination, "srt")

    content = destination.read_text(encoding="utf-8")
    blocks = content.strip().split("\n\n")
    previous_end = -1
    for expected_number, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        assert int(lines[0]) == expected_number
        match = re.fullmatch(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})",
            lines[1],
        )
        assert match
        values = [int(value) for value in match.groups()]
        start = ((values[0] * 60 + values[1]) * 60 + values[2]) * 1000 + values[3]
        end = ((values[4] * 60 + values[5]) * 60 + values[6]) * 1000 + values[7]
        assert start >= previous_end
        assert end > start
        previous_end = end
