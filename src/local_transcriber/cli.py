from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

from local_transcriber.engine import TranscriptionEngine
from local_transcriber.environment import write_environment_report
from local_transcriber.exporters import export_result
from local_transcriber.jobs import JobBusyError, JobStore
from local_transcriber.media import (
    MediaError,
    estimate_transcription_seconds,
    normalize_audio,
    probe_media,
)
from local_transcriber.models import MODEL_SPECS, pull_models, write_model_manifest
from local_transcriber.progress import ProgressEstimator
from local_transcriber.schema import (
    SUPPORTED_LANGUAGES,
    CanonicalResult,
    EngineInfo,
    JobInfo,
    Segment,
    SourceInfo,
    write_result,
)


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="local-transcriber")
    subparsers = parser.add_subparsers(dest="command", required=True)

    environment = subparsers.add_parser("environment", help="inspect the local runtime")
    environment_sub = environment.add_subparsers(dest="environment_command", required=True)
    probe = environment_sub.add_parser("probe", help="write a JSON environment report")
    probe.add_argument("--output", type=Path, required=True)

    models = subparsers.add_parser("models", help="manage model snapshots")
    models_sub = models.add_subparsers(dest="models_command", required=True)
    pull = models_sub.add_parser("pull", help="cache the pinned model snapshots")
    pull.add_argument("--cache-dir", type=Path, default=Path("var/cache/models"))
    pull.add_argument("--manifest", type=Path, default=Path("var/acceptance/models.json"))

    transcribe = subparsers.add_parser("transcribe", help="transcribe one local media file")
    transcribe.add_argument("input", type=Path)
    transcribe.add_argument("--output-dir", type=Path, required=True)
    transcribe.add_argument("--runtime-dir", type=Path, default=Path("var/work"))
    transcribe.add_argument("--cache-dir", type=Path, default=Path("var/cache/models"))
    transcribe.add_argument("--threads", type=_positive, default=2)
    transcribe.add_argument("--speakers", type=_positive)
    transcribe.add_argument(
        "--language",
        choices=tuple(sorted(SUPPORTED_LANGUAGES)),
        default="auto",
        help="language hint: auto, zh, en, yue, ja, ko (default: auto)",
    )
    transcribe.add_argument("--keep-normalized", action="store_true")

    job = subparsers.add_parser("job", help="inspect persisted transcription jobs")
    job_sub = job.add_subparsers(dest="job_command", required=True)
    status = job_sub.add_parser("status", help="read one job without starting a worker")
    status.add_argument("job_id")
    status.add_argument("--runtime-dir", type=Path, default=Path("var/work"))
    status.add_argument("--json", action="store_true", dest="as_json")

    export = subparsers.add_parser("export", help="derive a format from canonical JSON")
    export.add_argument("result", type=Path)
    export.add_argument("--format", choices=("md", "txt", "srt"), required=True)
    export.add_argument("--output", type=Path)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_engine(threads: int, speakers: int | None, language: str) -> EngineInfo:
    return EngineInfo(
        funasr_version=version("funasr"),
        asr_model=MODEL_SPECS["asr"].model_id,
        vad_model=MODEL_SPECS["vad"].model_id,
        speaker_model=MODEL_SPECS["speaker"].model_id,
        device="cpu",
        threads=threads,
        speakers=speakers,
        language=language,
    )


def _transcribe(args: argparse.Namespace) -> int:
    job_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    store = JobStore(args.runtime_dir)
    stored = store.create(job_id, str(args.input), args.output_dir)
    print(f"job started: {job_id}", file=sys.stderr, flush=True)
    work_dir = args.runtime_dir / job_id
    result_dir = args.output_dir / job_id
    normalized = work_dir / "normalized.wav"
    try:
        with store.worker(job_id):
            if not args.input.is_file():
                raise MediaError(f"input media does not exist: {args.input}")
            stored = store.transition(job_id, "running")
            store.update_progress(job_id, stage="probing", progress_percent=1)
            media = probe_media(args.input)
            low_seconds, high_seconds = estimate_transcription_seconds(media.duration_ms)
            now = datetime.now(UTC)
            print(
                "estimated completion: "
                f"{(now + timedelta(seconds=low_seconds)).isoformat(timespec='seconds')} to "
                f"{(now + timedelta(seconds=high_seconds)).isoformat(timespec='seconds')} "
                f"({low_seconds // 60}-{(high_seconds + 59) // 60} minutes)",
                file=sys.stderr,
                flush=True,
            )
            store.update_progress(job_id, stage="normalizing", progress_percent=3)
            normalize_audio(args.input, normalized, media.audio_stream_index)
            store.update_progress(job_id, stage="loading", progress_percent=5)
            engine = TranscriptionEngine(
                cache_dir=args.cache_dir,
                threads=args.threads,
                speakers=args.speakers,
                language=args.language,
            )
            store.update_progress(job_id, stage="vad", progress_percent=10)
            estimator = ProgressEstimator()

            def persist_progress(current: float, total: float) -> None:
                estimate = estimator.observe(current, total)
                store.update_progress(
                    job_id,
                    stage="transcribing",
                    progress_percent=estimate.progress_percent,
                    processed_units=estimate.processed_units,
                    total_units=estimate.total_units,
                    eta_low_seconds=estimate.eta_low_seconds,
                    eta_high_seconds=estimate.eta_high_seconds,
                    eta_confidence=estimate.confidence,
                )

            raw_segments = engine.transcribe(normalized, progress_callback=persist_progress)
            store.update_progress(job_id, stage="finalizing", progress_percent=95)
            segments = tuple(
                item if isinstance(item, Segment) else Segment(**item) for item in raw_segments
            )
            result = CanonicalResult(
                schema_version=1,
                source=SourceInfo(
                    path=str(args.input.resolve()),
                    size_bytes=args.input.stat().st_size,
                    sha256=_sha256(args.input),
                    duration_ms=media.duration_ms,
                ),
                engine=(
                    engine.info
                    if isinstance(getattr(engine, "info", None), EngineInfo)
                    else _default_engine(args.threads, args.speakers, args.language)
                ),
                job=JobInfo(
                    id=stored.id,
                    status="succeeded",
                    created_at=stored.created_at,
                    started_at=stored.started_at,
                    finished_at=datetime.now(UTC).isoformat(),
                    error=None,
                ),
                segments=segments,
            )
            result_path = result_dir / "result.json"
            write_result(result_path, result)
            exports = (
                ("md", "transcript.md"),
                ("txt", "transcript.txt"),
                ("srt", "transcript.srt"),
            )
            for format_name, filename in exports:
                export_result(result_path, result_dir / filename, format_name)
            (result_dir / "media.json").write_text(
                json.dumps(media.to_dict(), indent=2) + "\n", encoding="utf-8"
            )
            stored = store.transition(job_id, "succeeded")
            result = CanonicalResult(
                schema_version=result.schema_version,
                source=result.source,
                engine=result.engine,
                job=JobInfo(
                    id=stored.id,
                    status=stored.status,
                    created_at=stored.created_at,
                    started_at=stored.started_at,
                    finished_at=stored.finished_at,
                    error=stored.error,
                ),
                segments=result.segments,
            )
            write_result(result_path, result)
            if not args.keep_normalized:
                shutil.rmtree(work_dir, ignore_errors=True)
            print(result_path)
            return 0
    except KeyboardInterrupt:
        if stored.status in {"queued", "running"}:
            store.transition(job_id, "cancelled")
        print("transcription cancelled", file=sys.stderr)
        return 130
    except JobBusyError as exc:
        store.transition(job_id, "failed", error=str(exc))
        print(str(exc), file=sys.stderr)
        return 4
    except (MediaError, ValueError) as exc:
        if store.load(job_id).status in {"queued", "running"}:
            store.transition(job_id, "failed", error=str(exc))
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        if store.load(job_id).status in {"queued", "running"}:
            store.transition(job_id, "failed", error=str(exc))
        print(str(exc), file=sys.stderr)
        return 3


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "environment" and args.environment_command == "probe":
        report = write_environment_report(args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "models" and args.models_command == "pull":
        pull_models(args.cache_dir)
        manifest = write_model_manifest(args.manifest, args.cache_dir)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    if args.command == "transcribe":
        return _transcribe(args)
    if args.command == "job" and args.job_command == "status":
        try:
            stored = JobStore(args.runtime_dir, create=False).load(args.job_id)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        payload = asdict(stored)
        payload.pop("input_path", None)
        payload.pop("output_dir", None)
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            eta = "calculating"
            if stored.eta_low_seconds is not None and stored.eta_high_seconds is not None:
                eta = f"{stored.eta_low_seconds}-{stored.eta_high_seconds}s"
            print(
                f"{stored.id} {stored.status} {stored.stage} "
                f"{stored.progress_percent:.1f}% ETA {eta} (estimate)"
            )
        return 0
    if args.command == "export":
        destination = args.output or args.result.with_suffix(f".{args.format}")
        export_result(args.result, destination, args.format)
        print(destination)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
