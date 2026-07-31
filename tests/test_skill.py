from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
SKILL_PATH = PROJECT_ROOT / ".hermes/skills/local-speaker-transcription/SKILL.md"


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_local_speaker_transcription_skill_has_valid_frontmatter() -> None:
    text = _skill_text()
    assert text.startswith("---\n")
    closing = text.find("\n---\n", 4)
    assert closing > 4
    frontmatter = text[4:closing]
    assert re.search(r"^name: local-speaker-transcription$", frontmatter, re.MULTILINE)
    description = re.search(r'^description: "([^"]+)"$', frontmatter, re.MULTILINE)
    assert description is not None
    assert description.group(1).startswith("Use when ")
    assert len(description.group(1)) <= 1024
    assert text[closing + 5 :].strip()


def test_local_speaker_transcription_skill_pins_verified_safe_contract() -> None:
    text = _skill_text()
    required_contracts = (
        "${LOCALTRANSCRIBER_ROOT}",
        "uv run local-transcriber transcribe",
        "--threads 2",
        "--language auto",
        "var/cache/models",
        "var/work/hermes",
        "var/output/hermes",
        "result.json",
        "transcript.md",
        "transcript.txt",
        "transcript.srt",
        "media.json",
        "succeeded",
        "SPEAKER_",
        "MEDIA:",
        "background=true",
        "notify_on_complete=true",
        "exit code 130",
        "single worker",
        "estimated completion",
        "local-transcriber job status",
        "--json",
        "engineering estimate",
        "Do not poll in a tight loop",
    )
    for contract in required_contracts:
        assert contract in text


def test_local_speaker_transcription_skill_documents_privacy_and_limits() -> None:
    text = _skill_text()
    required_limits = (
        "anonymous",
        "not identity recognition",
        "segment timestamps",
        "not word-level",
        "Do not upload",
        "Do not expose an HTTP service",
        "overlapping speech",
        "manual review",
    )
    for limit in required_limits:
        assert limit in text
