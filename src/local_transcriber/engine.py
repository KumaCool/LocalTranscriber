from __future__ import annotations

import os
from importlib.metadata import version
from pathlib import Path
from typing import Any

from local_transcriber.models import MODEL_SPECS, validate_raw_result
from local_transcriber.schema import SUPPORTED_LANGUAGES, EngineInfo, Segment


class TranscriptionEngine:
    def __init__(
        self,
        cache_dir: Path = Path("var/cache/models"),
        threads: int = 2,
        speakers: int | None = None,
        language: str = "auto",
    ) -> None:
        if threads < 1:
            raise ValueError("threads must be positive")
        if speakers is not None and speakers < 1:
            raise ValueError("speakers must be positive")
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {language}")
        for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            os.environ[variable] = str(threads)
        import torch
        from funasr import AutoModel

        torch.set_num_threads(threads)
        paths = {
            role: (cache_dir / spec.cache_dirname).resolve() for role, spec in MODEL_SPECS.items()
        }
        missing = [str(path) for path in paths.values() if not path.is_dir()]
        if missing:
            raise RuntimeError(f"model cache is incomplete: {', '.join(missing)}")
        self._speakers = speakers
        self._language = language
        self._model: Any = AutoModel(
            model=str(paths["asr"]),
            vad_model=str(paths["vad"]),
            spk_model=str(paths["speaker"]),
            device="cpu",
            disable_update=True,
        )
        self.info = EngineInfo(
            funasr_version=version("funasr"),
            asr_model=MODEL_SPECS["asr"].model_id,
            vad_model=MODEL_SPECS["vad"].model_id,
            speaker_model=MODEL_SPECS["speaker"].model_id,
            device="cpu",
            threads=threads,
            speakers=speakers,
            language=language,
        )

    def transcribe(self, source: Path) -> list[Segment]:
        arguments: dict[str, Any] = {
            "batch_size_s": 300,
            "language": self._language,
            "use_itn": True,
            "sentence_timestamp": True,
        }
        if self._speakers is not None:
            arguments["preset_spk_num"] = self._speakers
        raw = self._model.generate(input=str(source), **arguments)
        return [Segment(**item) for item in validate_raw_result(raw)]
