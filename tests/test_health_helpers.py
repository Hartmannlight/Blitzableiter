from __future__ import annotations

from pathlib import Path

from app.config import AppConfig
from app.health import _check_metrics_health, _parse_last_iteration_timestamp


def make_config(metrics_enabled: bool = False) -> AppConfig:
    return AppConfig(
        service_name='test',
        env='test',
        log_level='INFO',
        metrics_enabled=metrics_enabled,
        metrics_port=8000,
        loop_sleep_seconds=1.0,
        version='0.0.0',
        commit='test',
        config_source=str(Path('test-config.yml')),
        instance='test-instance',
    )


def test_parse_last_iteration_timestamp_valid() -> None:
    body = 'app_last_iteration_timestamp_seconds 123.5\n'
    assert _parse_last_iteration_timestamp(body) == 123.5


def test_parse_last_iteration_timestamp_missing() -> None:
    body = 'some_other_metric 1\n'
    assert _parse_last_iteration_timestamp(body) is None


def test_parse_last_iteration_timestamp_invalid_value() -> None:
    body = 'app_last_iteration_timestamp_seconds not-a-number\n'
    assert _parse_last_iteration_timestamp(body) is None


def test_check_metrics_health_skipped_when_disabled() -> None:
    config = make_config(metrics_enabled=False)
    assert _check_metrics_health(config) is None
