# Python-Boilerplate/tests/test_metrics.py
from __future__ import annotations

from app.config import AppConfig
from app.metrics import mark_iteration, mark_shutdown, start_metrics_server


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
        config_source='test',
        instance='test-instance',
    )


def test_metrics_functions_do_not_crash() -> None:
    config = make_config(metrics_enabled=False)
    start_metrics_server(config)
    mark_iteration()
    mark_shutdown()
