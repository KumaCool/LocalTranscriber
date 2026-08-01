from __future__ import annotations

from pathlib import Path


def test_systemd_worker_template_is_local_without_overriding_user_resource_policy() -> None:
    unit = Path("packaging/systemd/local-transcriber-worker.service").read_text()

    assert "local-transcriber worker run" in unit
    assert "Restart=on-failure" in unit
    assert "UMask=0077" in unit
    assert "PrivateTmp=yes" in unit
    assert "RestrictAddressFamilies=AF_UNIX" in unit
    assert "CPUQuota=" not in unit
    assert "MemoryHigh=" not in unit
    assert "http" not in unit.lower()
    assert "nohup" not in unit and " &" not in unit
