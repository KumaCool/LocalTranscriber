from __future__ import annotations

import json
import os
import socket
import threading
from pathlib import Path

import pytest

from local_transcriber.ipc import IPCError, UnixIPCClient, UnixIPCServer, socket_path


def test_unix_ipc_round_trip_is_local_and_owner_only(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    server = UnixIPCServer(runtime, lambda request: {"ok": True, "batch_id": request["batch_id"]})
    thread = threading.Thread(target=server.serve_once)
    thread.start()
    try:
        response = UnixIPCClient(runtime).request({"action": "submit", "batch_id": "batch-1"})
    finally:
        thread.join(timeout=2)
        server.close()

    path = socket_path(runtime)
    assert response == {"ok": True, "batch_id": "batch-1"}
    assert path.exists()
    assert path.is_socket()
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(runtime).st_mode & 0o777 == 0o700


def test_ipc_rejects_oversized_or_non_object_requests(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    server = UnixIPCServer(runtime, lambda request: {"ok": True})
    thread = threading.Thread(target=server.serve_once)
    thread.start()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path(runtime)))
            client.sendall(json.dumps(["not", "an", "object"]).encode() + b"\n")
            payload = json.loads(client.makefile("rb").readline())
    finally:
        thread.join(timeout=2)
        server.close()

    assert payload["ok"] is False
    assert "object" in payload["error"]

    with pytest.raises(IPCError, match="not available"):
        UnixIPCClient(tmp_path / "missing").request({"action": "ping"})


def test_socket_path_falls_back_for_long_runtime_directory(tmp_path: Path) -> None:
    runtime = tmp_path / ("nested-" * 20)

    first = socket_path(runtime)
    second = socket_path(runtime)

    assert first == second
    assert len(os.fsencode(first)) <= 100
    assert first.parent == Path("/tmp")
    assert str(os.getuid()) in first.name
