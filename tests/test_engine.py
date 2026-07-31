from pathlib import Path

from local_transcriber.engine import TranscriptionEngine


def test_engine_passes_language_quality_and_progress_options_to_funasr() -> None:
    received = {}
    callbacks = []

    class FakeModel:
        def generate(self, **kwargs):
            received.update(kwargs)
            kwargs["progress_callback"](2, 5)
            return [{"sentence_info": [{"start": 0, "end": 100, "spk": 0, "sentence": "你好"}]}]

    engine = TranscriptionEngine.__new__(TranscriptionEngine)
    engine._model = FakeModel()
    engine._speakers = None
    engine._language = "zh"

    result = engine.transcribe(
        Path("normalized.wav"),
        progress_callback=lambda current, total: callbacks.append((current, total)),
    )

    assert result[0].text == "你好"
    assert received["language"] == "zh"
    assert received["use_itn"] is True
    assert received["sentence_timestamp"] is True
    assert received["disable_pbar"] is True
    assert callbacks == [(2, 5)]


def test_engine_swallows_project_progress_callback_errors() -> None:
    class FakeModel:
        def generate(self, **kwargs):
            kwargs["progress_callback"](1, 2)
            return [{"sentence_info": [{"start": 0, "end": 100, "spk": 0, "sentence": "你好"}]}]

    engine = TranscriptionEngine.__new__(TranscriptionEngine)
    engine._model = FakeModel()
    engine._speakers = None
    engine._language = "zh"

    def broken_callback(current: float, total: float) -> None:
        raise RuntimeError("observer failed")

    assert (
        engine.transcribe(Path("normalized.wav"), progress_callback=broken_callback)[0].text
        == "你好"
    )


def test_engine_instruments_real_vad_asr_work_when_native_callback_is_only_file_level() -> None:
    callbacks = []

    class FakeModel:
        vad_model = object()
        model = object()
        spk_model = object()

        def inference(self, audio, *, model=None, **kwargs):
            if model is self.vad_model:
                return [{"value": [[0, 1000], [1500, 3500]]}]
            return []

        def generate(self, *, progress_callback, **kwargs):
            progress_callback(1, 1)
            self.inference("source", model=self.vad_model)
            self.inference([[0] * 16000], model=self.model)
            self.inference([[0] * 32000], model=self.model)
            return [{"sentence_info": [{"start": 0, "end": 100, "spk": 0, "sentence": "你好"}]}]

    engine = TranscriptionEngine.__new__(TranscriptionEngine)
    engine._model = FakeModel()
    engine._speakers = None
    engine._language = "zh"

    engine.transcribe(
        Path("normalized.wav"),
        progress_callback=lambda current, total: callbacks.append((current, total)),
    )

    assert callbacks == [(0.0, 3000.0), (1000.0, 3000.0), (3000.0, 3000.0)]
