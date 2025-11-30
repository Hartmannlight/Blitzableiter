from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from app.config import AppConfig, load_config


def _parse_last_iteration_timestamp(text: str) -> float | None:
    for line in text.splitlines():
        if line.startswith('app_last_iteration_timestamp_seconds'):
            parts = line.split()
            if len(parts) == 2:
                try:
                    return float(parts[1])
                except ValueError:
                    return None
    return None


def _check_metrics_health(config: AppConfig) -> str | None:
    if not config.metrics_enabled:
        return None

    import urllib.error
    import urllib.request

    url = f'http://127.0.0.1:{config.metrics_port}/metrics'
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            body_bytes = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        return f'cannot reach metrics endpoint: {exc}'

    body = body_bytes.decode('utf-8', errors='replace')
    last_ts = _parse_last_iteration_timestamp(body)
    if last_ts is None:
        return 'metric app_last_iteration_timestamp_seconds not found'

    now = time.time()
    age = now - last_ts
    max_age = max(30.0, 3.0 * config.loop_sleep_seconds)

    if age > max_age:
        return f'last iteration too old: age={age:.1f}s, max={max_age:.1f}s'

    return None


def main() -> None:
    try:
        load_dotenv()
        config = load_config()
    except Exception as exc:  # noqa: BLE001
        payload: dict[str, Any] = {'status': 'error', 'error': str(exc)}
        print(json.dumps(payload), file=sys.stderr)
        sys.exit(1)

    metrics_error = _check_metrics_health(config)
    if metrics_error is not None:
        payload = {
            'status': 'error',
            'service': config.service_name,
            'env': config.env,
            'version': config.version,
            'commit': config.commit,
            'error': metrics_error,
            'timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        }
        print(json.dumps(payload))
        sys.exit(1)

    payload = {
        'status': 'ok',
        'service': config.service_name,
        'env': config.env,
        'version': config.version,
        'commit': config.commit,
        'timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
    }
    print(json.dumps(payload))
    sys.exit(0)


if __name__ == '__main__':
    main()
