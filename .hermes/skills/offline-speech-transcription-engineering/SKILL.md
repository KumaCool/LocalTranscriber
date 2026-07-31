---
name: localtranscriber-engineering
description: "Use when engineering the LocalTranscriber offline STT project."
version: 1.0.0
created_by: agent
metadata:
  hermes:
    tags: [localtranscriber, speech-to-text, transcription, diarization, timestamps, offline, cpu, audio]
---

# LocalTranscriber Engineering

Design, validate, and integrate privacy-preserving speech-to-text pipelines for local files, especially when the user requires timestamps, speaker labels, bounded CPU/RAM use, or Hermes integration.

## Trigger

Use this skill when asked to:

- select or compare a local ASR stack;
- transcribe meetings/interviews with timestamps;
- distinguish speakers (diarization);
- build a CPU-only transcription CLI, queue, or local service;
- connect a custom transcription pipeline to Hermes;
- assess whether an existing STT plugin, skill, or MCP satisfies diarization requirements.

Do not use for TTS, music generation, generic audio visualization, or cloud-only transcription where local processing is irrelevant.

## Core distinctions

Keep these capabilities separate in both design and reporting:

1. **ASR** converts speech to text.
2. **VAD** finds regions containing speech.
3. **Speaker embedding + clustering** assigns anonymous speaker labels.
4. **Speaker identification** maps a voice to a real identity and requires enrollment/reference audio plus explicit thresholds.
5. **Segment timestamps** locate utterances; they are not word-level forced alignment.
6. **Source separation/overlap handling** is distinct from diarization and may require another model.

Never describe anonymous `Speaker 0/1` labels as real-person recognition. Never imply segment boundaries are word-accurate unless forced alignment was actually run and verified.

## Workflow

### 1. Establish the operating envelope

Probe the live host before recommending or installing models:

- CPU architecture, core/thread count, SIMD flags;
- available RAM and swap;
- usable accelerator, not merely a display adapter;
- free disk space;
- Python/runtime compatibility;
- FFmpeg/ffprobe availability.

Convert the result into explicit limits: worker count, thread cap, expected batch rather than realtime operation, model-cache budget, and whether a persistent model process is viable.

### 2. Turn requirements into an acceptance matrix

Record at minimum:

- primary languages and code-switching needs;
- offline-after-cache requirement;
- segment versus word timestamps;
- anonymous diarization versus known-speaker identification;
- expected/known speaker count;
- overlap/noise/telephone/remote-mic conditions;
- input formats and maximum duration;
- required exports (canonical JSON, Markdown/TXT, SRT/VTT);
- privacy and network exposure constraints;
- acceptable real-time factor and peak memory.

### 3. Verify upstream capability rather than inferring it

Consult current official repository/docs and inspect the exact installed/package version. Confirm:

- the ASR checkpoint's supported languages;
- whether diarization is native or composed from a separate model;
- which result object contains timestamps and speaker IDs;
- whether the desired behavior requires a minimum or source version;
- model licenses and download sources;
- CPU support and Python compatibility.

Pin tested versions. Do not let a README example using a moving `main` branch become an unverified production contract.

### 4. Search integrations without confusing them with engines

Inventory independently:

- installed skills;
- skill registries/hubs;
- enabled and bundled plugins;
- Hermes native STT configuration and runtime dependencies;
- configured MCP servers and the official MCP catalog.

A skill is usually procedural guidance, not proof that its model stack is installed. A config flag is not proof that provider dependencies or credentials are usable. Inspect community packages before installation for uploads, remote scripts, credential access, shell interpolation, model/version pinning, and whether they truly implement diarization.

### 5. Prefer a canonical local engine boundary

For a single-host workflow, implement and verify an independent CLI first:

```text
media input -> ffprobe -> FFmpeg normalization -> VAD/ASR/diarization -> canonical JSON -> derived exports
```

Use canonical JSON as the source of truth. Derive readable text and subtitle formats from it rather than independently formatting raw model output.

Minimum segment schema:

```json
{
  "start_ms": 650,
  "end_ms": 4200,
  "speaker": "SPEAKER_00",
  "text": "..."
}
```

Also record source metadata, engine/model versions, parameters, task status, and errors.

### 6. Normalize media safely

Use FFmpeg argument arrays, not shell-concatenated filenames. A typical ASR normalization target is 16 kHz mono signed 16-bit PCM, but verify the selected model's expected input. Record selected audio stream and ffprobe metadata.

### 7. Bound resources and make jobs recoverable

On constrained CPU hosts:

- default to one worker and one loaded model stack;
- set OMP/MKL/PyTorch thread limits based on benchmarks;
- use durable states such as `queued/running/succeeded/failed/cancelled`;
- separate input, work, output, and model-cache directories;
- retain diagnostics on failure and clean disposable normalized audio by policy;
- do not expose each HTTP request as an unconstrained model process.

### 8. Validate with representative audio

Run real samples covering quiet two-speaker, noisy two-speaker, multi-speaker, overlap, code-switching, and telephone-quality audio. Measure:

- transcription errors/subjective corrections;
- speaker confusion and false speaker switches;
- timestamp boundary error;
- real-time factor (processing duration / audio duration);
- peak RSS and CPU utilization;
- human correction effort.

A smoke test proves wiring only, not quality.

### 9. Prove offline operation

Pre-fetch all required models, then repeat a known test with network access blocked or disabled. Only claim offline operation after that test succeeds from cache.

### 10. Integrate in layers

Use the lightest suitable layer:

1. stable local CLI;
2. project/user skill that invokes the verified CLI;
3. native Hermes tool/plugin only when structured frequent invocation warrants it;
4. stdio MCP when multiple MCP clients need the capability;
5. HTTP service only when a service boundary is genuinely needed, bound to localhost or a private overlay network unless explicitly authorized otherwise.

Hermes's short-message STT can coexist with a meeting-file pipeline but should not be represented as a replacement for diarization/alignment unless it actually provides those outputs.

## Documentation deliverables

For a new project, write two documents early:

- a solution document covering requirements, architecture, semantics, resources, output schema, phases, and acceptance;
- an integration survey covering relevant skills, native STT, plugins, MCPs, trust level, and the recommended integration boundary.

Clearly mark what is planned versus installed and empirically verified.

## Pitfalls

- Treating VAD segments as guaranteed sentence boundaries.
- Treating speaker clustering as identity recognition.
- Claiming word-level timing from segment timestamps.
- Assuming a community skill's description proves its implementation.
- Assuming `enabled: true` proves runtime readiness.
- Installing two competing ASR stacks into the global Hermes environment instead of an isolated project environment.
- Starting with MCP or a web service before the transcription CLI and schema are stable.
- Benchmarking only clean, single-speaker demo audio.
- Claiming offline behavior merely because models are cacheable.

## Verification checklist

- [ ] Live host envelope recorded.
- [ ] Exact ASR/VAD/diarization roles documented.
- [ ] Version and result schema verified against current upstream.
- [ ] Canonical JSON schema defined.
- [ ] Single-worker and thread limits chosen from measurements.
- [ ] Representative diarization test set exercised.
- [ ] JSON and subtitle exports read back successfully.
- [ ] Offline cached run completed without network.
- [ ] Integration layer justified (CLI/skill/plugin/MCP/service).
- [ ] Planned, installed, configured, enabled, and verified states are not conflated.

## Reference

See `references/funasr-sensevoice-hermes.md` for a concrete CPU-oriented FunASR/SenseVoice/CAM++ stack and Hermes integration notes.