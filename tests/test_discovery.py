from __future__ import annotations

import subprocess
from pathlib import Path

from local_transcriber.discovery import discover_directory, discover_explicit, output_path_for


def _audio(path: Path, *, frequency: int = 440) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration=0.05",
            str(path),
        ],
        check=True,
    )


def test_explicit_files_preserve_user_order_and_deduplicate_content(tmp_path: Path) -> None:
    first = tmp_path / "z.wav"
    second = tmp_path / "a.wav"
    duplicate = tmp_path / "copy.wav"
    _audio(first, frequency=330)
    _audio(second, frequency=550)
    duplicate.write_bytes(first.read_bytes())

    result = discover_explicit([first, second, duplicate, first])

    assert [item.path for item in result.accepted] == [first.resolve(), second.resolve()]
    assert [item.input_order for item in result.accepted] == [0, 1]
    assert [item.reason for item in result.skipped] == ["duplicate_content", "duplicate_path"]


def test_directory_is_nonrecursive_by_default_and_recursively_sorted_on_request(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input"
    top_b = source / "b.wav"
    top_a = source / "a.wav"
    nested = source / "nested" / "c.wav"
    _audio(top_b, frequency=330)
    _audio(top_a, frequency=440)
    _audio(nested, frequency=550)

    shallow = discover_directory(source)
    recursive = discover_directory(source, recursive=True)

    assert [item.relative_path.as_posix() for item in shallow.accepted] == ["a.wav", "b.wav"]
    assert [item.relative_path.as_posix() for item in recursive.accepted] == [
        "a.wav",
        "b.wav",
        "nested/c.wav",
    ]


def test_directory_prefilters_extensions_but_ffprobe_confirms_audio(tmp_path: Path) -> None:
    source = tmp_path / "input"
    valid = source / "valid.wav"
    corrupt = source / "broken.mp3"
    ignored = source / "notes.txt"
    _audio(valid)
    corrupt.write_text("not media", encoding="utf-8")
    ignored.write_text("not media", encoding="utf-8")

    result = discover_directory(source)

    assert [item.path for item in result.accepted] == [valid.resolve()]
    assert {(item.path.name, item.reason) for item in result.skipped} == {
        ("broken.mp3", "invalid_media"),
        ("notes.txt", "unsupported_extension"),
    }


def test_directory_skips_symlinks_and_excluded_runtime_trees(tmp_path: Path) -> None:
    source = tmp_path / "input"
    real = source / "real.wav"
    linked = source / "linked.wav"
    runtime_media = source / "runtime" / "old.wav"
    output_media = source / "output" / "old.wav"
    cache_media = source / "cache" / "old.wav"
    work_media = source / "work" / "old.wav"
    state_media = source / "state" / "old.wav"
    _audio(real)
    _audio(runtime_media)
    _audio(output_media)
    _audio(cache_media)
    _audio(work_media)
    _audio(state_media)
    linked.symlink_to(real)

    result = discover_directory(
        source,
        recursive=True,
        excluded_roots=[source / "runtime", source / "output"],
    )

    assert [item.path for item in result.accepted] == [real.resolve()]
    reasons = {(item.path.name, item.reason) for item in result.skipped}
    assert ("linked.wav", "symlink") in reasons
    assert ("runtime", "excluded_directory") in reasons
    assert ("output", "excluded_directory") in reasons
    assert ("cache", "excluded_directory") in reasons
    assert ("work", "excluded_directory") in reasons
    assert ("state", "excluded_directory") in reasons


def test_output_path_preserves_relative_tree_and_task_id(tmp_path: Path) -> None:
    root = tmp_path / "input"
    left = root / "left" / "same.wav"
    right = root / "right" / "same.wav"
    _audio(left, frequency=330)
    _audio(right, frequency=550)
    result = discover_directory(root, recursive=True)

    paths = [
        output_path_for(tmp_path / "out", item, f"job-{index}")
        for index, item in enumerate(result.accepted)
    ]

    assert paths == [
        tmp_path / "out" / "left" / "same-job-0",
        tmp_path / "out" / "right" / "same-job-1",
    ]
    assert len(set(paths)) == 2
