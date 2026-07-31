from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    role: str
    model_id: str
    revision: str
    cache_dirname: str
    source: str = "ModelScope"
    license: str = "Apache-2.0"


MODEL_SPECS = {
    "asr": ModelSpec(
        role="asr",
        model_id="iic/SenseVoiceSmall",
        revision="7bf452403abd7353a300cd760f7adae7701c92c1",
        cache_dirname="sensevoice-small",
    ),
    "vad": ModelSpec(
        role="vad",
        model_id="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        revision="f9a8b8274674755d925277e27063869038d41515",
        cache_dirname="fsmn-vad",
    ),
    "speaker": ModelSpec(
        role="speaker",
        model_id="iic/speech_campplus_sv_zh-cn_16k-common",
        revision="a045b2afcaa9c3049c98a9215a2bc274407ab237",
        cache_dirname="campplus",
    ),
}

_RICH_TAG = re.compile(r"<\|[^|]*\|>")


def _clean_transcript_text(text: str) -> str:
    cleaned = _RICH_TAG.sub("", text).strip()
    if not cleaned:
        return ""
    for repeats in range(4, 1, -1):
        if len(cleaned) % repeats == 0:
            unit = cleaned[: len(cleaned) // repeats]
            if len(unit) >= 4 and unit * repeats == cleaned:
                return unit.strip()
    return cleaned


def pull_models(cache_root: Path) -> list[dict[str, Any]]:
    from modelscope.hub.snapshot_download import snapshot_download

    cache_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for spec in MODEL_SPECS.values():
        destination = cache_root / spec.cache_dirname
        resolved = snapshot_download(
            spec.model_id,
            revision=spec.revision,
            local_dir=str(destination),
        )
        records.append({**asdict(spec), "path": str(Path(resolved).resolve()), "cached": True})
    return records


def write_model_manifest(destination: Path, cache_root: Path) -> dict[str, Any]:
    models = []
    for spec in MODEL_SPECS.values():
        path = (cache_root / spec.cache_dirname).resolve()
        models.append({**asdict(spec), "path": str(path), "cached": path.is_dir()})
    payload = {
        "schema_version": "1.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "models": models,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def validate_raw_result(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, list) or not result:
        raise ValueError("raw result must be a non-empty list")
    sentence_info = result[0].get("sentence_info") if isinstance(result[0], dict) else None
    if not isinstance(sentence_info, list):
        raise ValueError("raw result must contain sentence_info")
    if not sentence_info:
        raise ValueError("sentence_info must be non-empty")

    normalized = []
    for index, segment in enumerate(sentence_info):
        if not isinstance(segment, dict):
            raise ValueError(f"segment {index} must be an object")
        text = segment.get("sentence", segment.get("text"))
        if not isinstance(text, str):
            raise ValueError(f"segment {index} text must be non-empty")
        original_text = text
        text = _clean_transcript_text(text)
        if not text and original_text.strip() == "":
            raise ValueError(f"segment {index} text must be non-empty")
        if not text:
            continue
        start = segment.get("start")
        end = segment.get("end")
        if not isinstance(start, int | float) or not isinstance(end, int | float):
            raise ValueError(f"segment {index} must have numeric time range")
        if start < 0 or end <= start:
            raise ValueError(f"segment {index} has invalid time range")
        speaker = segment.get("spk")
        if speaker is None:
            raise ValueError(f"segment {index} must have speaker output")
        normalized.append(
            {
                "start_ms": int(start),
                "end_ms": int(end),
                "speaker": f"SPEAKER_{int(speaker):02d}",
                "text": text,
            }
        )
    return normalized
