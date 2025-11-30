# C:\Users\Nathaniel\PycharmProjects\Python-Boilerplate\src\app\service_async.py
from __future__ import annotations

import asyncio
import logging

from app.config import AppConfig
from app.metrics import mark_iteration

log = logging.getLogger(__name__)


class AsyncService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._running = True

    async def start(self) -> None:
        self._running = True
        log.info('Async service loop started')
        while self._running:
            try:
                await self.run_once()
                mark_iteration()
            except Exception:  # noqa: BLE001
                log.exception('Error in async service loop iteration')
            await asyncio.sleep(self._config.loop_sleep_seconds)

    def stop(self) -> None:
        log.info('Async service loop stopping')
        self._running = False

    async def run_once(self) -> None:
        log.debug('Async service iteration')
