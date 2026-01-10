from __future__ import annotations

import json
import logging
import sys

from app.config import AppConfig
from app.logging_setup import JsonFormatter, configure_logging


def _config(log_level: str = 'INFO') -> AppConfig:
    return AppConfig(
        service_name='svc',
        env='test',
        log_level=log_level,
        metrics_enabled=False,
        metrics_port=8000,
        loop_sleep_seconds=1.0,
        health_file='test-health.json',
        version='0.0.0',
        commit='test',
        config_source='test',
        instance='unit',
    )


def test_json_formatter_includes_extras_and_error() -> None:
    formatter = JsonFormatter(_config())
    record = logging.LogRecord(
        name='test',
        level=logging.ERROR,
        pathname=__file__,
        lineno=10,
        msg='boom',
        args=(),
        exc_info=None,
    )
    record.request_id = 'abc'
    text = formatter.format(record)
    payload = json.loads(text)

    assert payload['level'] == 'error'
    assert payload['msg'] == 'boom'
    assert payload['request_id'] == 'abc'
    assert payload['error'] == 'boom'


def test_json_formatter_includes_exception() -> None:
    formatter = JsonFormatter(_config())
    try:
        raise ValueError('bad')
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name='test',
        level=logging.ERROR,
        pathname=__file__,
        lineno=20,
        msg='fail',
        args=(),
        exc_info=exc_info,
    )
    text = formatter.format(record)
    payload = json.loads(text)

    assert 'stack' in payload
    assert payload['exception_type'] == 'ValueError'


def test_configure_logging_sets_root_handler() -> None:
    config = _config(log_level='WARNING')
    configure_logging(config)

    root = logging.getLogger()
    assert root.level == logging.WARNING
    assert len(root.handlers) == 1
