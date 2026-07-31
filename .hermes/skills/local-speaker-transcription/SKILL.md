---
name: local-speaker-transcription
description: "Use when locally transcribing an authorized media file with anonymous speakers and segment timestamps."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [transcription, audio, diarization, offline, localtranscriber]
    related_skills: [localtranscriber-engineering]
---

# Local Speaker Transcription

## Overview

Use the verified LocalTranscriber CLI in `${LOCALTRANSCRIBER_ROOT}` to process one authorized local media file at a time. The pipeline runs locally with cached FunASR models and produces canonical JSON plus Markdown, TXT, and SRT exports.

Speaker labels are anonymous clustering labels such as `SPEAKER_00`; they are not identity recognition. Timestamps are segment timestamps and are not word-level alignment. Results, especially overlapping speech and multi-speaker audio, require manual review.

## When to Use

Use this skill when the user asks to:

- transcribe a local meeting, interview, voice message, or media file;
- distinguish anonymous speakers and include segment timestamps;
- export a local transcription as JSON, Markdown, TXT, or SRT;
- perform an offline-after-cache transcription through Hermes.

Do not use it to identify real people by voice, promise word-level timing, separate overlapping sources, process an untrusted path without inspection, or expose a network service.

## Verified Runtime Contract

- Project root: `${LOCALTRANSCRIBER_ROOT}` (set it to the absolute path of the repository)
- Command: `uv run local-transcriber transcribe`
- Model cache: `var/cache/models`
- Hermes runtime state: `var/work/hermes`
- Hermes output root: `var/output/hermes`
- Resource policy: single worker, `--threads 2`, automatic speaker-count estimation by default
- Language policy: `--language auto` by default; offer `zh`, `en`, `yue`, `ja`, or `ko` when the user knows the language
- Success artifact set: `result.json`, `transcript.md`, `transcript.txt`, `transcript.srt`, `media.json`
- Success state: `result.json.job.status == "succeeded"`
- Cancellation: exit code 130 means cancelled; do not report success

Do not add `--speakers N` unless the user explicitly requests a known count and accepts that it may degrade clustering. Do not use `--keep-normalized` unless diagnostics require it.

## Workflow

### 1. Validate input and scope

1. Resolve the supplied path and confirm it is a regular file.
2. Keep all writes under `${LOCALTRANSCRIBER_ROOT}/var/`.
3. Inspect media with `ffprobe` before starting. Reject files without an audio stream and report duration/format when available.
4. Confirm the media was supplied by the user or is an existing project-owned authorized acceptance sample. Do not upload source audio to third parties.
5. Check that the model cache directories exist. Do not run `models pull` during a private/offline transcription unless the user authorized network access.

Completion criterion: input exists, contains audio, is authorized, and cached model prerequisites are present.

Before launch, report the CLI's estimated completion window. Describe it as an estimate based on media duration and this host's measured runs, not a deadline.

### 2. Start exactly one transcription

Use absolute paths for input and project-owned output/runtime directories:

```bash
cd "${LOCALTRANSCRIBER_ROOT:?set LOCALTRANSCRIBER_ROOT to the repository path}"
uv run local-transcriber transcribe /absolute/path/to/input \
  --output-dir var/output/hermes \
  --runtime-dir var/work/hermes \
  --cache-dir var/cache/models \
  --language auto \
  --threads 2
```

Transcription is resource-heavy and may take minutes. Start it with the Hermes terminal tool using `background=true` and `notify_on_complete=true`. Do not launch another transcription while one is active. Do not poll in a tight loop; wait for completion notification or inspect only when the user asks for progress.

Completion criterion: the process exits and its stdout identifies the generated `result.json` path.

### 3. Handle exit states

- Exit code `0`: continue to artifact validation.
- Exit code `2`: input/media/validation error; read the corresponding job record and report the safe error.
- Exit code `3`: engine/model failure; retain the job record and diagnostics, but do not claim partial output is valid.
- Exit code `4`: another single worker owns the lock; do not bypass the lock or spawn a second worker.
- Exit code `130`: cancelled; report cancellation and do not return artifacts as a successful transcript.
- Other nonzero exit: report the actual exit code and stderr; do not invent output.

Completion criterion: nonzero runs stop with an evidence-based failure report; only exit code `0` proceeds.

### 4. Validate canonical output before delivery

Read `result.json` and verify all of the following:

1. `schema_version` is `1`.
2. `job.status` is `succeeded` and `job.error` is null.
3. `source.path`, `size_bytes`, `sha256`, and `duration_ms` are present.
4. Every segment has integer `start_ms` and `end_ms`, `0 <= start_ms <= end_ms`, a speaker beginning with `SPEAKER_`, and text.
5. The engine records CPU, model IDs, and `threads == 2`.
6. The same directory contains nonempty `transcript.md`, `transcript.txt`, `transcript.srt`, and `media.json`.
7. Read back each text export. Parse `media.json`. Do not trust file existence alone.

Empty segments may be a valid engine result for silent audio, but explicitly tell the user that no speech segments were detected.

Completion criterion: canonical JSON and every requested derived artifact parse/read successfully and agree on the completed job directory.

Readable output should not contain raw SenseVoice `<|...|>` tags or pure `nospeech` segments. Exact adjacent whole-sentence repetitions may be collapsed, but this does not correct semantic recognition errors.

### 5. Return results through Telegram

Give a concise caveat that labels are anonymous, segment timing is not word-level, and manual review is required for multi-speaker or overlapping speech. Attach only artifacts the user requested; when no subset was requested, return Markdown and SRT by default and offer canonical JSON for machine processing.

Use absolute attachment lines in the final response, for example:

```text
MEDIA:${LOCALTRANSCRIBER_ROOT}/var/output/hermes/<job-id>/transcript.md
MEDIA:${LOCALTRANSCRIBER_ROOT}/var/output/hermes/<job-id>/transcript.srt
```

Do not attach the original recording unless the user explicitly asks. Do not paste sensitive transcript text into chat merely to prove success.

Completion criterion: requested validated files are attached with `MEDIA:` paths and the semantic limitations are stated accurately.

## Privacy and Retention

- Do not upload audio, normalized PCM, transcripts, hashes, or model input to cloud services.
- Do not expose an HTTP service or open a listening port for this workflow.
- Keep input, work state, logs, and outputs under ignored `var/` paths.
- The CLI normally deletes normalized audio after success; preserve it only for explicitly authorized diagnostics.
- Never commit recordings, transcripts, job records, or generated acceptance artifacts.
- Before Git operations, verify `var/` remains ignored and stage only exact source/document paths.

## Known Limits

- `SPEAKER_XX` is anonymous and may not remain stable across runs.
- Automatic speaker estimation can merge speakers; forcing a count does not guarantee better labels.
- Multi-speaker and overlapping speech quality is not reliable.
- SenseVoice output may include rich-text event tags or repeated text that needs correction.
- Peak memory observed during acceptance was about 3.2 GiB; keep one loaded model stack and one worker.

## Common Pitfalls

1. **Using Hermes short-message STT instead.** That path does not satisfy this project's diarization and canonical export contract. Invoke this CLI.
2. **Foreground timeout interpreted as model failure.** Long jobs must use tracked background execution with completion notification.
3. **Returning files before parsing JSON.** A directory can contain stale or partial exports. Validate the job status and every artifact first.
4. **Calling labels identities.** Use “anonymous speaker labels,” never names, unless a separate enrollment/identification system was explicitly run.
5. **Claiming word precision.** These are segment timestamps, not word-level forced alignment.
6. **Bypassing the worker lock.** Wait or report busy; never create unconstrained parallel model processes.
7. **Leaking private media through Git or chat.** Keep generated data in `var/`, attach only requested derived files, and never commit it.

## Verification Checklist

- [ ] Input is authorized, local, and has an audio stream.
- [ ] Cached model paths exist; no unapproved model download occurred.
- [ ] One background process ran with `--threads 2` and the project runtime/output roots.
- [ ] Process exited `0`; canonical status is `succeeded`.
- [ ] Segment bounds, anonymous labels, source metadata, and engine metadata validate.
- [ ] JSON, Markdown, TXT, SRT, and media metadata were read back.
- [ ] Only requested validated artifacts are returned through `MEDIA:` paths.
- [ ] Privacy, anonymity, segment-timestamp, overlap, and manual-review limits are stated.
