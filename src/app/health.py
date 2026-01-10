from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.config import AppConfig, load_config
from app.health_state import check_heartbeat


def _check_health_file(config: AppConfig) -> str | None:
    return check_heartbeat(Path(config.health_file), config.loop_sleep_seconds)


def main() -> None:
    try:
        load_dotenv()
        config = load_config()
    except Exception as exc:  # noqa: BLE001
        payload: dict[str, Any] = {'status': 'error', 'error': str(exc)}
        print(json.dumps(payload), file=sys.stderr)
        sys.exit(1)

    health_error = _check_health_file(config)
    if health_error is not None:
        payload = {
            'status': 'error',
            'service': config.service_name,
            'env': config.env,
            'version': config.version,
            'commit': config.commit,
            'error': health_error,
            'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        }
        print(json.dumps(payload))
        sys.exit(1)

    payload = {
        'status': 'ok',
        'service': config.service_name,
        'env': config.env,
        'version': config.version,
        'commit': config.commit,
        'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
    }
    print(json.dumps(payload))
    sys.exit(0)


if __name__ == '__main__':
    main()
