---
name: local-speaker-transcription
description: "Use when locally transcribing authorized media with anonymous speakers and segment timestamps."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [transcription, audio, diarization, offline, localtranscriber]
    related_skills: [localtranscriber-engineering]
---

# Local Speaker Transcription

## Purpose and limits

Use the verified LocalTranscriber CLI in `${LOCALTRANSCRIBER_ROOT}` for authorized local media. It produces canonical `result.json` plus `transcript.md`, `transcript.txt`, `transcript.srt`, and `media.json`.

`SPEAKER_XX` labels are anonymous and are not identity recognition. Timestamps are segment timestamps, not word-level alignment. Multi-speaker and overlapping speech require manual review. Do not upload private audio or transcripts. Do not expose an HTTP service or open a listening port.

The verified default is a single worker unless the live CPU and memory budget safely permits more; never force concurrency beyond the persisted effective budget.

## Verified contract

- Commands: `uv run local-transcriber transcribe` and `uv run local-transcriber transcribe-dir`.
- Model cache: `var/cache/models`; runtime: `var/work/hermes`; output: `var/output/hermes`.
- Runtime defaults: `--language auto`, `--threads 2`, automatic speaker count, bounded resource policy.
- The application run mode is **default foreground**. File count, duration, Hermes invocation, or terminal lifetime must never silently change it.
- Only use `--bg` when the user explicitly requests background execution or the task must survive the current Hermes process/session or terminal disconnect.
- `--background` and Unicode `—bg` are invalid.
- A successful result has `result.json.job.status == "succeeded"`; exit code 130 means cancelled.

Do not add `--speakers N` unless the user requests a known count and accepts that it may degrade clustering. Do not use `--keep-normalized` except for authorized diagnostics.

## 1. Validate input

1. Resolve each path; accept regular files or one directory for `transcribe-dir`.
2. Confirm the source is user-supplied or a project-owned authorized fixture.
3. Use `ffprobe` to confirm audio streams. Do not upload media.
4. Confirm cached model directories exist. Do not run `models pull` without authorization for network access.
5. Keep runtime and outputs under `${LOCALTRANSCRIBER_ROOT}/var/`.
6. For directories, use `--dry-run --json` first when scope or exclusions need inspection; add `--recursive` only when requested.

Report an estimated completion window as an engineering estimate, not a deadline.

## 2. Choose the run mode

### Default foreground

For ordinary single-file, multi-file, and directory requests, omit `--bg`:

```bash
cd "${LOCALTRANSCRIBER_ROOT:?set LOCALTRANSCRIBER_ROOT}"
uv run local-transcriber transcribe /absolute/a.wav /absolute/b.wav \
  --output-dir var/output/hermes \
  --runtime-dir var/work/hermes \
  --cache-dir var/cache/models \
  --language auto \
  --threads 2
```

Directory form:

```bash
uv run local-transcriber transcribe-dir /absolute/input-dir \
  --output-dir var/output/hermes \
  --runtime-dir var/work/hermes \
  --cache-dir var/cache/models \
  --language auto \
  --threads 2
```

The CLI remains foreground and waits for the batch terminal state. For a long command, Hermes may track that same foreground CLI process with terminal `background=true` and `notify_on_complete=true`; this is process tracking only and must not add application `--bg` or create an orphan process.

### Explicit durable background

Only use `--bg` under the policy above:

```bash
uv run local-transcriber transcribe /absolute/a.wav /absolute/b.wav \
  --output-dir var/output/hermes \
  --runtime-dir var/work/hermes \
  --cache-dir var/cache/models \
  --language auto \
  --threads 2 \
  --bg --json
```

Record the returned batch ID and task IDs. A queued record is not enough: submission succeeds only after the local manager acknowledges it. Exit code `4` means busy, insufficient resources, or manager/IPC failure; do not claim submission.

The manager uses same-UID Unix IPC and no TCP/HTTP. Use the managed worker lifecycle, never `nohup`, shell `&`, or an untracked subprocess:

```bash
uv run local-transcriber worker status --runtime-dir var/work/hermes --json
uv run local-transcriber worker restart --runtime-dir var/work/hermes --json
```

## 3. Query and control

Read-only status commands:

```bash
uv run local-transcriber batch status BATCH_ID --runtime-dir var/work/hermes --json
uv run local-transcriber job status JOB_ID --runtime-dir var/work/hermes --json
```

Do not poll in a tight loop. Report stage, progress percent, and ETA range as an engineering estimate. Schedule periodic updates only when requested; suppress unchanged or tiny updates and always send a terminal result.

User-directed controls:

```bash
uv run local-transcriber batch cancel BATCH_ID --runtime-dir var/work/hermes --json
uv run local-transcriber batch retry BATCH_ID --runtime-dir var/work/hermes --json
```

`job cancel` and `job retry` use the same form. Retry creates new IDs and does not overwrite old evidence or successful artifacts. Manager restart may mark orphaned running work `interrupted`; queued background work is recoverable, but interrupted work requires explicit retry.

## 4. Handle completion

- `0`: validate artifacts.
- `2`: input/discovery/control error.
- `3`: one or more engine/model tasks failed; other batch tasks may still succeed.
- `4`: manager, scheduler, lock, or resource failure.
- `130`: cancelled; do not report success.

For a partial-failure batch, report the aggregate honestly and validate successful jobs individually. Never describe pipeline success as proof of speaker accuracy.

## 5. Validate every successful job

Read, do not merely stat, each artifact:

1. Parse `result.json`; require schema version `1`, status `succeeded`, null error, source metadata, engine metadata, and CPU/thread values.
2. Require integer segment bounds with `0 <= start_ms <= end_ms`, `SPEAKER_` labels, and text.
3. Parse `media.json`.
4. Read nonempty Markdown/TXT/SRT; confirm they belong to the same job directory.
5. Empty segments may represent silence; state that no speech was detected.

Status and logs must not reveal input paths, transcript text, cache secrets, or private media. Never commit `var/` recordings, state, logs, or generated transcripts.

## 6. Return through Telegram

Attach only requested validated outputs. If the user does not specify, return Markdown and SRT and offer canonical JSON:

```text
MEDIA:${LOCALTRANSCRIBER_ROOT}/var/output/hermes/<job-id>/transcript.md
MEDIA:${LOCALTRANSCRIBER_ROOT}/var/output/hermes/<job-id>/transcript.srt
```

Do not attach the original media unless explicitly requested. State that labels are anonymous, timing is segment-level, and overlap/multi-speaker results need review.

## Verification checklist

- [ ] Input is local, authorized, and has audio.
- [ ] Models are cached; no unapproved download occurred.
- [ ] Default foreground was used unless durable `--bg` was justified.
- [ ] Background submission, when used, was manager-acknowledged and IDs were saved.
- [ ] Batch/job terminal states and actual exit codes were checked.
- [ ] Every successful canonical JSON and derived artifact was parsed/read.
- [ ] Partial failures, cancellation, anonymity, timing, and quality limits were reported honestly.
- [ ] No private media, transcript, secret, network service, or untracked process was exposed.
