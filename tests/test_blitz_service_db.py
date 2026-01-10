from __future__ import annotations

from datetime import datetime, timedelta, timezone

import json
from pathlib import Path

from app.atudo_client import NormalizedPoi
from app.blitz_service import BlitzableiterService
from app.state import PersistedPoiState
from tests.helpers import make_test_dir


class _FakeRepo:
    def __init__(self, persisted=None, fail_load: bool = False, fail_write: bool = False) -> None:
        self.persisted = persisted or []
        self.fail_load = fail_load
        self.fail_write = fail_write
        self.snapshots = []
        self.observations = []
        self.upserts = 0

    def load_poi_state(self):
        if self.fail_load:
            raise RuntimeError('load failed')
        return self.persisted

    def upsert_poi(self, poi, now):
        if self.fail_write:
            raise RuntimeError('write failed')
        self.upserts += 1
        return 99

    def add_observation(self, poi_db_id, observed_at, raw_payload, request_key):
        self.observations.append((poi_db_id, request_key))

    def store_raw_snapshot(self, response):
        self.snapshots.append(response.request_key)


def _make_persisted(now: datetime) -> PersistedPoiState:
    poi = NormalizedPoi(
        source='blitzer_de',
        source_poi_id='p1',
        lat=1.0,
        lng=2.0,
        poi_type='1',
        vmax=None,
        address={},
        create_date=None,
        confirm_date=None,
        raw_payload={},
    )
    return PersistedPoiState(
        poi=poi,
        first_seen_at=now - timedelta(days=1),
        last_seen_at=now,
        db_id=1,
        notifications={},
        reminder_days=set(),
    )


def _write_geojson(path: Path) -> None:
    payload = {
        'type': 'FeatureCollection',
        'features': [
            {
                'type': 'Feature',
                'properties': {'name': 'test'},
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [
                        [[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0], [0.0, 0.0]]
                    ],
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
        '    url_env: "https://discord.com/api/webhooks/example"\n'
        'areas:\n'
        '  a1:\n'
        f'    geojson_path: "{geo_path.as_posix()}"\n'
        '    senders:\n'
        '      - s1\n',
        encoding='utf-8',
    )


def test_hydrate_state_with_repository(monkeypatch) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo = _FakeRepo(persisted=[_make_persisted(now)])

    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    config = tmp / 'config.yml'
    _write_geojson(geo)
    _write_config(config, geo)

    monkeypatch.setenv('BLITZ_DATABASE_URL', 'postgresql://example')
    monkeypatch.setenv('APP_CONFIG_PATH', str(config))
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')
    monkeypatch.setattr('app.blitz_service.PostgresRepository', lambda url: repo)

    service = BlitzableiterService()

    snapshot = service._state.snapshot()
    assert snapshot


def test_hydrate_state_failure_is_swallowed(monkeypatch) -> None:
    repo = _FakeRepo(fail_load=True)
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    config = tmp / 'config.yml'
    _write_geojson(geo)
    _write_config(config, geo)

    monkeypatch.setenv('BLITZ_DATABASE_URL', 'postgresql://example')
    monkeypatch.setenv('APP_CONFIG_PATH', str(config))
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')
    monkeypatch.setattr('app.blitz_service.PostgresRepository', lambda url: repo)

    BlitzableiterService()


def test_run_cycle_ignores_repository_errors(monkeypatch) -> None:
    repo = _FakeRepo(fail_write=True)
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    config = tmp / 'config.yml'
    _write_geojson(geo)
    _write_config(config, geo)

    monkeypatch.setenv('BLITZ_DATABASE_URL', 'postgresql://example')
    monkeypatch.setenv('APP_CONFIG_PATH', str(config))
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')
    monkeypatch.setattr('app.blitz_service.PostgresRepository', lambda url: repo)

    service = BlitzableiterService()

    from app.atudo_client import AtudoResponse

    def _fake_fetch(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        body = {'pois': [{'backend': 'p1', 'lat': '1.0', 'lng': '2.0', 'type': '1'}]}
        return AtudoResponse(
            request_key='k1',
            requested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            response_body=body,
            raw_hash='hash',
        )

    service._client.fetch = _fake_fetch  # type: ignore[attr-defined]
    service.run_cycle(now=datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert repo.upserts == 0


def test_run_cycle_persists_observations(monkeypatch) -> None:
    repo = _FakeRepo()
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    config = tmp / 'config.yml'
    _write_geojson(geo)
    _write_config(config, geo)

    monkeypatch.setenv('BLITZ_DATABASE_URL', 'postgresql://example')
    monkeypatch.setenv('APP_CONFIG_PATH', str(config))
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')
    monkeypatch.setattr('app.blitz_service.PostgresRepository', lambda url: repo)

    service = BlitzableiterService()

    from app.atudo_client import AtudoResponse

    def _fake_fetch(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        body = {'pois': [{'backend': 'p1', 'lat': '1.0', 'lng': '1.0', 'type': '1'}]}
        return AtudoResponse(
            request_key='k2',
            requested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            response_body=body,
            raw_hash='hash2',
        )

    service._client.fetch = _fake_fetch  # type: ignore[attr-defined]
    service.run_cycle(now=datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert repo.upserts == 1
    assert repo.observations
    assert repo.snapshots == ['k2']
    assert service.last_interval == 5


def test_store_raw_snapshot_failure_is_swallowed(monkeypatch) -> None:
    repo = _FakeRepo()
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    config = tmp / 'config.yml'
    _write_geojson(geo)
    _write_config(config, geo)

    def _store_raw_snapshot(response):  # noqa: ARG001
        raise RuntimeError('fail')

    repo.store_raw_snapshot = _store_raw_snapshot  # type: ignore[assignment]

    monkeypatch.setenv('BLITZ_DATABASE_URL', 'postgresql://example')
    monkeypatch.setenv('APP_CONFIG_PATH', str(config))
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')
    monkeypatch.setattr('app.blitz_service.PostgresRepository', lambda url: repo)

    service = BlitzableiterService()

    from app.atudo_client import AtudoResponse

    def _fake_fetch(bbox, poi_types, zoom: int = 14):  # noqa: ARG001
        body = {'pois': [{'backend': 'p1', 'lat': '1.0', 'lng': '1.0', 'type': '1'}]}
        return AtudoResponse(
            request_key='k3',
            requested_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            response_body=body,
            raw_hash='hash3',
        )

    service._client.fetch = _fake_fetch  # type: ignore[attr-defined]
    service.run_cycle(now=datetime(2026, 1, 1, tzinfo=timezone.utc))

    assert repo.upserts == 1


def test_db_init_failure_is_swallowed(monkeypatch) -> None:
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    config = tmp / 'config.yml'
    _write_geojson(geo)
    _write_config(config, geo)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config))
    monkeypatch.setenv('BLITZ_DATABASE_URL', 'postgresql://example')
    monkeypatch.setattr('app.blitz_service.PostgresRepository', lambda url: (_ for _ in ()).throw(RuntimeError('db')))

    service = BlitzableiterService()
    assert service._repository is None


def test_run_cycle_handles_reload_config_error(monkeypatch) -> None:
    tmp = make_test_dir()
    geo = tmp / 'area.geojson'
    config = tmp / 'config.yml'
    _write_geojson(geo)
    _write_config(config, geo)

    monkeypatch.setenv('APP_CONFIG_PATH', str(config))
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')

    service = BlitzableiterService()
    service.reload_config = lambda: (_ for _ in ()).throw(RuntimeError('bad'))  # type: ignore[assignment]
    service._process_area = lambda area: []  # type: ignore[assignment]

    interval = service.run_cycle(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert interval == 5


def test_matches_area_false(monkeypatch) -> None:
    from app.blitz_config import AreaConfig
    from app.geo import GeoRegion

    monkeypatch.delenv('BLITZ_DATABASE_URL', raising=False)
    monkeypatch.delenv('DATABASE_URL', raising=False)

    service = BlitzableiterService()
    region = GeoRegion(name='r1', polygons=(((10.0, 10.0), (10.0, 11.0), (11.0, 11.0)),))
    area = AreaConfig(name='a1', geojson_path=Path('x'), senders=('s1',), regions=(region,))
    poi = NormalizedPoi(
        source='blitzer_de',
        source_poi_id='p',
        lat=0.0,
        lng=0.0,
        poi_type='1',
        vmax=None,
        address={},
        create_date=None,
        confirm_date=None,
        raw_payload={},
    )

    assert service._matches_area(poi, area) is False
