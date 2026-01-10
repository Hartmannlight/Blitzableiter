from __future__ import annotations

import json
from datetime import time

import pytest

from app.blitz_config import (
    PollingConfig,
    SenderConfig,
    _parse_bool,
    _parse_int,
    _parse_polling_windows,
    _parse_time,
    load_blitz_config,
)
from tests.helpers import make_test_dir


def _write_geojson(path) -> None:
    payload = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {'name': 'test'},
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.0, 0.0]]],
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_parse_helpers_default_fallbacks() -> None:
    assert _parse_time('bad', default=time(hour=8, minute=0)) == time(hour=8, minute=0)
    assert _parse_bool('maybe', default=True) is True
    assert _parse_int('nope', default=5) == 5


def test_parse_polling_windows_spans_midnight() -> None:
    windows = _parse_polling_windows(['23:00-02:00'])
    assert len(windows) == 1
    assert windows[0].contains(time(hour=1, minute=0)) is True


def test_polling_current_interval_matches_peak() -> None:
    config = PollingConfig(
        default_interval_seconds=10,
        peak_interval_seconds=2,
        peak_windows=_parse_polling_windows(['07:00-09:00']),
    )
    assert config.current_interval(time(hour=8, minute=0)) == 2
    assert config.current_interval(time(hour=10, minute=0)) == 10


def test_sender_config_resolve_secret_handles_url() -> None:
    sender = SenderConfig(name='s', kind='discord_webhook')
    assert sender.resolve_secret(None) is None
    assert sender.resolve_secret('https://example.com') == 'https://example.com'


def test_parse_time_accepts_time_instance() -> None:
    value = time(hour=7, minute=30)
    assert _parse_time(value, default=time(hour=8)) == value


def test_parse_polling_windows_ignores_invalid_items() -> None:
    windows = _parse_polling_windows([123, 'bad'])
    assert windows == ()


def test_load_blitz_config_rejects_non_mapping() -> None:
    tmp = make_test_dir()
    path = tmp / 'config.yml'
    path.write_text('- bad\n- list\n', encoding='utf-8')

    with pytest.raises(ValueError):
        load_blitz_config(path)


def test_area_requires_sender() -> None:
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    _write_geojson(geo)
    path = tmp / 'config.yml'
    path.write_text(
        'senders:\n'
        '  s1:\n'
        '    kind: telegram\n'
        '    chat_id: "1"\n'
        '    token_env: "TEST"\n'
        'areas:\n'
        '  a1:\n'
        f'    geojson_path: "{geo.as_posix()}"\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='must specify at least one sender'):
        load_blitz_config(path)


def test_area_rejects_unknown_sender() -> None:
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    _write_geojson(geo)
    path = tmp / 'config.yml'
    path.write_text(
        'senders:\n'
        '  s1:\n'
        '    kind: telegram\n'
        '    chat_id: "1"\n'
        '    token_env: "TEST"\n'
        'areas:\n'
        '  a1:\n'
        f'    geojson_path: "{geo.as_posix()}"\n'
        '    senders:\n'
        '      - missing\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='undefined senders'):
        load_blitz_config(path)


def test_area_requires_geojson() -> None:
    tmp = make_test_dir()
    path = tmp / 'config.yml'
    path.write_text(
        'senders:\n'
        '  s1:\n'
        '    kind: telegram\n'
        '    chat_id: "1"\n'
        '    token_env: "TEST"\n'
        'areas:\n'
        '  a1:\n'
        '    senders:\n'
        '      - s1\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='missing geojson_path'):
        load_blitz_config(path)


def test_area_requires_polygons() -> None:
    tmp = make_test_dir()
    geo = tmp / 'empty.geojson'
    geo.write_text(json.dumps({'type': 'FeatureCollection', 'features': []}), encoding='utf-8')
    path = tmp / 'config.yml'
    path.write_text(
        'senders:\n'
        '  s1:\n'
        '    kind: telegram\n'
        '    chat_id: "1"\n'
        '    token_env: "TEST"\n'
        'areas:\n'
        '  a1:\n'
        f'    geojson_path: "{geo.as_posix()}"\n'
        '    senders:\n'
        '      - s1\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='contains no polygons'):
        load_blitz_config(path)


def test_load_blitz_config_missing_file_defaults() -> None:
    tmp = make_test_dir()
    missing = tmp / 'missing.yml'
    config = load_blitz_config(missing)
    assert config.global_filters.poi_types


def test_load_senders_rejects_missing_kind() -> None:
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    _write_geojson(geo)
    path = tmp / 'config.yml'
    path.write_text(
        'senders:\n'
        '  s1:\n'
        '    chat_id: "1"\n'
        'areas:\n'
        '  a1:\n'
        f'    geojson_path: "{geo.as_posix()}"\n'
        '    senders:\n'
        '      - s1\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='missing a kind'):
        load_blitz_config(path)


def test_language_falls_back_to_english(monkeypatch) -> None:
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    _write_geojson(geo)
    path = tmp / 'config.yml'
    path.write_text(
        'global:\n'
        '  language: xx\n'
        'senders:\n'
        '  s1:\n'
        '    kind: telegram\n'
        '    chat_id: "1"\n'
        '    token_env: "TEST"\n'
        'areas:\n'
        '  a1:\n'
        f'    geojson_path: "{geo.as_posix()}"\n'
        '    senders:\n'
        '      - s1\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('APP_CONFIG_PATH', str(path))

    config = load_blitz_config()
    assert config.language == 'en'
