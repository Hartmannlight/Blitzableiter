# C:\Users\Nathaniel\PycharmProjects\Python-Boilerplate\src\app\main_sync.py
from __future__ import annotations

import logging
import signal
import sys

from dotenv import load_dotenv

from app.config import load_config
from app.logging_setup import configure_logging
from app.metrics import mark_shutdown, start_metrics_server
from app.service_sync import Service

log = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()
    config = load_config()
    configure_logging(config)

    log.info(
        'Service startup succeeded',
        extra={
            'event': 'startup_success',
            'version': config.version,
            'commit': config.commit,
            'config_source': config.config_source,
        },
    )

    start_metrics_server(config)
    service = Service(config)

    def handle_signal(signum: int, frame: object | None) -> None:
        if signum == signal.SIGINT:
            reason = 'SIGINT'
        elif signum == signal.SIGTERM:
            reason = 'SIGTERM'
        else:
            reason = 'signal'

        log.info(
            'Shutting down',
            extra={
                'event': 'shutting_down',
                'reason': reason,
                'signal': signum,
            },
        )
        service.stop()
        mark_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handle_signal)
        except Exception:  # noqa: BLE001
            pass

    try:
        service.start()
    except KeyboardInterrupt:
        handle_signal(signal.SIGINT, None)
    except Exception:  # noqa: BLE001
        log.exception(
            'Application crashed',
            extra={'event': 'crashed'},
        )
        mark_shutdown()
        sys.exit(1)


if __name__ == '__main__':
    main()
