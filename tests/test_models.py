from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_transcriber.cli import main
from local_transcriber.models import (
    MODEL_SPECS,
    validate_raw_result,
    write_model_manifest,
)


def test_model_specs_pin_all_three_required_models() -> None:
    assert set(MODEL_SPECS) == {"asr", "vad", "speaker"}
    assert MODEL_SPECS["asr"].model_id == "iic/SenseVoiceSmall"
    assert MODEL_SPECS["asr"].revision != "master"
    assert MODEL_SPECS["vad"].model_id == "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    assert MODEL_SPECS["speaker"].model_id == "iic/speech_campplus_sv_zh-cn_16k-common"
    assert all(spec.license == "Apache-2.0" for spec in MODEL_SPECS.values())


def test_validate_raw_result_accepts_verified_sentence_shape() -> None:
    segments = validate_raw_result(
        [{"sentence_info": [{"start": 120, "end": 900, "spk": 0, "sentence": "你好"}]}]
    )

    assert segments == [{"start_ms": 120, "end_ms": 900, "speaker": "SPEAKER_00", "text": "你好"}]


def test_validate_raw_result_cleans_rich_tags_and_drops_nospeech() -> None:
    segments = validate_raw_result(
        [
            {
                "sentence_info": [
                    {
                        "start": 0,
                        "end": 400,
                        "spk": 0,
                        "sentence": "<|nospeech|><|EMO_UNKNOWN|><|Speech|><|woitn|>",
                    },
                    {
                        "start": 500,
                        "end": 900,
                        "spk": 0,
                        "sentence": "<|zh|><|NEUTRAL|><|Speech|><|woitn|>你好",
                    },
                ]
            }
        ]
    )

    assert segments == [{"start_ms": 500, "end_ms": 900, "speaker": "SPEAKER_00", "text": "你好"}]


def test_validate_raw_result_collapses_exact_adjacent_repetitions() -> None:
    segments = validate_raw_result(
        [
            {
                "sentence_info": [
                    {
                        "start": 0,
                        "end": 900,
                        "spk": 0,
                        "sentence": "今天天气很好今天天气很好今天天气很好",
                    }
                ]
            }
        ]
    )

    assert segments[0]["text"] == "今天天气很好"


def test_validate_raw_result_keeps_short_intentional_repetition() -> None:
    segments = validate_raw_result(
        [{"sentence_info": [{"start": 0, "end": 900, "spk": 0, "sentence": "哈哈哈哈"}]}]
    )

    assert segments[0]["text"] == "哈哈哈哈"


@pytest.mark.parametrize(
    ("result", "message"),
    [
        ([], "non-empty list"),
        ([{}], "sentence_info"),
        ([{"sentence_info": []}], "non-empty"),
        (
            [{"sentence_info": [{"start": 0, "end": 1, "spk": 0, "sentence": ""}]}],
            "text",
        ),
        (
            [{"sentence_info": [{"start": 5, "end": 4, "spk": 0, "sentence": "x"}]}],
            "time range",
        ),
        (
            [{"sentence_info": [{"start": 0, "end": 4, "sentence": "x"}]}],
            "speaker",
        ),
    ],
)
def test_validate_raw_result_rejects_invalid_upstream_shapes(result, message) -> None:
    with pytest.raises(ValueError, match=message):
        validate_raw_result(result)


def test_write_model_manifest_records_resolved_cache(tmp_path: Path) -> None:
    cache = tmp_path / "models"
    for spec in MODEL_SPECS.values():
        (cache / spec.cache_dirname).mkdir(parents=True)

    destination = tmp_path / "models.json"
    write_model_manifest(destination, cache)

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert {item["role"] for item in payload["models"]} == {"asr", "vad", "speaker"}
    assert all(item["cached"] for item in payload["models"])


def test_models_pull_runs_a_second_time_without_downloading_weights(tmp_path, monkeypatch) -> None:
    calls = []

    def fake_pull(cache_root):
        calls.append(cache_root)
        for spec in MODEL_SPECS.values():
            (cache_root / spec.cache_dirname).mkdir(parents=True, exist_ok=True)
        return []

    monkeypatch.setattr("local_transcriber.cli.pull_models", fake_pull)
    cache = tmp_path / "models"
    manifest = tmp_path / "manifest.json"

    assert main(["models", "pull", "--cache-dir", str(cache), "--manifest", str(manifest)]) == 0

    assert calls == [cache]
    assert all(item["cached"] for item in json.loads(manifest.read_text())["models"])
