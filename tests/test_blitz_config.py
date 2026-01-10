from __future__ import annotations

import json
from datetime import time
from pathlib import Path

from app.blitz_config import BlitzConfig, load_blitz_config
from tests.helpers import make_test_dir


def _write_geojson(path: Path) -> None:
    payload = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {'name': 'test'},
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]],
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_load_blitz_config(monkeypatch) -> None:
    tmp_path = make_test_dir()
    geojson_path = tmp_path / 'area.geojson'
    _write_geojson(geojson_path)

    config_file = tmp_path / 'config.yml'
    config_file.write_text(
        'global:\n'
        '  default_interval: 600\n'
        '  peak_interval: 120\n'
        '  peak_hours:\n'
        '    - "07:00-09:00"\n'
        '  reminder:\n'
        '    enable: true\n'
        '    maximum_days: 2\n'
        '    time_of_day: "08:00"\n'
        '  filters:\n'
        '    types: ["1", "vwd"]\n'
        'senders:\n'
        '  telegram_main:\n'
        '    kind: telegram\n'
        '    chat_id: "123"\n'
        '    token_env: "TEST_TOKEN"\n'
        'areas:\n'
        '  city:\n'
        '    geojson_path: "' + str(geojson_path).replace("\\", "\\\\") + '"\n'
        '    senders:\n'
        '      - telegram_main\n',
        encoding='utf-8',
    )

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_file))
    config = load_blitz_config()

    assert isinstance(config, BlitzConfig)
    assert config.polling.default_interval_seconds == 600
    assert config.polling.peak_interval_seconds == 120
    assert config.polling.peak_windows[0].contains(time(hour=8, minute=0))
    assert config.reminder.max_days == 2
    assert config.global_filters.poi_types == ('1', 'vwd')
    assert 'telegram_main' in config.senders
    assert 'city' in config.areas
    area = config.areas['city']
    assert area.geojson_path == geojson_path
    assert area.senders == ('telegram_main',)
    assert len(area.regions) == 1


def test_env_overrides_utc_fields(monkeypatch) -> None:
    tmp_path = make_test_dir()
    geojson_path = tmp_path / 'area.geojson'
    _write_geojson(geojson_path)

    config_file = tmp_path / 'config.yml'
    config_file.write_text(
        'global:\n'
        '  default_interval: 600\n'
        'senders:\n'
        '  telegram_main:\n'
        '    kind: telegram\n'
        '    chat_id: "123"\n'
        '    token_env: "TEST_TOKEN"\n'
        'areas:\n'
        '  city:\n'
        '    geojson_path: "' + str(geojson_path).replace("\\", "\\\\") + '"\n'
        '    senders:\n'
        '      - telegram_main\n',
        encoding='utf-8',
    )

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_file))
    monkeypatch.setenv('BLITZ_REMINDER_TIME_UTC', '09:15')
    monkeypatch.setenv('BLITZ_PEAK_HOURS_UTC', '06:00-07:00,18:00-19:00')

    config = load_blitz_config()

    assert config.reminder.time_of_day == time(hour=9, minute=15)
    assert config.polling.peak_windows[0].contains(time(hour=6, minute=30))


def test_env_overrides_global_values(monkeypatch) -> None:
    tmp_path = make_test_dir()
    geojson_path = tmp_path / 'area.geojson'
    _write_geojson(geojson_path)

    config_file = tmp_path / 'config.yml'
    config_file.write_text(
        'global:\n'
        '  default_interval: 600\n'
        '  peak_interval: 120\n'
        '  filters:\n'
        '    types: ["1"]\n'
        '  reminder:\n'
        '    enable: true\n'
        '    maximum_days: 2\n'
        'senders:\n'
        '  telegram_main:\n'
        '    kind: telegram\n'
        '    chat_id: "123"\n'
        '    token_env: "TEST_TOKEN"\n'
        'areas:\n'
        '  city:\n'
        '    geojson_path: "' + str(geojson_path).replace("\\", "\\\\") + '"\n'
        '    senders:\n'
        '      - telegram_main\n',
        encoding='utf-8',
    )

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_file))
    monkeypatch.setenv('BLITZ_DEFAULT_INTERVAL', '111')
    monkeypatch.setenv('BLITZ_PEAK_INTERVAL', '222')
    monkeypatch.setenv('BLITZ_POI_TYPES', '1,vwd')
    monkeypatch.setenv('BLITZ_REMINDER_ENABLE', '0')
    monkeypatch.setenv('BLITZ_REMINDER_MAX_DAYS', '5')

    config = load_blitz_config()

    assert config.polling.default_interval_seconds == 111
    assert config.polling.peak_interval_seconds == 222
    assert config.global_filters.poi_types == ('1', 'vwd')
    assert config.reminder.enabled is False
    assert config.reminder.max_days == 5
