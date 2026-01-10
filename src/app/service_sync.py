# C:\Users\Nathaniel\PycharmProjects\Python-Boilerplate\src\app\service_sync.py
from __future__ import annotations

import logging
from pathlib import Path
from threading import Event

from app.blitz_service import BlitzableiterService
from app.config import AppConfig
from app.health_state import write_heartbeat
from app.metrics import mark_iteration

log = logging.getLogger(__name__)


class Service:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._running = False
        self._engine = BlitzableiterService()
        self._stop_event = Event()

    def start(self) -> None:
        self._running = True
        self._stop_event.clear()
        try:
            write_heartbeat(Path(self._config.health_file))
        except Exception:  # noqa: BLE001
            log.exception('Failed to write initial health heartbeat')
        log.info('Service loop started')
        try:
            while True:
                if self._stop_event.is_set():
                    break
                try:
                    sleep_for = self.run_once()
                    mark_iteration()
                    try:
                        write_heartbeat(Path(self._config.health_file))
                    except Exception:  # noqa: BLE001
                        log.exception('Failed to write health heartbeat')
                except Exception:  # noqa: BLE001
                    log.exception('Error in service loop iteration')
                    sleep_for = self._config.loop_sleep_seconds
                if self._stop_event.is_set():
                    break
                if self._stop_event.wait(timeout=sleep_for):
                    break
        except KeyboardInterrupt:
            self.stop()
            raise

    def stop(self) -> None:
        log.info('Service loop stopping')
        self._running = False
        self._stop_event.set()

    def run_once(self) -> float:
        log.debug('Service iteration')
        return self._engine.run_cycle()
