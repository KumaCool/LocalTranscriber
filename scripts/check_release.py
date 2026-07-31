#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
HEADING = re.compile(
    r"^## \[(?P<version>[^]]+)](?: - (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2}))?$", re.MULTILINE
)


@dataclass(frozen=True)
class ChangelogDocument:
    has_unreleased: bool
    versions: tuple[str, ...]
    dates: tuple[str, ...]


def package_version(root: Path = ROOT) -> str:
    source = root / "src" / "local_transcriber" / "__init__.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    values = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            values.append(ast.literal_eval(node.value))
    if len(values) != 1 or not isinstance(values[0], str):
        raise ValueError("exactly one literal __version__ is required")
    if not SEMVER.fullmatch(values[0]):
        raise ValueError("package version must use MAJOR.MINOR.PATCH")
    return values[0]


def parse_changelog(path: Path) -> ChangelogDocument:
    headings = list(HEADING.finditer(path.read_text(encoding="utf-8")))
    unreleased = [match for match in headings if match.group("version") == "Unreleased"]
    if len(unreleased) != 1 or unreleased[0].group("date") is not None:
        raise ValueError("CHANGELOG must contain exactly one undated [Unreleased]")
    releases = [match for match in headings if match.group("version") != "Unreleased"]
    versions = tuple(match.group("version") for match in releases)
    dates = tuple(match.group("date") or "" for match in releases)

    if not versions or len(versions) != len(set(versions)):
        raise ValueError("CHANGELOG release versions must be non-empty and unique")
    if any(not SEMVER.fullmatch(version) for version in versions):
        raise ValueError("CHANGELOG release versions must use MAJOR.MINOR.PATCH")
    if tuple(map(_version_key, versions)) != tuple(
        sorted(map(_version_key, versions), reverse=True)
    ):
        raise ValueError("CHANGELOG releases must be ordered newest first")
    for value in dates:
        if not value:
            raise ValueError("released CHANGELOG sections require a date")
        if date.fromisoformat(value) > date.today():
            raise ValueError("CHANGELOG release date cannot be in the future")
    return ChangelogDocument(True, versions, dates)


def _version_key(value: str) -> tuple[int, int, int]:
    return tuple(map(int, value.split(".")))  # type: ignore[return-value]


def git_tags(root: Path = ROOT) -> set[str]:
    result = subprocess.run(
        ["git", "tag", "--list"], cwd=root, text=True, capture_output=True, check=True
    )
    return set(result.stdout.splitlines())


def remote_tags(remote: str, root: Path = ROOT) -> set[str]:
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs", remote],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return {line.rsplit("refs/tags/", 1)[1] for line in result.stdout.splitlines() if line}


def validate(release: str | None, allow_unreleased: bool, existing_tags: set[str]) -> str:
    version = package_version()
    changelog = parse_changelog(ROOT / "CHANGELOG.md")
    if release is not None:
        if release != version:
            raise ValueError(f"package version {version} does not match release {release}")
        if not changelog.versions or changelog.versions[0] != release:
            raise ValueError("latest CHANGELOG release does not match package version")
        tag = f"v{release}"
        if tag in existing_tags:
            raise ValueError(f"tag {tag} already exists; releases are immutable")
    elif not allow_unreleased:
        raise ValueError("choose --release VERSION or --allow-unreleased")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate release version and changelog")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--release")
    group.add_argument("--allow-unreleased", action="store_true")
    parser.add_argument("--existing-tag", action="append", default=[])
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args(argv)
    try:
        existing_tags = git_tags() | set(args.existing_tag)
        if args.release is not None:
            existing_tags |= remote_tags(args.remote)
        version = validate(args.release, args.allow_unreleased, existing_tags)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"release validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"release metadata valid: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
