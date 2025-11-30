# src/app/metrics.py
from __future__ import annotations

import logging
import time

from prometheus_client import Counter, Gauge, start_http_server

from app.config import AppConfig

log = logging.getLogger(__name__)

service_up = Gauge('app_up', 'Service status (1=up, 0=down)')
service_iterations_total = Counter('app_iterations_total', 'Total main loop iterations.')
service_last_iteration_timestamp_seconds = Gauge(
    'app_last_iteration_timestamp_seconds',
    'Unix timestamp of the last successful loop iteration.',
)
app_build_info = Gauge(
    'app_build_info',
    'Deployment identification.',
    ['version', 'commit', 'env'],
)


def start_metrics_server(config: AppConfig) -> None:
    if not config.metrics_enabled:
        log.info('Metrics disabled')
        return

    start_http_server(config.metrics_port)

    app_build_info.labels(
        version=config.version,
        commit=config.commit,
        env=config.env,
    ).set(1)

    service_up.set(1)

    log.info('Metrics server started', extra={'metrics_port': config.metrics_port})


def mark_iteration() -> None:
    now = time.time()
    service_iterations_total.inc()
    service_last_iteration_timestamp_seconds.set(now)


def mark_shutdown() -> None:
    service_up.set(0)
