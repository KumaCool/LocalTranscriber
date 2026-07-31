from __future__ import annotations

from pathlib import Path

from local_transcriber.schema import CanonicalResult, read_result


def _clock(milliseconds: int, separator: str = ".") -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def render_markdown(result: CanonicalResult) -> str:
    lines = ["# Transcript", ""]
    for segment in result.segments:
        lines.extend(
            [
                f"**{_clock(segment.start_ms)} – {_clock(segment.end_ms)} · {segment.speaker}**",
                "",
                segment.text,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_text(result: CanonicalResult) -> str:
    return "".join(
        f"[{_clock(segment.start_ms)} - {_clock(segment.end_ms)}] "
        f"{segment.speaker}: {segment.text}\n"
        for segment in result.segments
    )


def render_srt(result: CanonicalResult) -> str:
    blocks = []
    for index, segment in enumerate(result.segments, start=1):
        blocks.append(
            f"{index}\n{_clock(segment.start_ms, ',')} --> {_clock(segment.end_ms, ',')}\n"
            f"[{segment.speaker}] {segment.text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def export_result(source: Path, destination: Path, format_name: str) -> None:
    result = read_result(source)
    renderers = {"md": render_markdown, "txt": render_text, "srt": render_srt}
    try:
        content = renderers[format_name](result)
    except KeyError as exc:
        raise ValueError(f"unsupported export format: {format_name}") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
