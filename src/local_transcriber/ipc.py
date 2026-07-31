from __future__ import annotations

import json
import os
import socket
import struct
from collections.abc import Callable
from pathlib import Path

_MAX_MESSAGE_BYTES = 64 * 1024


class IPCError(RuntimeError):
    pass


def socket_path(runtime_dir: Path) -> Path:
    return runtime_dir / "worker.sock"


class UnixIPCServer:
    def __init__(
        self,
        runtime_dir: Path,
        handler: Callable[[dict[str, object]], dict[str, object]],
    ) -> None:
        self.runtime_dir = runtime_dir
        self.handler = handler
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.runtime_dir, 0o700)
        self.path = socket_path(runtime_dir)
        self.path.unlink(missing_ok=True)
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.bind(str(self.path))
        os.chmod(self.path, 0o600)
        self._socket.listen(16)

    @staticmethod
    def _peer_uid(connection: socket.socket) -> int:
        credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        _pid, uid, _gid = struct.unpack("3i", credentials)
        return uid

    def serve_once(self) -> None:
        connection, _ = self._socket.accept()
        with connection:
            if self._peer_uid(connection) != os.getuid():
                response: dict[str, object] = {"ok": False, "error": "peer uid rejected"}
            else:
                try:
                    line = connection.makefile("rb").readline(_MAX_MESSAGE_BYTES + 1)
                    if not line or len(line) > _MAX_MESSAGE_BYTES:
                        raise IPCError("invalid IPC message size")
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise IPCError("IPC request must be an object")
                    response = self.handler(request)
                except (IPCError, json.JSONDecodeError) as exc:
                    response = {"ok": False, "error": str(exc)}
            connection.sendall(json.dumps(response, ensure_ascii=False).encode() + b"\n")

    def close(self) -> None:
        self._socket.close()


class UnixIPCClient:
    def __init__(self, runtime_dir: Path, *, timeout: float = 2.0) -> None:
        self.path = socket_path(runtime_dir)
        self.timeout = timeout

    def request(self, request: dict[str, object]) -> dict[str, object]:
        payload = json.dumps(request, ensure_ascii=False).encode() + b"\n"
        if len(payload) > _MAX_MESSAGE_BYTES:
            raise IPCError("IPC request is too large")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(self.timeout)
                client.connect(str(self.path))
                client.sendall(payload)
                line = client.makefile("rb").readline(_MAX_MESSAGE_BYTES + 1)
        except (FileNotFoundError, ConnectionRefusedError, TimeoutError, OSError) as exc:
            raise IPCError("background manager is not available") from exc
        if not line or len(line) > _MAX_MESSAGE_BYTES:
            raise IPCError("invalid IPC response")
        response = json.loads(line)
        if not isinstance(response, dict):
            raise IPCError("IPC response must be an object")
        return response
