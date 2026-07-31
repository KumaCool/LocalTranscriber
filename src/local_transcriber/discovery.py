from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from local_transcriber.media import MediaError, MediaInfo, probe_media

SUPPORTED_MEDIA_EXTENSIONS = frozenset(
    {
        ".aac",
        ".flac",
        ".m4a",
        ".mkv",
        ".mov",
        ".mp3",
        ".mp4",
        ".ogg",
        ".opus",
        ".wav",
        ".webm",
        ".wma",
    }
)
EXCLUDED_DIRECTORY_NAMES = frozenset({"runtime", "output", "cache", "work", "state"})


@dataclass(frozen=True)
class DiscoveredInput:
    path: Path
    relative_path: Path
    input_order: int
    size_bytes: int
    sha256: str
    media: MediaInfo


@dataclass(frozen=True)
class SkippedInput:
    path: Path
    reason: str
    detail: str | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    accepted: tuple[DiscoveredInput, ...]
    skipped: tuple[SkippedInput, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect(
    candidates: Iterable[tuple[Path, Path]],
    *,
    initial_skipped: Iterable[SkippedInput] = (),
) -> DiscoveryResult:
    accepted: list[DiscoveredInput] = []
    skipped = list(initial_skipped)
    seen_paths: set[Path] = set()
    seen_content: set[tuple[int, str]] = set()
    for candidate, relative_path in candidates:
        if candidate.is_symlink():
            skipped.append(SkippedInput(candidate.absolute(), "symlink"))
            continue
        resolved = candidate.resolve()
        if resolved in seen_paths:
            skipped.append(SkippedInput(resolved, "duplicate_path"))
            continue
        seen_paths.add(resolved)
        if candidate.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
            skipped.append(SkippedInput(resolved, "unsupported_extension"))
            continue
        try:
            size = candidate.stat().st_size
            content_hash = _sha256(candidate)
            media = probe_media(candidate)
        except (MediaError, OSError) as exc:
            skipped.append(SkippedInput(resolved, "invalid_media", str(exc)))
            continue
        identity = (size, content_hash)
        if identity in seen_content:
            skipped.append(SkippedInput(resolved, "duplicate_content"))
            continue
        seen_content.add(identity)
        accepted.append(
            DiscoveredInput(
                path=resolved,
                relative_path=relative_path,
                input_order=len(accepted),
                size_bytes=size,
                sha256=content_hash,
                media=media,
            )
        )
    return DiscoveryResult(tuple(accepted), tuple(skipped))


def discover_explicit(paths: Iterable[Path]) -> DiscoveryResult:
    return _inspect((path, Path(path.name)) for path in paths)


def discover_directory(
    root: Path,
    *,
    recursive: bool = False,
    excluded_roots: Iterable[Path] = (),
) -> DiscoveryResult:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"input directory does not exist or is unsafe: {root}")
    resolved_root = root.resolve()
    exclusions = {path.resolve() for path in excluded_roots}
    candidates: list[tuple[Path, Path]] = []
    skipped: list[SkippedInput] = []
    for current, directories, files in os.walk(resolved_root, followlinks=False):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(directories):
            child = current_path / name
            if child.is_symlink():
                skipped.append(SkippedInput(child.absolute(), "symlink"))
            elif child.resolve() in exclusions or name.casefold() in EXCLUDED_DIRECTORY_NAMES:
                skipped.append(SkippedInput(child.resolve(), "excluded_directory"))
            elif recursive:
                kept_directories.append(name)
        directories[:] = kept_directories
        for name in sorted(files):
            path = current_path / name
            candidates.append((path, path.relative_to(resolved_root)))
        if not recursive:
            break
    candidates.sort(key=lambda item: item[1].as_posix())
    return _inspect(candidates, initial_skipped=skipped)


def output_path_for(output_root: Path, item: DiscoveredInput, task_id: str) -> Path:
    relative_parent = item.relative_path.parent
    return output_root / relative_parent / f"{item.relative_path.stem}-{task_id}"
