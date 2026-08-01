# LocalTranscriber User Guide

**English** | [简体中文](user-guide.zh-CN.md)

This guide covers installation, model preparation, single-file and batch transcription, background jobs, output export, and troubleshooting. Run all commands from the project root.

## 1. Purpose and Boundaries

LocalTranscriber uses the local CPU to transcribe audio and video into:

- text with millisecond segment timestamps;
- anonymous speaker labels such as `SPEAKER_00` and `SPEAKER_01`;
- JSON, Markdown, TXT, and SRT files.

Important limitations:

- Speaker labels distinguish voice clusters within a task; they do not identify real people.
- Timestamps are segment-level, not word-level forced alignment.
- Overlapping speech, short responses, noise, accents, and technical terminology may reduce accuracy.
- Important results require human review and must not be used for forensic analysis or high-risk automated decisions.

## 2. Runtime Requirements

- Linux
- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- FFmpeg and ffprobe
- An x86_64 host supported by the PyTorch CPU build
- Enough storage for Python dependencies, model caches, and transcription outputs

Install FFmpeg on Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## 3. Installation and First-Time Setup

```bash
git clone https://github.com/KumaCool/LocalTranscriber.git
cd LocalTranscriber
uv sync --locked
```

Check the version:

```bash
uv run local-transcriber --version
```

Probe the local environment and save the report:

```bash
uv run local-transcriber environment probe \
  --output var/acceptance/environment.json
```

Download the pinned models before the first run:

```bash
uv run local-transcriber models pull
```

The default model cache is `var/cache/models/`. Model prefetching requires network access; transcription can run offline after the cache is complete.

## 4. Common Operations

### 4.1 Transcribe One File

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output
```

The command waits in the foreground by default. At startup, stderr displays the task ID; after success, stdout displays the result JSON path.

### 4.2 Transcribe Multiple Files

```bash
uv run local-transcriber transcribe \
  /path/to/a.wav /path/to/b.mp3 \
  --output-dir var/output
```

All tasks use the same bounded scheduler. LocalTranscriber may lower actual concurrency according to CPU and available memory. `--max-workers` is an upper request, not guaranteed concurrency.

### 4.3 Transcribe a Directory

Scan only the directory's top level:

```bash
uv run local-transcriber transcribe-dir /path/to/media \
  --output-dir var/output
```

Scan subdirectories recursively:

```bash
uv run local-transcriber transcribe-dir /path/to/media \
  --recursive \
  --output-dir var/output
```

Preview accepted and skipped files before processing:

```bash
uv run local-transcriber transcribe-dir /path/to/media \
  --recursive --dry-run --json \
  --output-dir var/output
```

Supported extensions: `.aac`, `.flac`, `.m4a`, `.mkv`, `.mov`, `.mp3`, `.mp4`, `.ogg`, `.opus`, `.wav`, `.webm`, and `.wma`.

Discovery skips symbolic links, duplicate paths, duplicate content, unsupported extensions, and media that cannot be probed. Recursive scans also exclude directories named `runtime`, `output`, `cache`, `work`, or `state`, plus the runtime, output, and cache directories selected for the current command.

## 5. Common Transcription Options

| Option | Default | Purpose |
|---|---:|---|
| `--output-dir PATH` | required | Root directory for final results |
| `--runtime-dir PATH` | `var/work` | Task, batch-state, and local IPC data |
| `--cache-dir PATH` | `var/cache/models` | Model cache directory |
| `--language VALUE` | `auto` | Language hint: `auto`, `zh`, `en`, `yue`, `ja`, or `ko` |
| `--speakers N` | automatic | Hint for a known speaker count; it does not guarantee better clustering |
| `--threads N` | `2` | Requested threads per worker, still constrained by the resource budget |
| `--max-workers N` | `1` | Requested worker limit, still constrained by CPU and memory budgets |
| `--cpu-limit-percent N` | `50` | CPU budget from `1–100`; use `0` to disable the CPU budget |
| `--memory-limit-percent N` | `70` | Memory budget from `1–100`; use `0` to disable the percentage budget |
| `--config PATH` | none | Load the `[resources]` table from a TOML file |
| `--nice N` | `10` | Process niceness from `0–19` |
| `--keep-normalized` | off | Keep the FFmpeg-normalized temporary WAV |
| `--bg` | off | Submit to the local background manager |
| `--json` | off | Emit machine-readable JSON for commands that support it |

Provide a Chinese language hint:

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output \
  --language zh
```

Provide a two-speaker hint:

```bash
uv run local-transcriber transcribe /path/to/input.wav \
  --output-dir var/output \
  --speakers 2
```

Resource settings use this precedence: command-line options, then the TOML file, then built-in defaults. For example:

```toml
[resources]
cpu_limit_percent = 50
memory_limit_percent = 70
max_workers = 1
threads_per_worker = 2
nice = 10
```

Pass it with `--config /path/to/local-transcriber.toml`. Set either percentage to `0` to disable that budget. A disabled memory percentage does not bypass physical availability: the scheduler still refuses to start a worker that cannot fit in currently available memory.

## 6. Foreground Progress, Status, and Cancellation

Without `--bg`, the command always runs in foreground mode. It reports the current stage, completion percentage, and estimated completion range. The ETA may initially remain in a calculating state and can change with system load.

Query a task from another terminal:

```bash
uv run local-transcriber job status <job-id> \
  --runtime-dir var/work
```

Request machine-readable JSON:

```bash
uv run local-transcriber job status <job-id> \
  --runtime-dir var/work --json
```

Pressing `Ctrl+C` during a foreground run requests cancellation of the current batch and exits with code `130`. A task reaches `100%` and `succeeded` only after every output has been written successfully.

## 7. Background Operation and Recovery

The background manager uses local Unix IPC only. It does not listen on HTTP or TCP ports.

### 7.1 Hosts With User-Level systemd

```bash
uv run local-transcriber worker start --runtime-dir var/work
uv run local-transcriber worker status --runtime-dir var/work
```

Submit a background batch:

```bash
uv run local-transcriber transcribe-dir /path/to/media \
  --recursive \
  --output-dir var/output \
  --runtime-dir var/work \
  --bg --json
```

A successful command immediately returns a batch ID and task IDs.

### 7.2 Hosts Without User-Level systemd

Run the manager in a terminal tracked by a terminal multiplexer or service manager:

```bash
uv run local-transcriber worker run --runtime-dir var/work
```

Submit `--bg` tasks from another terminal. Do not start an unmanaged worker with a bare `&` or `nohup`.

### 7.3 Query, Cancel, and Retry

```bash
uv run local-transcriber batch status <batch-id> \
  --runtime-dir var/work

uv run local-transcriber batch cancel <batch-id> \
  --runtime-dir var/work --json

uv run local-transcriber batch retry <batch-id> \
  --runtime-dir var/work --json
```

Replace `batch` with `job` to run `status`, `cancel`, or `retry` on one task.

After a manager restart:

- queued tasks can resume processing;
- tasks that were running are accurately marked as interrupted rather than successful;
- interrupted or failed tasks require an explicit `retry`;
- retries receive new IDs while old records and successful outputs remain intact.

Stop or restart a systemd worker:

```bash
uv run local-transcriber worker stop --runtime-dir var/work
uv run local-transcriber worker restart --runtime-dir var/work
```

`job cancel/retry` and `batch cancel/retry` require the background manager to be running. Status queries read persisted state directly.

## 8. Output Directories and Files

Every successful task has its own result directory. Directory batches preserve the input's relative directory structure and include the task ID in the result directory name to prevent collisions.

| File | Purpose |
|---|---|
| `result.json` | Authoritative structured result containing source, engine, task, and segment data |
| `transcript.md` | Human-readable Markdown transcript |
| `transcript.txt` | Plain-text transcript |
| `transcript.srt` | SRT subtitles |
| `media.json` | Input-media information reported by ffprobe |

`result.json` is the sole source of truth for all derived exports. Each segment contains:

```json
{
  "start_ms": 650,
  "end_ms": 4200,
  "speaker": "SPEAKER_00",
  "text": "..."
}
```

LocalTranscriber removes SenseVoice rich-text tags, filters pure `nospeech` segments, and collapses obvious consecutive whole-sentence repetition. It does not automatically correct semantic recognition errors.

## 9. Re-export From JSON

```bash
uv run local-transcriber export /path/to/result.json --format srt
uv run local-transcriber export /path/to/result.json --format md
uv run local-transcriber export /path/to/result.json --format txt
```

By default, the export is written beside the JSON file with the corresponding extension. To select another path:

```bash
uv run local-transcriber export /path/to/result.json \
  --format srt \
  --output /path/to/meeting.srt
```

## 10. Data, Privacy, and Offline Operation

Default runtime paths:

- `var/cache/`: model cache
- `var/input/`: optional local input copies
- `var/work/`: task state, IPC data, and temporary files
- `var/output/`: final transcription results
- `var/acceptance/`: local validation artifacts

These directories are excluded from Git by default. Do not publish recordings, transcripts, task records, or environment reports. Ensure that you are authorized to process the input and comply with privacy, copyright, and data-protection requirements.

For strict offline operation:

1. Run `models pull` while online.
2. Use the same `--cache-dir` for subsequent commands.
3. Validate one non-sensitive sample with network access blocked.
4. Do not delete or move the cached models.

LocalTranscriber does not provide an HTTP service and does not upload media. Installing dependencies and prefetching models require network access the first time.

## 11. Troubleshooting

### FFmpeg or ffprobe Is Missing

Install FFmpeg, then repeat the environment probe:

```bash
uv run local-transcriber environment probe \
  --output var/acceptance/environment.json
```

### Background Submission Reports That It Cannot Connect to the systemd Bus

The host does not provide a usable user-level systemd session. Follow the “Hosts Without User-Level systemd” instructions, start a tracked `worker run`, and submit again.

### Multiple Workers Were Requested, but Only One Runs

This is resource protection. The actual worker count is constrained by logical CPUs, the default 50% CPU budget, available memory, and user options. LocalTranscriber lowers concurrency instead of forcing multiple model instances into insufficient resources.

### Speaker Labels Are Incorrect

Anonymous clustering is sensitive to overlapping speech, short utterances, multiple speakers, and poor recordings. `--speakers N` is only a hint, not an accuracy guarantee. Review and correct important results manually.

### Some Directory Files Were Not Processed

Run `transcribe-dir --dry-run --json` and inspect the skip reasons. Typical causes include unsupported extensions, invalid media, symbolic links, duplicate content, or excluded directories.

### Display Complete Command Help

```bash
uv run local-transcriber --help
uv run local-transcriber transcribe --help
uv run local-transcriber transcribe-dir --help
uv run local-transcriber worker --help
```

## 12. Upgrade and Rollback

Stop the background worker before upgrading, then check out the intended version and synchronize from the lock file:

```bash
uv run local-transcriber worker stop --runtime-dir var/work
git fetch --tags origin
git checkout v0.2.1
uv sync --locked
uv run local-transcriber --version
```

To roll back, check out the previous tag and run `uv sync --locked` again. See [`../CHANGELOG.md`](../CHANGELOG.md) for version and compatibility notes. Do not overwrite or move existing release tags.
