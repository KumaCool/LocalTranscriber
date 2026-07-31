#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_MODULES = frozenset(path.name for path in (ROOT / "src" / "local_transcriber").glob("*.py"))
REQUIRED_ARCHIVE_FILES = {
    "wheel": frozenset({"LICENSE", "README.md", "CHANGELOG.md", "local_transcriber/cli.py"}),
    "sdist": frozenset({"LICENSE", "README.md", "CHANGELOG.md", "local_transcriber/cli.py"}),
}


def run(arguments: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        arguments, cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    if result.returncode:
        command = " ".join(arguments)
        output = f"{result.stdout}{result.stderr}"
        raise RuntimeError(f"command failed ({result.returncode}): {command}\n{output}")
    return result.stdout


def archive_names(path: Path) -> set[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return set(archive.namelist())
    with tarfile.open(path, "r:gz") as archive:
        return set(archive.getnames())


def require_archive_files(path: Path, kind: str) -> None:
    names = archive_names(path)
    if kind == "wheel":
        normalized = names
        package_prefix = "local_transcriber/"
    else:
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            raise RuntimeError(f"{path.name} must have exactly one sdist root")
        root = next(iter(roots))
        normalized = {
            name.removeprefix(f"{root}/").removeprefix("src/")
            for name in names
            if name.startswith(f"{root}/")
        }
        package_prefix = "local_transcriber/"
    missing = [required for required in REQUIRED_ARCHIVE_FILES[kind] if required not in normalized]
    missing.extend(
        f"{package_prefix}{module}"
        for module in PACKAGE_MODULES
        if f"{package_prefix}{module}" not in normalized
    )
    if missing:
        raise RuntimeError(f"{path.name} is missing required files: {', '.join(missing)}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_clean_install(wheel: Path, version: str) -> None:
    with tempfile.TemporaryDirectory(prefix="local-transcriber-release-") as raw:
        venv = Path(raw) / "venv"
        run(["uv", "venv", "--python", "3.11", str(venv)])
        python = venv / "bin" / "python"
        cli = venv / "bin" / "local-transcriber"
        run(["uv", "pip", "install", "--python", str(python), str(wheel)])
        if run([str(cli), "--version"]).strip() != f"local-transcriber {version}":
            raise RuntimeError("installed CLI version does not match release")
        help_text = run([str(cli), "--help"])
        if "transcribe-dir" not in help_text or "worker" not in help_text:
            raise RuntimeError("installed CLI help is incomplete")
        probe = run(
            [
                str(python),
                "-c",
                "import importlib.metadata as m; print(m.version('local-transcriber'))",
            ]
        ).strip()
        if probe != version:
            raise RuntimeError("installed package metadata does not match release")


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_release import git_tags, package_version, validate

    try:
        version = validate(package_version(), False, git_tags())
        with tempfile.TemporaryDirectory(prefix="local-transcriber-build-") as raw_build:
            dist = Path(raw_build)
            run(["uv", "build", "--out-dir", str(dist)])
            wheels = list(dist.glob("*.whl"))
            sdists = list(dist.glob("*.tar.gz"))
            if len(wheels) != 1 or len(sdists) != 1:
                raise RuntimeError("build must produce exactly one wheel and one sdist")
            require_archive_files(wheels[0], "wheel")
            require_archive_files(sdists[0], "sdist")
            verify_clean_install(wheels[0], version)
            release_dist = ROOT / "dist"
            release_dist.mkdir(exist_ok=True)
            artifacts = []
            for path in (wheels[0], sdists[0]):
                destination = release_dist / path.name
                temporary = destination.with_suffix(destination.suffix + ".tmp")
                shutil.copyfile(path, temporary)
                temporary.replace(destination)
                artifacts.append(destination)
            payload = {
                "version": version,
                "artifacts": [
                    {"path": path.name, "sha256": sha256(path), "size_bytes": path.stat().st_size}
                    for path in artifacts
                ],
            }
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"release verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
