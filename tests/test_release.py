from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_changelog_has_unreleased_and_descending_unique_releases() -> None:
    release = _load_script("check_release.py")
    document = release.parse_changelog(ROOT / "CHANGELOG.md")

    assert document.has_unreleased
    assert document.versions == ("0.2.1", "0.2.0", "0.1.0")
    assert len(document.versions) == len(set(document.versions))


def test_release_checker_accepts_current_release_and_rejects_existing_tag(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    command = [
        sys.executable,
        "scripts/check_release.py",
        "--release",
        "0.2.1",
        "--remote",
        str(remote),
    ]
    accepted = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert accepted.returncode == 0, accepted.stderr

    rejected = subprocess.run(
        [*command, "--existing-tag", "v0.2.1"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode != 0
    assert "already exists" in rejected.stderr


def test_release_checker_accepts_development_changelog() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_release.py", "--allow-unreleased"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_changelog_rejects_duplicate_unreleased_and_future_release(tmp_path: Path) -> None:
    release = _load_script("check_release.py")
    duplicate = tmp_path / "duplicate.md"
    duplicate.write_text(
        "## [Unreleased]\n\n## [Unreleased]\n\n## [0.2.0] - 2026-08-01\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly one"):
        release.parse_changelog(duplicate)

    dated_unreleased = tmp_path / "dated-unreleased.md"
    dated_unreleased.write_text(
        "## [Unreleased] - 2026-08-01\n\n## [0.2.0] - 2026-08-01\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="undated"):
        release.parse_changelog(dated_unreleased)

    future = tmp_path / "future.md"
    future.write_text("## [Unreleased]\n\n## [0.2.0] - 2999-01-01\n", encoding="utf-8")
    with pytest.raises(ValueError, match="future"):
        release.parse_changelog(future)


@pytest.mark.parametrize("archive_kind", ["wheel", "sdist"])
def test_release_archive_requirements_are_declared(archive_kind: str) -> None:
    verifier = _load_script("verify_release.py")
    required = verifier.REQUIRED_ARCHIVE_FILES[archive_kind]

    assert "LICENSE" in required
    assert "README.md" in required
    assert "CHANGELOG.md" in required
    assert "local_transcriber/cli.py" in required


def test_archive_check_rejects_suffix_lookalikes_and_incomplete_package(tmp_path: Path) -> None:
    verifier = _load_script("verify_release.py")
    wheel = tmp_path / "fake.whl"
    import zipfile

    with zipfile.ZipFile(wheel, "w") as archive:
        for name in (
            "fake/LICENSE",
            "fake/README.md",
            "fake/CHANGELOG.md",
            "x/local_transcriber/cli.py",
        ):
            archive.writestr(name, "x")
    with pytest.raises(RuntimeError):
        verifier.require_archive_files(wheel, "wheel")

    sdist = tmp_path / "fake.tar.gz"
    import io
    import tarfile

    with tarfile.open(sdist, "w:gz") as archive:
        for name in (
            "fake/src/LICENSE",
            "fake/src/README.md",
            "fake/src/CHANGELOG.md",
            *(f"fake/src/local_transcriber/{module}" for module in verifier.PACKAGE_MODULES),
        ):
            info = tarfile.TarInfo(name)
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(RuntimeError):
        verifier.require_archive_files(sdist, "sdist")
