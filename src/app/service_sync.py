# C:\Users\Nathaniel\PycharmProjects\Python-Boilerplate\src\app\service_sync.py
from __future__ import annotations

import logging
import time

from app.config import AppConfig
from app.metrics import mark_iteration

log = logging.getLogger(__name__)


class Service:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._running = False

    def start(self) -> None:
        self._running = True
        log.info('Service loop started')
        while self._running:
            try:
                self.run_once()
                mark_iteration()
            except Exception:  # noqa: BLE001
                log.exception('Error in service loop iteration')
            time.sleep(self._config.loop_sleep_seconds)

    def stop(self) -> None:
        log.info('Service loop stopping')
        self._running = False

    def run_once(self) -> None:
        log.debug('Service iteration')
