from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

from local_transcriber.engine import TranscriptionEngine
from local_transcriber.exporters import export_result
from local_transcriber.jobs import JobStore
from local_transcriber.media import (
    MediaError,
    estimate_transcription_seconds,
    normalize_audio,
    probe_media,
)
from local_transcriber.models import MODEL_SPECS
from local_transcriber.progress import ProgressEstimator
from local_transcriber.schema import (
    CanonicalResult,
    EngineInfo,
    JobInfo,
    Segment,
    SourceInfo,
    write_result,
)


@dataclass(frozen=True)
class ExecutorOptions:
    cache_dir: Path
    threads: int = 2
    speakers: int | None = None
    language: str = "auto"
    keep_normalized: bool = False


@dataclass(frozen=True)
class ExecutionOutcome:
    job_id: str
    status: str
    exit_code: int
    result_path: Path | None = None
    error: str | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_engine(options: ExecutorOptions) -> EngineInfo:
    return EngineInfo(
        funasr_version=version("funasr"),
        asr_model=MODEL_SPECS["asr"].model_id,
        vad_model=MODEL_SPECS["vad"].model_id,
        speaker_model=MODEL_SPECS["speaker"].model_id,
        device="cpu",
        threads=options.threads,
        speakers=options.speakers,
        language=options.language,
    )


def execute_job(
    job_id: str,
    runtime_dir: Path,
    options: ExecutorOptions,
    *,
    cancel_event=None,
) -> ExecutionOutcome:
    store = JobStore(runtime_dir)
    stored = store.load(job_id)
    source = Path(stored.input_path)
    result_dir = Path(stored.output_dir)
    work_dir = runtime_dir / job_id
    normalized = work_dir / "normalized.wav"
    try:
        if cancel_event is not None and cancel_event.is_set():
            store.transition(job_id, "cancelled")
            return ExecutionOutcome(job_id, "cancelled", 130)
        if not source.is_file():
            raise MediaError(f"input media does not exist: {source}")
        stored = store.transition(job_id, "running")
        store.update_progress(job_id, stage="probing", progress_percent=1)
        media = probe_media(source)
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
        normalize_audio(source, normalized, media.audio_stream_index)
        if cancel_event is not None and cancel_event.is_set():
            store.transition(job_id, "cancelled")
            return ExecutionOutcome(job_id, "cancelled", 130)
        store.update_progress(job_id, stage="loading", progress_percent=5)
        engine = TranscriptionEngine(
            cache_dir=options.cache_dir,
            threads=options.threads,
            speakers=options.speakers,
            language=options.language,
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
        if cancel_event is not None and cancel_event.is_set():
            store.transition(job_id, "cancelled")
            return ExecutionOutcome(job_id, "cancelled", 130)
        store.update_progress(job_id, stage="finalizing", progress_percent=95)
        segments = tuple(
            item if isinstance(item, Segment) else Segment(**item) for item in raw_segments
        )
        result = CanonicalResult(
            schema_version=1,
            source=SourceInfo(
                path=str(source.resolve()),
                size_bytes=source.stat().st_size,
                sha256=_sha256(source),
                duration_ms=media.duration_ms,
            ),
            engine=(
                engine.info
                if isinstance(getattr(engine, "info", None), EngineInfo)
                else _default_engine(options)
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
        artifacts = {
            "result": str(result_path),
            "markdown": str(result_dir / "transcript.md"),
            "text": str(result_dir / "transcript.txt"),
            "srt": str(result_dir / "transcript.srt"),
            "media": str(result_dir / "media.json"),
        }
        for format_name, key in (("md", "markdown"), ("txt", "text"), ("srt", "srt")):
            export_result(result_path, Path(artifacts[key]), format_name)
        Path(artifacts["media"]).write_text(
            json.dumps(media.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
        store.update_artifacts(job_id, artifacts)
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
        if not options.keep_normalized:
            shutil.rmtree(work_dir, ignore_errors=True)
        return ExecutionOutcome(job_id, "succeeded", 0, result_path=result_path)
    except KeyboardInterrupt:
        if store.load(job_id).status in {"queued", "running"}:
            store.transition(job_id, "cancelled")
        return ExecutionOutcome(job_id, "cancelled", 130, error="transcription cancelled")
    except (MediaError, ValueError) as exc:
        if store.load(job_id).status in {"queued", "running"}:
            store.transition(job_id, "failed", error=str(exc))
        return ExecutionOutcome(job_id, "failed", 2, error=str(exc))
    except Exception as exc:
        if store.load(job_id).status in {"queued", "running"}:
            store.transition(job_id, "failed", error=str(exc))
        return ExecutionOutcome(job_id, "failed", 3, error=str(exc))
