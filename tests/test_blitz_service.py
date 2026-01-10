from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.atudo_client import AtudoResponse
from app.blitz_service import BlitzableiterService
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


def _write_config(path: Path, geo_path: Path) -> None:
    path.write_text(
        'global:\n'
        '  default_interval: 5\n'
        'senders:\n'
        '  s1:\n'
        '    kind: discord_webhook\n'
        '    url_env: "https://discord.com/api/webhooks/example1"\n'
        '  s2:\n'
        '    kind: discord_webhook\n'
        '    url_env: "https://discord.com/api/webhooks/example2"\n'
        'areas:\n'
        '  a1:\n'
        f'    geojson_path: "{geo_path.as_posix()}"\n'
        '    senders:\n'
        '      - s1\n'
        '  a2:\n'
        f'    geojson_path: "{geo_path.as_posix()}"\n'
        '    senders:\n'
        '      - s2\n',
        encoding='utf-8',
    )


def _fake_response(lat: float, lng: float) -> AtudoResponse:
    body = {
        'pois': [
            {
                'backend': 'sim-1',
                'id': 'sim-1',
                'lat': f'{lat:.6f}',
                'lng': f'{lng:.6f}',
                'type': '1',
                'vmax': '50',
                'address': {'city': 'test'},
                'create_date': '01.01.2026',
                'confirm_date': '01.01.2026',
                'info': {},
                'style': 1,
            }
        ]
    }
    raw = json.dumps(body, sort_keys=True)
    return AtudoResponse(
        request_key='synthetic',
        requested_at=datetime.now(UTC),
        response_body=body,
        raw_hash=hashlib.sha256(raw.encode('utf-8')).hexdigest(),
    )


class FakeDispatcher:
    def __init__(self) -> None:
        self.sent: list = []

    def send_all(self, intents) -> None:
        self.sent.extend(intents)


def test_service_aggregates_senders_for_same_poi(monkeypatch) -> None:
    tmp_path = make_test_dir()
    geo_path = tmp_path / 'area.geojson'
    config_path = tmp_path / 'config.yml'
    _write_geojson(geo_path)
    _write_config(config_path, geo_path)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_path))
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')

    service = BlitzableiterService()
    dispatcher = FakeDispatcher()
    service._dispatcher = dispatcher  # type: ignore[assignment]
    service.reload_config = lambda: None  # type: ignore[assignment]

    def fake_fetch(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        return _fake_response(lat=0.5, lng=0.5)

    service._client.fetch = fake_fetch  # type: ignore[attr-defined]

    service.run_cycle(now=datetime(2026, 1, 1, tzinfo=UTC))

    assert len(dispatcher.sent) == 2
    senders = {intent.senders[0] for intent in dispatcher.sent}
    assert senders == {'s1', 's2'}
    for intent in dispatcher.sent:
        assert set(intent.area_names) == {'a1', 'a2'}


def test_service_handles_fetch_failures(monkeypatch) -> None:
    tmp_path = make_test_dir()
    geo_path = tmp_path / 'area.geojson'
    config_path = tmp_path / 'config.yml'
    _write_geojson(geo_path)
    _write_config(config_path, geo_path)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_path))
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')

    service = BlitzableiterService()
    dispatcher = FakeDispatcher()
    service._dispatcher = dispatcher  # type: ignore[assignment]

    def failing_fetch(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        raise RuntimeError('boom')

    service._client.fetch = failing_fetch  # type: ignore[attr-defined]

    interval = service.run_cycle(now=datetime(2026, 1, 1, tzinfo=UTC))

    assert interval == 5
    assert dispatcher.sent == []
