# FunASR + SenseVoice + CAM++ and Hermes Notes

Use this reference only after checking current upstream docs and installed versions; version-specific claims can change.

## Concrete composed pipeline

A CPU-oriented Chinese-first stack can be composed as:

- FunASR orchestration;
- SenseVoiceSmall for ASR/language/emotion/event output;
- FSMN-VAD for speech regions;
- CAM++ for speaker embeddings and clustering;
- FFmpeg/ffprobe for input normalization and inspection.

Conceptual initialization:

```python
from funasr import AutoModel

model = AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model="fsmn-vad",
    spk_model="cam++",
    device="cpu",
)
```

The useful composed result is typically in `sentence_info`, with segment start/end, text/sentence, and `spk`. Verify exact keys with a real invocation before defining the application's schema.

## Semantics

- SenseVoiceSmall does not by itself identify or diarize speakers; CAM++ is a separate component.
- `spk` values are anonymous and task-local unless an explicit cross-file identity system is built.
- VAD-derived or sentence-level timing is suitable for navigation and ordinary subtitles, not automatically word-level alignment.
- Overlapping speech remains a difficult case because embedding clustering is not equivalent to source separation.

## CPU host policy

For roughly 4 CPU cores and 8 GiB RAM:

- one transcription worker;
- one loaded model stack;
- benchmark 2 versus 3 inference threads;
- queue long files instead of concurrent requests;
- capture real-time factor and peak RSS before choosing persistent serving;
- keep model dependencies in the project's isolated environment, not Hermes's global runtime.

Do not state a processing speed before running a representative benchmark.

## Outputs

Prefer a canonical JSON document containing:

- schema version;
- source path/hash/duration and selected stream;
- exact package and model identifiers;
- runtime device and relevant parameters;
- segments with `start_ms`, `end_ms`, `speaker`, and `text`;
- task timestamps, status, and errors.

Generate Markdown/TXT/SRT/VTT from JSON. Avoid inventing word timing while constructing subtitles.

## Hermes survey procedure

Check these separately:

```bash
hermes tools list
hermes plugins list --plain --no-bundled
hermes plugins list --plain
hermes mcp list
hermes mcp catalog
hermes skills search "FunASR"
hermes skills search "speaker diarization"
```

Then inspect Hermes config without exposing secrets. Distinguish:

- STT configured in YAML;
- STT toolset enabled for the active surface;
- local package installed or cloud credentials present;
- a real voice sample successfully transcribed.

Hermes native local STT commonly uses faster-whisper for short inbound voice messages. That is a separate use case from long-file diarization. Hermes documentation allows cached inbound audio paths to reach the agent when automatic STT is disabled, which can be useful for handing a file to a custom CLI; verify the current docs before configuring.

## Integration decision

Use:

- **CLI + skill** for one-host, agent-invoked batch transcription;
- **native tool/plugin** for frequent structured Hermes calls;
- **stdio MCP** only when several MCP clients need the same engine;
- **HTTP service** only with a genuine service requirement, queue controls, authentication, and local/private-overlay binding.

Avoid enabling unrelated meeting-platform plugins merely because they mention transcription: caption capture or Graph-provided transcripts do not provide the same local ASR/diarization capability.

## Candidate skill safety

Community transcription skills may be useful examples but should be inspected before installation. Confirm they do not upload audio, run opaque remote installers, read unrelated credentials, or claim speaker support without actually configuring a speaker model. Prefer an internally verified CLI and a thin self-owned invocation skill once the engine works.