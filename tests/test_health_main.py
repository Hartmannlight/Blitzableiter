from __future__ import annotations

import json

import pytest

from app import health
from app.config import AppConfig


def _config(health_file: str) -> AppConfig:
    return AppConfig(
        service_name='svc',
        env='test',
        log_level='INFO',
        metrics_enabled=False,
        metrics_port=0,
        loop_sleep_seconds=5.0,
        health_file=health_file,
        version='0.0.0',
        commit='test',
        config_source='test',
        instance='unit',
    )


def test_health_main_ok(monkeypatch, capsys, tmp_path) -> None:
    health_file = tmp_path / 'health.json'
    monkeypatch.setattr(health, 'load_dotenv', lambda: None)
    monkeypatch.setattr(health, 'load_config', lambda: _config(str(health_file)))
    monkeypatch.setattr(health, '_check_health_file', lambda config: None)

    with pytest.raises(SystemExit) as excinfo:
        health.main()

    assert excinfo.value.code == 0
    output = capsys.readouterr().out.strip()
    payload = json.loads(output)
    assert payload['status'] == 'ok'


def test_health_main_error_on_config(monkeypatch, capsys) -> None:
    monkeypatch.setattr(health, 'load_dotenv', lambda: None)
    monkeypatch.setattr(health, 'load_config', lambda: (_ for _ in ()).throw(RuntimeError('bad')))

    with pytest.raises(SystemExit) as excinfo:
        health.main()

    assert excinfo.value.code == 1
    output = capsys.readouterr().err.strip()
    payload = json.loads(output)
    assert payload['status'] == 'error'


def test_health_main_health_error(monkeypatch, capsys, tmp_path) -> None:
    health_file = tmp_path / 'health.json'
    monkeypatch.setattr(health, 'load_dotenv', lambda: None)
    monkeypatch.setattr(health, 'load_config', lambda: _config(str(health_file)))
    monkeypatch.setattr(health, '_check_health_file', lambda config: 'bad health')

    with pytest.raises(SystemExit) as excinfo:
        health.main()

    assert excinfo.value.code == 1
    output = capsys.readouterr().out.strip()
    payload = json.loads(output)
    assert payload['status'] == 'error'
    assert payload['error'] == 'bad health'
