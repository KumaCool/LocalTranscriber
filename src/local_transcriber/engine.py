from __future__ import annotations

import os
from collections.abc import Callable
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

    def transcribe(
        self,
        source: Path,
        progress_callback: Callable[[float, float], None] | None = None,
    ) -> list[Segment]:
        arguments: dict[str, Any] = {
            "batch_size_s": 300,
            "language": self._language,
            "use_itn": True,
            "sentence_timestamp": True,
            "disable_pbar": True,
        }
        if self._speakers is not None:
            arguments["preset_spk_num"] = self._speakers

        def safe_progress(current: float, total: float) -> None:
            if progress_callback is None:
                return
            try:
                progress_callback(current, total)
            except Exception:
                return

        original_inference = getattr(self._model, "inference", None)
        vad_model = getattr(self._model, "vad_model", None)
        asr_model = getattr(self._model, "model", None)
        vad_total_ms = 0.0
        processed_ms = 0.0

        if callable(original_inference) and vad_model is not None:

            def inference_with_progress(*args: Any, **kwargs: Any) -> Any:
                nonlocal processed_ms, vad_total_ms
                result = original_inference(*args, **kwargs)
                selected_model = kwargs.get("model")
                if selected_model is vad_model and result:
                    segments = result[0].get("value", [])
                    vad_total_ms = float(sum(max(0, end - start) for start, end in segments))
                    if vad_total_ms > 0:
                        safe_progress(0.0, vad_total_ms)
                elif selected_model is asr_model and vad_total_ms > 0 and args:
                    batch = args[0]
                    try:
                        batch_ms = sum(len(samples) for samples in batch) / 16.0
                    except (TypeError, ValueError):
                        batch_ms = 0.0
                    processed_ms = min(vad_total_ms, processed_ms + batch_ms)
                    safe_progress(processed_ms, vad_total_ms)
                return result

            self._model.inference = inference_with_progress

        def native_progress(current: float, total: float) -> None:
            if not callable(original_inference) or vad_model is None:
                safe_progress(current, total)

        try:
            raw = self._model.generate(
                input=str(source), progress_callback=native_progress, **arguments
            )
        finally:
            if callable(original_inference):
                self._model.inference = original_inference
        return [Segment(**item) for item in validate_raw_result(raw)]
