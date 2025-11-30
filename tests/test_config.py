# tests/test_config.py
from __future__ import annotations

from pathlib import Path

import pytest  # type: ignore[import]

from app.config import AppConfig, load_config


def test_load_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APP_SERVICE_NAME', 'test-service')
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.setenv('APP_LOG_LEVEL', 'DEBUG')
    monkeypatch.setenv('APP_METRICS_ENABLED', '0')
    monkeypatch.setenv('APP_METRICS_PORT', '9000')
    monkeypatch.setenv('APP_LOOP_SLEEP_SECONDS', '1.5')
    monkeypatch.setenv('APP_CONFIG_PATH', 'nonexistent.yml')
    monkeypatch.setenv('APP_VERSION', '1.2.3')
    monkeypatch.setenv('APP_COMMIT', 'deadbeef')
    monkeypatch.setenv('APP_INSTANCE', 'test-instance')

    config = load_config()

    assert isinstance(config, AppConfig)
    assert config.service_name == 'test-service'
    assert config.env == 'test'
    assert config.log_level == 'DEBUG'
    assert config.metrics_enabled is False
    assert config.metrics_port == 9000
    assert config.loop_sleep_seconds == 1.5
    assert config.version == '1.2.3'
    assert config.commit == 'deadbeef'
    assert config.instance == 'test-instance'
    assert config.config_source == 'env-only'


def test_load_config_from_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / 'config.yml'
    config_file.write_text(
        'service_name: yaml-service\n'
        'env: yaml-env\n'
        'log_level: WARNING\n'
        'metrics_enabled: true\n'
        'metrics_port: 9100\n'
        'loop_sleep_seconds: 2.0\n'
        'version: 9.9.9\n'
        'commit: cafebabe\n',
        encoding='utf-8',
    )

    monkeypatch.delenv('APP_SERVICE_NAME', raising=False)
    monkeypatch.delenv('APP_ENV', raising=False)
    monkeypatch.delenv('APP_LOG_LEVEL', raising=False)
    monkeypatch.delenv('APP_METRICS_ENABLED', raising=False)
    monkeypatch.delenv('APP_METRICS_PORT', raising=False)
    monkeypatch.delenv('APP_LOOP_SLEEP_SECONDS', raising=False)
    monkeypatch.delenv('APP_VERSION', raising=False)
    monkeypatch.delenv('APP_COMMIT', raising=False)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_file))

    config = load_config()

    assert config.service_name == 'yaml-service'
    assert config.env == 'yaml-env'
    assert config.log_level == 'WARNING'
    assert config.metrics_enabled is True
    assert config.metrics_port == 9100
    assert config.loop_sleep_seconds == 2.0
    assert config.version == '9.9.9'
    assert config.commit == 'cafebabe'
    assert config.config_source == str(config_file.resolve())
