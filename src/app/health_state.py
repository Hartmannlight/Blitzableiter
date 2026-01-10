from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, cast


def write_heartbeat(path: Path, status: str = 'ok', now: float | None = None) -> None:
    payload: dict[str, Any] = {
        'timestamp': float(now if now is not None else time.time()),
        'status': status,
        'pid': os.getpid(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(json.dumps(payload), encoding='utf-8')
    tmp_path.replace(path)


def check_heartbeat(path: Path, loop_sleep_seconds: float, now: float | None = None) -> str | None:
    if not path.exists():
        return f'health file missing: {path}'

    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        return f'health file unreadable: {exc}'

    if not isinstance(payload, dict):
        return 'health file payload invalid'

    payload_dict = cast(dict[str, Any], payload)
    status = payload_dict.get('status', 'ok')
    if status != 'ok':
        return f'health status is {status}'

    timestamp = payload_dict.get('timestamp')
    if not isinstance(timestamp, int | float | str):
        return 'health file timestamp invalid'

    try:
        last_ts = float(timestamp)
    except ValueError:
        return 'health file timestamp invalid'

    current = float(now if now is not None else time.time())
    age = current - last_ts
    max_age = max(30.0, 3.0 * loop_sleep_seconds)
    if age > max_age:
        return f'last iteration too old: age={age:.1f}s, max={max_age:.1f}s'

    return None
