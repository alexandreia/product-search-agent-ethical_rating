"""Heartbeat writer for exposing current agent status."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HeartbeatWriter:
    """Writes a small status file during and after agent runs."""

    def __init__(self, path: str | Path = "heartbeat/heartbeat.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, status: str, **fields: Any) -> None:
        payload = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

