from __future__ import annotations

import json
import logging
import sys
from dataclasses import fields

from app.config import AppConfig
from app.logging_setup import JsonFormatter


def make_config() -> AppConfig:
    return AppConfig(
        service_name='test-service',
        env='test',
        log_level='INFO',
        metrics_enabled=False,
        metrics_port=8000,
        loop_sleep_seconds=1.0,
        version='0.0.0',
        commit='test',
        config_source='test',
        instance='test-instance',
    )


def test_appconfig_has_required_fields() -> None:
    required_fields = {
        'service_name',
        'env',
        'log_level',
        'metrics_enabled',
        'metrics_port',
        'loop_sleep_seconds',
        'version',
        'commit',
        'config_source',
        'instance',
    }
    names = {f.name for f in fields(AppConfig)}
    assert required_fields.issubset(names)


def test_json_formatter_includes_required_keys() -> None:
    config = make_config()
    formatter = JsonFormatter(config)

    record = logging.LogRecord(
        name='test-logger',
        level=logging.INFO,
        pathname=__file__,
        lineno=123,
        msg='hello world',
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    for key in ('ts', 'level', 'service', 'logger', 'instance', 'env', 'msg'):
        assert key in payload

    assert payload['msg'] == 'hello world'
    assert payload['service'] == config.service_name
    assert payload['logger'] == 'test-logger'
    assert payload['env'] == config.env
    assert payload['instance'] == config.instance
    assert payload['level'] == 'info'


def test_json_formatter_includes_error_and_exception_fields() -> None:
    config = make_config()
    formatter = JsonFormatter(config)

    try:
        raise ValueError('boom')
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name='test-logger',
        level=logging.ERROR,
        pathname=__file__,
        lineno=123,
        msg='something failed',
        args=(),
        exc_info=exc_info,
    )

    payload = json.loads(formatter.format(record))

    assert payload['error'] == 'something failed'
    assert 'stack' in payload
    assert payload['exception_type'] == 'ValueError'
