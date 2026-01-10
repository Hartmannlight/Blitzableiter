# src/app/metrics.py
from __future__ import annotations

import logging
import time

from prometheus_client import Counter, Gauge, Histogram

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
api_requests_total = Counter(
    'blitzableiter_api_requests_total',
    'Total API requests to external POI sources.',
    ['source', 'status'],
)
api_request_duration_seconds = Histogram(
    'blitzableiter_api_request_duration_seconds',
    'Duration of API requests to external POI sources.',
    ['source'],
)
pois_seen_total = Counter(
    'blitzableiter_pois_seen_total',
    'Number of POIs observed in raw responses.',
    ['source'],
)
pois_new_total = Counter(
    'blitzableiter_pois_new_total',
    'Number of POIs considered new or reappeared.',
    ['source'],
)
pois_active_current = Gauge(
    'blitzableiter_pois_active_current',
    'Current active POIs by source.',
    ['source'],
)
notifications_sent_total = Counter(
    'blitzableiter_notifications_sent_total',
    'Notifications sent by sender and type.',
    ['sender', 'type', 'success'],
)
raw_snapshots_stored_total = Counter(
    'blitzableiter_raw_snapshots_stored_total',
    'Raw API snapshots stored (deduplicated).',
    ['source'],
)
reminders_pending_total = Gauge(
    'blitzableiter_reminders_pending_total',
    'Reminders pending execution.',
)


def start_metrics_server(config: AppConfig) -> None:
    if not config.metrics_enabled:
        log.info('Metrics disabled')
        return

    app_build_info.labels(
        version=config.version,
        commit=config.commit,
        env=config.env,
    ).set(1)

    service_up.set(1)

    log.info('Metrics enabled (no HTTP server)')


def mark_iteration() -> None:
    now = time.time()
    service_iterations_total.inc()
    service_last_iteration_timestamp_seconds.set(now)


def mark_shutdown() -> None:
    service_up.set(0)


def mark_api_request_success(source: str) -> None:
    api_requests_total.labels(source=source, status='success').inc()


def mark_api_request_failure(source: str) -> None:
    api_requests_total.labels(source=source, status='error').inc()


def mark_api_request_duration(source: str, duration_seconds: float) -> None:
    api_request_duration_seconds.labels(source=source).observe(duration_seconds)


def mark_pois_seen(source: str) -> None:
    pois_seen_total.labels(source=source).inc()


def mark_new_poi(source: str) -> None:
    pois_new_total.labels(source=source).inc()


def mark_active_pois(source: str, count: int) -> None:
    pois_active_current.labels(source=source).set(count)


def mark_notification_result(sender: str, notification_type: str, success: bool) -> None:
    notifications_sent_total.labels(
        sender=sender,
        type=notification_type,
        success='true' if success else 'false',
    ).inc()


def mark_raw_snapshot_stored(source: str) -> None:
    raw_snapshots_stored_total.labels(source=source).inc()


def mark_reminders_pending(count: int) -> None:
    reminders_pending_total.set(count)
