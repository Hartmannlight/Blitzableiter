# src/app/main_async.py
from __future__ import annotations

import asyncio
import logging
import signal
import sys

from dotenv import load_dotenv

from app.config import load_config
from app.logging_setup import configure_logging
from app.metrics import mark_shutdown, start_metrics_server
from app.service_async import AsyncService

log = logging.getLogger(__name__)


async def run_service() -> None:
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
    service = AsyncService(config)

    loop = asyncio.get_running_loop()

    def handle_signal() -> None:
        log.info(
            'Shutting down',
            extra={'event': 'shutting_down', 'reason': 'signal'},
        )
        service.stop()
        mark_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            pass

    try:
        await service.start()
    except asyncio.CancelledError:
        # Normal cancellation (e.g. Ctrl+C) -> kein Crash-Log
        pass
    except Exception:  # noqa: BLE001
        log.exception(
            'Application crashed',
            extra={'event': 'crashed'},
        )
        mark_shutdown()
        sys.exit(1)


def main() -> None:
    load_dotenv()
    try:
        asyncio.run(run_service())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
