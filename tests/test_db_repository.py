from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.atudo_client import NormalizedPoi
from app.db import PostgresRepository


class FakeCursor:
    def __init__(self, scripted_results: list) -> None:
        self._scripted_results = scripted_results
        self.queries: list[tuple[str, tuple | None]] = []

    def execute(self, query: str, params: tuple | None = None) -> None:
        self.queries.append((query, params))

    def fetchone(self):
        return self._scripted_results.pop(0)

    def fetchall(self):
        return self._scripted_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class FakeConnection:
    def __init__(self, scripted_results: list) -> None:
        self._scripted_results = scripted_results

    def cursor(self) -> FakeCursor:
        return FakeCursor(self._scripted_results)


class FakePsycopg:
    def __init__(self, scripted_results: list) -> None:
        self._scripted_results = scripted_results

    def connect(self, dsn: str, autocommit: bool = True) -> FakeConnection:  # noqa: ARG002
        return FakeConnection(self._scripted_results)


def _make_poi() -> NormalizedPoi:
    return NormalizedPoi(
        source='blitzer_de',
        source_poi_id='p1',
        lat=1.0,
        lng=2.0,
        poi_type='1',
        vmax=50,
        address={'city': 'X'},
        create_date='01.01.2026',
        confirm_date='01.01.2026',
        raw_payload={'id': 'p1'},
    )


def test_repository_upsert_and_observation(monkeypatch) -> None:
    scripted = [(1,), (42,)]
    monkeypatch.setattr('app.db.psycopg', FakePsycopg(scripted))

    repo = PostgresRepository('postgresql://user:pass@localhost/db')
    poi = _make_poi()
    now = datetime(2026, 1, 1, tzinfo=UTC)

    poi_id = repo.upsert_poi(poi, now)
    repo.add_observation(poi_id, now, poi.raw_payload, request_key='bbox')

    assert poi_id == 42


def test_repository_load_state_with_notifications(monkeypatch) -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    rows = [
        (
            7,
            'p7',
            1.0,
            2.0,
            '1',
            30,
            {'city': 'Y'},
            '01.01.2026',
            '01.01.2026',
            now,
            now,
            {'id': 'p7'},
        )
    ]
    notifications = [
        (7, 'sender-a', 'initial'),
        (7, 'sender-a', 'reminder_day2'),
        (7, 'sender-a', 'reminder_daybad'),
    ]
    scripted = [(1,), rows, notifications]
    monkeypatch.setattr('app.db.psycopg', FakePsycopg(scripted))

    repo = PostgresRepository('postgresql://user:pass@localhost/db')
    state = repo.load_poi_state()

    assert len(state) == 1
    assert state[0].poi.source_poi_id == 'p7'
    assert 2 in state[0].reminder_days
    assert 'initial' in state[0].notifications['sender-a']


def test_repository_store_snapshot_and_notification(monkeypatch) -> None:
    scripted = [(1,), None]
    monkeypatch.setattr('app.db.psycopg', FakePsycopg(scripted))

    repo = PostgresRepository('postgresql://user:pass@localhost/db')
    response = type(
        'Resp',
        (),
        {
            'requested_at': datetime(2026, 1, 1, tzinfo=UTC),
            'request_key': 'k1',
            'response_body': {'pois': []},
            'raw_hash': 'hash',
        },
    )()
    repo.store_raw_snapshot(response)
    repo.add_notification(
        poi_db_id=1,
        sender_name='s1',
        notification_type='initial',
        sent_at=datetime(2026, 1, 1, tzinfo=UTC),
        success=True,
        error_message=None,
    )


def test_repository_ensure_schema_failure(monkeypatch) -> None:
    scripted = [None]
    monkeypatch.setattr('app.db.psycopg', FakePsycopg(scripted))

    with pytest.raises(RuntimeError):
        PostgresRepository('postgresql://user:pass@localhost/db')
