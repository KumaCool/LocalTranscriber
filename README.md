# LocalTranscriber

**English** | [简体中文](README.zh-CN.md)

LocalTranscriber is a local, offline speech transcription tool designed for CPU-only environments. Built with FunASR, SenseVoiceSmall, FSMN-VAD, and CAM++, it produces JSON, Markdown, TXT, and SRT files with anonymous speaker labels and segment-level timestamps.

Audio, model inputs, and transcription results can remain on the local machine. The project does not provide an HTTP service and does not upload media files.

## Features

- **Local offline transcription:** Runs without network access after the models have been downloaded.
- **Anonymous speaker clustering:** Produces task-scoped labels such as `SPEAKER_00` and `SPEAKER_01`.
- **Segment timestamps:** Provides millisecond start and end times; it does not claim word-level forced alignment.
- **Multiple export formats:** Canonical JSON, Markdown, plain text, and SRT subtitles.
- **Recoverable task state:** Persists task records and uses bounded workers for resource-constrained CPU hosts.
- **Media validation:** Uses FFmpeg/ffprobe to validate and normalize common audio and video inputs.
- **Hermes Agent integration:** Includes an optional local transcription Skill while keeping the CLI independently usable.

## Limitations

- Speaker labels are anonymous clustering results and cannot identify real people.
- Multi-speaker audio, short responses, and overlapping speech may cause speaker merges or assignment errors.
- Technical terminology, accents, noise, and low-quality recordings may reduce recognition accuracy.
- Results should be reviewed by a person and are not suitable for forensic analysis or other high-risk automated decisions.
- The current release requires Python 3.11 and primarily supports CPU-based operation.

## Requirements

- Linux (the primary verified platform; testing and contributions for other platforms are welcome)
- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- FFmpeg and ffprobe
- An x86_64 environment supported by the PyTorch CPU build
- Enough disk space for dependencies, model caches, and transcription outputs

Install FFmpeg on Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## Installation

Clone the repository and install the locked dependencies:

```bash
git clone https://github.com/KumaCool/LocalTranscriber.git
cd LocalTranscriber
uv sync --locked
```

Check the installed version:

```bash
uv run local-transcriber --version
```

Probe the environment:

```bash
uv run local-transcriber environment probe \
  --output var/acceptance/environment.json
```

Download the models before the first transcription:

```bash
uv run local-transcriber models pull
```

Models are stored under the Git-ignored `var/cache/models/` directory. This step requires network access; transcription can run offline after the cache is complete.

When upgrading, stop the background worker, fetch the intended version, and synchronize from the lock file. To roll back, check out the previous tag and synchronize again:

```bash
uv run local-transcriber worker stop
git fetch --tags origin
git checkout v0.2.1
uv sync --locked
uv run local-transcriber --version
```

See [`CHANGELOG.md`](CHANGELOG.md) for version changes. Do not overwrite or move an existing release tag.

## Quick Start

Transcribe one file:

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output
```

Without `--bg`, the command always waits in the foreground. Multiple files and directories use the same persistent scheduler. CPU and memory budgets default to 50% and 70%, but users may lower, raise, or disable either budget. Worker and thread counts use the resulting policy plus current available memory.

```bash
uv run local-transcriber transcribe /path/a.wav /path/b.mp3 \
  --output-dir var/output

uv run local-transcriber transcribe-dir /path/to/media-dir \
  --output-dir var/output
```

Use `--bg` only when the job must survive terminal disconnection or continue across sessions. The background manager uses local Unix IPC and does not listen on HTTP/TCP. A successful submission returns batch and task IDs:

```bash
uv run local-transcriber transcribe-dir /path/to/media-dir \
  --output-dir var/output --runtime-dir var/work --bg --json

uv run local-transcriber batch status <batch-id> --runtime-dir var/work --json
uv run local-transcriber batch cancel <batch-id> --runtime-dir var/work --json
uv run local-transcriber batch retry <batch-id> --runtime-dir var/work --json
```

Where user-level systemd is available, use `worker start/status/stop/restart`. Otherwise, run a tracked `worker run` foreground process; do not use a bare `&` or `nohup`.

Provide a Chinese language hint:

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output \
  --language zh
```

Provide a known speaker count, noting that this does not guarantee better clustering:

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output \
  --speakers 2
```

Re-export SRT from canonical JSON:

```bash
uv run local-transcriber export /path/to/result.json --format srt
```

At startup, the CLI writes the task ID to stderr. A second process can query the persisted state without starting another worker:

```bash
uv run local-transcriber job status <job-id> \
  --runtime-dir var/work \
  --json
```

Status data includes the current stage, monotonic completion percentage, measured work, and an ETA range. Progress is driven by media-stage events, VAD speech segments, and actual ASR batches. ETA is a dynamic engineering estimate, not a constant-rate or exact completion-time guarantee. It remains `null`/`calculating` until enough samples exist, and confidence may fall to `low` during load variation or stalls. A task reaches `100%` only after all outputs have been written successfully.

View all commands:

```bash
uv run local-transcriber --help
uv run local-transcriber transcribe --help
```

For complete operational instructions, see the **[English user guide](docs/user-guide.md)** or its **[Chinese version](docs/user-guide.zh-CN.md)**.

## Output Files

A successful task directory contains:

| File | Purpose |
|---|---|
| `result.json` | Authoritative structured result containing task, source, engine, and segment data |
| `transcript.md` | Human-readable Markdown transcript |
| `transcript.txt` | Plain-text transcript |
| `transcript.srt` | Subtitle file |
| `media.json` | Probed input-media metadata |

Post-processing removes SenseVoice rich-text tags, filters pure `nospeech` segments, and collapses obvious consecutive whole-sentence repetition. It does not automatically correct semantic recognition errors.

## Data and Privacy

Runtime data is stored under `var/`:

- `var/cache/`: model cache
- `var/input/`: optional local input copies
- `var/work/`: task state and temporary files
- `var/output/`: transcription results
- `var/acceptance/`: local validation artifacts

These paths are excluded by `.gitignore` by default. Do not commit recordings, transcripts, task records, or environment reports containing machine details. Users are responsible for ensuring they are authorized to process input media and comply with applicable privacy, copyright, and data-protection requirements.

## Development

Install development dependencies and run the quality checks:

```bash
uv sync --locked --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests do not download models, access the network, or depend on private recordings by default. Real-model validation records are stored under [`docs/acceptance/`](docs/acceptance/).

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before contributing. Report security issues privately according to [`SECURITY.md`](SECURITY.md).

## Documentation

- [User guide](docs/user-guide.md) ([简体中文](docs/user-guide.zh-CN.md))
- [Technical design](docs/design/solution.md)
- [Implementation plan and engineering record](docs/plan/01-localtranscriber-implementation-plan.md)
- [Offline verification](docs/acceptance/offline-verification.md)
- [Quality evaluation matrix](docs/acceptance/evaluation-matrix.md)
- [Progress and dynamic ETA acceptance](docs/acceptance/progress-and-eta.md)
- [Batch, background recovery, and resource acceptance](docs/acceptance/batch-background-resources.md)
- [Release acceptance](docs/acceptance/release.md)
- [Optional Hermes Agent integration](docs/design/skills-and-hermes-integration.md)

The documents under `docs/acceptance/` and `docs/plan/` preserve development and validation evidence. They are not quality guarantees for every hardware, language, or recording condition.

## Contributing

Issues, documentation improvements, platform compatibility reports, and code contributions are welcome. Please ensure that you:

- do not submit audio or transcripts you are not authorized to publish;
- add offline, repeatable tests for new behavior;
- preserve local processing, bounded-worker, and privacy boundaries;
- run tests, lint, and formatting checks before submitting changes.

## License

Copyright © 2026 Shunnketu Kuma.

This project is licensed under the [MIT License](LICENSE). Dependencies and downloaded models are governed by their respective licenses; users are responsible for reviewing and complying with those terms.
