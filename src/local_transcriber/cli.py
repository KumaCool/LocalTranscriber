from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from local_transcriber.batches import BatchStore
from local_transcriber.config import ResourceConfig
from local_transcriber.console import ForegroundConsole
from local_transcriber.daemon import BackgroundManager, service_control
from local_transcriber.discovery import (
    DiscoveredInput,
    discover_directory,
    discover_explicit,
    output_path_for,
)
from local_transcriber.environment import write_environment_report
from local_transcriber.executor import ExecutorOptions
from local_transcriber.exporters import export_result
from local_transcriber.ipc import IPCError, UnixIPCClient
from local_transcriber.jobs import JobStore
from local_transcriber.models import pull_models, write_model_manifest
from local_transcriber.resources import ResourceSnapshot, calculate_budget
from local_transcriber.scheduler import BoundedScheduler
from local_transcriber.schema import SUPPORTED_LANGUAGES


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _add_transcription_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, default=Path("var/work"))
    parser.add_argument("--cache-dir", type=Path, default=Path("var/cache/models"))
    parser.add_argument("--threads", type=_positive, default=2)
    parser.add_argument("--speakers", type=_positive)
    parser.add_argument(
        "--language",
        choices=tuple(sorted(SUPPORTED_LANGUAGES)),
        default="auto",
        help="language hint: auto, zh, en, yue, ja, ko (default: auto)",
    )
    parser.add_argument("--keep-normalized", action="store_true")
    parser.add_argument("--bg", action="store_true", help="submit to the local background manager")
    parser.add_argument("--json", action="store_true", dest="as_json")


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

    transcribe = subparsers.add_parser("transcribe", help="transcribe local media files")
    transcribe.add_argument("inputs", type=Path, nargs="+")
    _add_transcription_options(transcribe)
    transcribe.add_argument("--max-workers", type=_positive, default=1)

    transcribe_dir = subparsers.add_parser(
        "transcribe-dir", help="discover and transcribe media in a directory"
    )
    transcribe_dir.add_argument("directory", type=Path)
    transcribe_dir.add_argument("--recursive", action="store_true")
    transcribe_dir.add_argument("--dry-run", action="store_true")

    _add_transcription_options(transcribe_dir)
    transcribe_dir.add_argument("--max-workers", type=_positive, default=1)

    job = subparsers.add_parser("job", help="inspect or control persisted transcription jobs")
    job_sub = job.add_subparsers(dest="job_command", required=True)
    for action in ("status", "cancel", "retry"):
        command = job_sub.add_parser(action)
        command.add_argument("job_id")
        command.add_argument("--runtime-dir", type=Path, default=Path("var/work"))
        command.add_argument("--json", action="store_true", dest="as_json")

    batch = subparsers.add_parser(
        "batch", help="inspect or control persisted transcription batches"
    )
    batch_sub = batch.add_subparsers(dest="batch_command", required=True)
    for action in ("status", "cancel", "retry"):
        command = batch_sub.add_parser(action)
        command.add_argument("batch_id")
        command.add_argument("--runtime-dir", type=Path, default=Path("var/work"))
        command.add_argument("--json", action="store_true", dest="as_json")

    worker = subparsers.add_parser("worker", help="manage the local background worker")
    worker_sub = worker.add_subparsers(dest="worker_command", required=True)
    for action in ("run", "start", "status", "stop", "restart"):
        worker_action = worker_sub.add_parser(action)
        worker_action.add_argument("--runtime-dir", type=Path, default=Path("var/work"))
        worker_action.add_argument("--json", action="store_true", dest="as_json")

    export = subparsers.add_parser("export", help="derive a format from canonical JSON")
    export.add_argument("result", type=Path)
    export.add_argument("--format", choices=("md", "txt", "srt"), required=True)
    export.add_argument("--output", type=Path)
    return parser


def _new_id(prefix: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _batch_exit_code(codes: list[int]) -> int:
    for code in (4, 130, 3, 2):
        if code in codes:
            return code
    return 0


def _transcribe(
    args: argparse.Namespace,
    *,
    input_order: int = 0,
    discovered_input: DiscoveredInput | None = None,
) -> int:
    job_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    result_dir = (
        output_path_for(args.output_dir, discovered_input, job_id)
        if discovered_input is not None
        else args.output_dir / job_id
    )
    snapshot = ResourceSnapshot.capture()
    worker_peak = min(3 * 1024**3, max(1, snapshot.available_memory_bytes))
    config = ResourceConfig(max_workers=args.max_workers, threads_per_worker=args.threads)
    budget = calculate_budget(config, snapshot, worker_peak_rss_bytes=worker_peak)
    if budget.rejection_reason:
        print(budget.rejection_reason, file=sys.stderr)
        return 4
    batch_id = _new_id("batch")
    JobStore(args.runtime_dir).create(
        job_id,
        str(args.input.resolve()),
        result_dir,
        batch_id=batch_id,
        input_order=input_order,
        effective_budget=budget.to_dict(),
    )
    BatchStore(args.runtime_dir).create(
        batch_id,
        task_ids=(job_id,),
        run_mode="foreground",
        effective_budget=budget.to_dict(),
        output_dir=args.output_dir,
    )
    print(f"job started: {job_id}", file=sys.stderr, flush=True)
    try:
        report = BoundedScheduler(args.runtime_dir).run_batch(
            batch_id,
            ExecutorOptions(
                cache_dir=args.cache_dir,
                threads=budget.threads_per_worker,
                speakers=args.speakers,
                language=args.language,
                keep_normalized=args.keep_normalized,
            ),
        )
    except Exception as exc:
        current = JobStore(args.runtime_dir).load(job_id)
        if current.status in {"queued", "running"}:
            JobStore(args.runtime_dir).transition(job_id, "failed", error=str(exc))
        print(str(exc), file=sys.stderr)
        return 4
    outcome = report.outcomes[job_id]
    if outcome.result_path is not None:
        print(outcome.result_path)
    if outcome.error:
        print(outcome.error, file=sys.stderr)
    return outcome.exit_code


def _discovery_payload(result) -> dict[str, object]:
    return {
        "accepted": [
            {
                "path": str(item.path),
                "relative_path": item.relative_path.as_posix(),
                "input_order": item.input_order,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
                "duration_ms": item.media.duration_ms,
            }
            for item in result.accepted
        ],
        "skipped": [
            {"path": str(item.path), "reason": item.reason, "detail": item.detail}
            for item in result.skipped
        ],
    }


def _run_discovered(args: argparse.Namespace, result) -> int:
    if not result.accepted:
        invalid = next((item for item in result.skipped if item.reason == "invalid_media"), None)
        if invalid is not None:
            args.input = invalid.path
            return _transcribe(args)
        print("no supported media inputs found", file=sys.stderr)
        return 2

    snapshot = ResourceSnapshot.capture()
    worker_peak = min(3 * 1024**3, max(1, snapshot.available_memory_bytes))
    config = ResourceConfig(max_workers=args.max_workers, threads_per_worker=args.threads)
    budget = calculate_budget(config, snapshot, worker_peak_rss_bytes=worker_peak)
    if budget.rejection_reason:
        print(budget.rejection_reason, file=sys.stderr)
        return 4
    batch_id = _new_id("batch")
    run_mode = "background" if args.bg else "foreground"
    store = JobStore(args.runtime_dir)
    task_ids: list[str] = []
    for item in result.accepted:
        job_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        task_ids.append(job_id)
        store.create(
            job_id,
            str(item.path.resolve()),
            output_path_for(args.output_dir, item, job_id),
            batch_id=batch_id,
            run_mode=run_mode,
            input_order=item.input_order,
            effective_budget=budget.to_dict(),
        )
        print(f"job started: {job_id}", file=sys.stderr, flush=True)
    BatchStore(args.runtime_dir).create(
        batch_id,
        task_ids=tuple(task_ids),
        run_mode=run_mode,
        effective_budget=budget.to_dict(),
        output_dir=args.output_dir,
        execution_options={
            "cache_dir": str(args.cache_dir),
            "threads": budget.threads_per_worker,
            "speakers": args.speakers,
            "language": args.language,
            "keep_normalized": args.keep_normalized,
        },
    )
    if args.bg:
        request: dict[str, object] = {
            "action": "submit",
            "batch_id": batch_id,
            "cache_dir": str(args.cache_dir),
            "threads": budget.threads_per_worker,
            "speakers": args.speakers,
            "language": args.language,
            "keep_normalized": args.keep_normalized,
        }
        client = UnixIPCClient(args.runtime_dir)
        try:
            response = client.request(request)
        except IPCError as first_error:
            started = service_control("start", args.runtime_dir)
            if started.get("ok") is not True:
                print(
                    f"background batch not submitted: {started.get('error', str(first_error))}",
                    file=sys.stderr,
                )
                return 4
            deadline = time.monotonic() + 2.0
            while True:
                try:
                    response = client.request(request)
                    break
                except IPCError as exc:
                    if time.monotonic() >= deadline:
                        print(f"background batch not submitted: {exc}", file=sys.stderr)
                        return 4
                    time.sleep(0.05)
        if response.get("ok") is not True:
            error = response.get("error", "manager rejected request")
            print(
                f"background batch not submitted: {error}",
                file=sys.stderr,
            )
            return 4
        payload = {
            "mode": "background",
            "batch_id": batch_id,
            "task_ids": task_ids,
            "status_command": f"local-transcriber batch status {batch_id}",
        }
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"background batch submitted: {batch_id}; status: {payload['status_command']}")
        return 0
    console = ForegroundConsole(args.runtime_dir, batch_id)
    try:
        report = BoundedScheduler(args.runtime_dir).run_batch(
            batch_id,
            ExecutorOptions(
                cache_dir=args.cache_dir,
                threads=budget.threads_per_worker,
                speakers=args.speakers,
                language=args.language,
                keep_normalized=args.keep_normalized,
            ),
            progress_callback=lambda _batch, _jobs: console.refresh(),
        )
    except KeyboardInterrupt:
        job_store = JobStore(args.runtime_dir)
        for task_id in task_ids:
            current = job_store.load(task_id)
            if current.status in {"queued", "running"}:
                job_store.transition(task_id, "cancelled")
        BatchStore(args.runtime_dir).aggregate(
            batch_id,
            {task_id: job_store.load(task_id).status for task_id in task_ids},
        )
        console.finish()
        print(f"batch {batch_id} cancelled", file=sys.stderr)
        return 130
    except Exception as exc:
        console.finish()
        print(str(exc), file=sys.stderr)
        return 4
    console.finish()
    exit_codes: list[int] = []
    for task_id in task_ids:
        outcome = report.outcomes[task_id]
        if outcome.result_path is not None:
            print(outcome.result_path)
        if outcome.error:
            print(outcome.error, file=sys.stderr)
        exit_codes.append(outcome.exit_code)
    final = BatchStore(args.runtime_dir).load(batch_id)
    print(
        f"summary batch={batch_id} status={final.status} total={len(task_ids)} "
        f"succeeded={final.succeeded_count} failed={final.failed_count + final.interrupted_count} "
        f"cancelled={final.cancelled_count} skipped={final.skipped_count}",
        file=sys.stderr,
    )
    return _batch_exit_code(exit_codes)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    parser = _parser()
    if any(argument.startswith("—") for argument in arguments):
        parser.error("Unicode long-dash options are not supported")
    args = parser.parse_args(arguments)
    if args.command == "environment" and args.environment_command == "probe":
        report = write_environment_report(args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "models" and args.models_command == "pull":
        pull_models(args.cache_dir)
        manifest = write_model_manifest(args.manifest, args.cache_dir)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    if args.command == "worker":
        if args.worker_command == "run":
            manager = BackgroundManager(args.runtime_dir)
            try:
                manager.run()
            finally:
                manager.close()
            return 0
        result = service_control(args.worker_command, args.runtime_dir)
        if args.as_json:
            print(json.dumps(result, ensure_ascii=False))
        elif result.get("ok"):
            print(f"worker {args.worker_command}: ok")
        else:
            print(str(result.get("error", "worker command failed")), file=sys.stderr)
        return 0 if result.get("ok") else 4
    if args.command == "transcribe":
        result = discover_explicit(args.inputs)
        return _run_discovered(args, result)
    if args.command == "transcribe-dir":
        try:
            result = discover_directory(
                args.directory,
                recursive=args.recursive,
                excluded_roots=(args.runtime_dir, args.output_dir, args.cache_dir),
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if args.dry_run:
            payload = _discovery_payload(result)
            if args.as_json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"accepted: {len(result.accepted)}, skipped: {len(result.skipped)}")
                for item in result.accepted:
                    print(item.relative_path.as_posix())
            return 0 if result.accepted else 2
        return _run_discovered(args, result)
    if args.command in {"job", "batch"}:
        kind = args.command
        action = args.job_command if kind == "job" else args.batch_command
        item_id = args.job_id if kind == "job" else args.batch_id
        if action != "status":
            request = {"action": f"{action}_{kind}", f"{kind}_id": item_id}
            try:
                response = UnixIPCClient(args.runtime_dir).request(request)
            except IPCError as exc:
                print(f"background manager action failed: {exc}", file=sys.stderr)
                return 4
            if response.get("ok") is not True:
                print(str(response.get("error", "manager rejected request")), file=sys.stderr)
                return 2
            if args.as_json:
                print(json.dumps(response, ensure_ascii=False, indent=2))
            else:
                print(f"{kind} {action}: ok")
            return 0
        try:
            stored = (
                JobStore(args.runtime_dir, create=False).load(item_id)
                if kind == "job"
                else BatchStore(args.runtime_dir, create=False).load(item_id)
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        payload = asdict(stored)
        payload.pop("input_path", None)
        payload.pop("output_dir", None)
        payload.pop("artifact_paths", None)
        payload.pop("execution_options", None)
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif kind == "batch":
            completed = f"{payload['completed_count']}/{len(payload['task_ids'])}"
            failed = payload["failed_count"] + payload["interrupted_count"]
            print(
                f"{payload['id']} {payload['status']} completed={completed} "
                f"succeeded={payload['succeeded_count']} failed={failed} "
                f"cancelled={payload['cancelled_count']}"
            )
        else:
            eta = "calculating"
            if payload["eta_low_seconds"] is not None and payload["eta_high_seconds"] is not None:
                eta = f"{payload['eta_low_seconds']}-{payload['eta_high_seconds']}s"
            print(
                f"{payload['id']} {payload['status']} {payload['stage']} "
                f"{payload['progress_percent']:.1f}% ETA {eta} (estimate)"
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
