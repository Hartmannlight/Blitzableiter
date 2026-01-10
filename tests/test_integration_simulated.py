from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.atudo_client import AtudoResponse
from app.blitz_service import BlitzableiterService
from app.state import NotificationIntent
from tests.helpers import make_test_dir


def _write_geojson(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                'type': 'FeatureCollection',
                'features': [
                    {
                        'type': 'Feature',
                        'geometry': {
                            'type': 'Polygon',
                            'coordinates': [
                                [
                                    [0.0, 0.0],
                                    [0.0, 1.0],
                                    [1.0, 1.0],
                                    [1.0, 0.0],
                                    [0.0, 0.0],
                                ]
                            ],
                        },
                        'properties': {'name': 'test'},
                    }
                ],
            }
        ),
        encoding='utf-8',
    )


def _write_config(path: Path, geo_path: Path) -> None:
    path.write_text(
        'global:\n'
        '  default_interval: 5\n'
        'senders:\n'
        '  telegram_main:\n'
        '    kind: telegram\n'
        '    chat_id: "123456"\n'
        '    token_env: "TEST_TELEGRAM_TOKEN"\n'
        'areas:\n'
        '  test_area:\n'
        f'    geojson_path: "{geo_path.as_posix()}"\n'
        '    senders:\n'
        '      - telegram_main\n',
        encoding='utf-8',
    )


def _write_config_with_discord(path: Path, geo_path: Path) -> None:
    path.write_text(
        'global:\n'
        '  default_interval: 5\n'
        '  reminder:\n'
        '    enable: true\n'
        '    maximum_days: 2\n'
        '    time_of_day_utc: "08:00"\n'
        'senders:\n'
        '  discord_main:\n'
        '    kind: discord_webhook\n'
        '    url_env: "TEST_DISCORD_URL"\n'
        'areas:\n'
        '  test_area:\n'
        f'    geojson_path: "{geo_path.as_posix()}"\n'
        '    senders:\n'
        '      - discord_main\n',
        encoding='utf-8',
    )


def _write_config_with_two_senders(path: Path, geo_path: Path) -> None:
    path.write_text(
        'global:\n'
        '  default_interval: 5\n'
        'senders:\n'
        '  discord_main:\n'
        '    kind: discord_webhook\n'
        '    url_env: "TEST_DISCORD_URL"\n'
        '  telegram_main:\n'
        '    kind: telegram\n'
        '    chat_id: "123456"\n'
        '    token_env: "TEST_TELEGRAM_TOKEN"\n'
        'areas:\n'
        '  test_area:\n'
        f'    geojson_path: "{geo_path.as_posix()}"\n'
        '    senders:\n'
        '      - discord_main\n'
        '      - telegram_main\n',
        encoding='utf-8',
    )


def _fake_response(lat: float, lng: float) -> AtudoResponse:
    body = {
        'pois': [
            {
                'backend': 'simulated-1',
                'id': 'simulated-1',
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
        requested_at=datetime.now(timezone.utc),
        response_body=body,
        raw_hash=hashlib.sha256(raw.encode('utf-8')).hexdigest(),
    )


def test_simulated_cycle_triggers_state(monkeypatch) -> None:
    tmp_path = make_test_dir()
    geo_path = tmp_path / 'area.geojson'
    config_path = tmp_path / 'config.yml'
    _write_geojson(geo_path)
    _write_config(config_path, geo_path)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_path))
    monkeypatch.setenv('TEST_TELEGRAM_TOKEN', 'dummy-token')
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')

    service = BlitzableiterService()

    def fake_fetch(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        return _fake_response(lat=0.5, lng=0.5)

    service._client.fetch = fake_fetch  # type: ignore[attr-defined]

    service.run_cycle(now=datetime(2025, 1, 1, tzinfo=timezone.utc))

    snapshot = service._state.snapshot()
    assert snapshot  # at least one POI stored
    record = next(iter(snapshot.values()))
    assert record.active is True
    assert record.poi.source_poi_id == 'simulated-1'


def test_simulated_discord_notifications_over_days(monkeypatch) -> None:
    class FakeSender:
        def __init__(self) -> None:
            self.intents: list[NotificationIntent] = []

        def send(self, intent: NotificationIntent):  # type: ignore[override]
            self.intents.append(intent)
            return True, None

    tmp_path = make_test_dir()
    geo_path = tmp_path / 'area.geojson'
    config_path = tmp_path / 'config.yml'
    _write_geojson(geo_path)
    _write_config_with_discord(config_path, geo_path)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_path))
    monkeypatch.setenv('TEST_DISCORD_URL', 'https://example.test/webhook')
    monkeypatch.delenv('BLITZ_DISABLE_NOTIFICATIONS', raising=False)

    fake_sender = FakeSender()

    def fake_build_sender(config, language='en'):  # noqa: ARG001
        return fake_sender

    monkeypatch.setattr('app.notifications._build_sender', fake_build_sender)

    service = BlitzableiterService()

    def fake_fetch(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        return _fake_response(lat=0.5, lng=0.5)

    service._client.fetch = fake_fetch  # type: ignore[attr-defined]

    service.run_cycle(now=datetime(2025, 1, 1, 7, 0, tzinfo=timezone.utc))
    assert len(fake_sender.intents) == 1
    assert fake_sender.intents[-1].notification_type == 'initial'

    service.run_cycle(now=datetime(2025, 1, 2, 7, 0, tzinfo=timezone.utc))
    assert len(fake_sender.intents) == 1

    service.run_cycle(now=datetime(2025, 1, 2, 8, 1, tzinfo=timezone.utc))
    assert len(fake_sender.intents) == 2
    assert fake_sender.intents[-1].notification_type == 'reminder_day1'
    assert fake_sender.intents[-1].is_final_reminder is False

    service.run_cycle(now=datetime(2025, 1, 3, 8, 1, tzinfo=timezone.utc))
    assert len(fake_sender.intents) == 3
    assert fake_sender.intents[-1].notification_type == 'reminder_day2'
    assert fake_sender.intents[-1].is_final_reminder is True


def test_simulated_reappear_triggers_initial_again(monkeypatch) -> None:
    class FakeSender:
        def __init__(self) -> None:
            self.intents: list[NotificationIntent] = []

        def send(self, intent: NotificationIntent):  # type: ignore[override]
            self.intents.append(intent)
            return True, None

    tmp_path = make_test_dir()
    geo_path = tmp_path / 'area.geojson'
    config_path = tmp_path / 'config.yml'
    _write_geojson(geo_path)
    _write_config_with_discord(config_path, geo_path)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_path))
    monkeypatch.setenv('TEST_DISCORD_URL', 'https://example.test/webhook')
    monkeypatch.setenv('BLITZ_REMINDER_ENABLE', '0')
    monkeypatch.delenv('BLITZ_DISABLE_NOTIFICATIONS', raising=False)

    fake_sender = FakeSender()
    monkeypatch.setattr('app.notifications._build_sender', lambda config, language='en': fake_sender)

    service = BlitzableiterService()

    def fake_fetch_present(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        return _fake_response(lat=0.5, lng=0.5)

    def fake_fetch_empty(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        body = {'pois': []}
        raw = json.dumps(body, sort_keys=True)
        return AtudoResponse(
            request_key='synthetic-empty',
            requested_at=datetime.now(timezone.utc),
            response_body=body,
            raw_hash=hashlib.sha256(raw.encode('utf-8')).hexdigest(),
        )

    service._client.fetch = fake_fetch_present  # type: ignore[attr-defined]
    service.run_cycle(now=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc))
    assert [intent.notification_type for intent in fake_sender.intents] == ['initial']

    service._client.fetch = fake_fetch_empty  # type: ignore[attr-defined]
    service.run_cycle(now=datetime(2025, 1, 2, 9, 0, tzinfo=timezone.utc))
    assert [intent.notification_type for intent in fake_sender.intents] == ['initial']
    snapshot = service._state.snapshot()
    record = next(iter(snapshot.values()))
    assert record.active is False

    service._client.fetch = fake_fetch_present  # type: ignore[attr-defined]
    service.run_cycle(now=datetime(2025, 1, 3, 9, 0, tzinfo=timezone.utc))
    assert [intent.notification_type for intent in fake_sender.intents] == [
        'initial',
        'initial',
    ]


def test_simulated_multiple_senders_dedup(monkeypatch) -> None:
    class FakeSender:
        def __init__(self) -> None:
            self.intents: list[NotificationIntent] = []

        def send(self, intent: NotificationIntent):  # type: ignore[override]
            self.intents.append(intent)
            return True, None

    tmp_path = make_test_dir()
    geo_path = tmp_path / 'area.geojson'
    config_path = tmp_path / 'config.yml'
    _write_geojson(geo_path)
    _write_config_with_two_senders(config_path, geo_path)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config_path))
    monkeypatch.setenv('TEST_DISCORD_URL', 'https://example.test/webhook')
    monkeypatch.setenv('TEST_TELEGRAM_TOKEN', 'dummy-token')
    monkeypatch.delenv('BLITZ_DISABLE_NOTIFICATIONS', raising=False)

    senders = {
        'discord_main': FakeSender(),
        'telegram_main': FakeSender(),
    }

    def fake_build_sender(config, language='en'):  # noqa: ARG001
        return senders[config.name]

    monkeypatch.setattr('app.notifications._build_sender', fake_build_sender)

    service = BlitzableiterService()

    def fake_fetch(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        return _fake_response(lat=0.5, lng=0.5)

    service._client.fetch = fake_fetch  # type: ignore[attr-defined]

    service.run_cycle(now=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc))
    assert len(senders['discord_main'].intents) == 1
    assert len(senders['telegram_main'].intents) == 1

    service.run_cycle(now=datetime(2025, 1, 1, 9, 5, tzinfo=timezone.utc))
    assert len(senders['discord_main'].intents) == 1
    assert len(senders['telegram_main'].intents) == 1
