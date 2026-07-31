from pathlib import Path

from local_transcriber.engine import TranscriptionEngine


def test_engine_passes_language_and_quality_options_to_funasr() -> None:
    received = {}

    class FakeModel:
        def generate(self, **kwargs):
            received.update(kwargs)
            return [{"sentence_info": [{"start": 0, "end": 100, "spk": 0, "sentence": "你好"}]}]

    engine = TranscriptionEngine.__new__(TranscriptionEngine)
    engine._model = FakeModel()
    engine._speakers = None
    engine._language = "zh"

    result = engine.transcribe(Path("normalized.wav"))

    assert result[0].text == "你好"
    assert received["language"] == "zh"
    assert received["use_itn"] is True
    assert received["sentence_timestamp"] is True
