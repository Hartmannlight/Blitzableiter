from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.atudo_client import AtudoResponse, NormalizedPoi
from app.state import PersistedPoiState

psycopg: Any | None = None
_psycopg: Any | None = None
try:
    import psycopg as _imported_psycopg
except ImportError:  # pragma: no cover
    pass
else:
    _psycopg = _imported_psycopg
psycopg = _psycopg

log = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS data_source (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

INSERT INTO data_source (name) VALUES ('blitzer_de')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS raw_snapshots (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_source(id),
    requested_at TIMESTAMPTZ NOT NULL,
    request_key TEXT NOT NULL,
    response_body JSONB NOT NULL,
    response_hash TEXT NOT NULL,
    UNIQUE (source_id, request_key, response_hash)
);

CREATE TABLE IF NOT EXISTS pois (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES data_source(id),
    source_poi_id TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    poi_type TEXT NOT NULL,
    vmax INTEGER,
    address JSONB,
    create_date TEXT,
    confirm_date TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    raw_payload JSONB,
    UNIQUE (source_id, source_poi_id)
);

CREATE TABLE IF NOT EXISTS poi_observations (
    id SERIAL PRIMARY KEY,
    poi_id INTEGER NOT NULL REFERENCES pois(id),
    observed_at TIMESTAMPTZ NOT NULL,
    raw_payload JSONB,
    request_key TEXT
);

CREATE TABLE IF NOT EXISTS poi_notifications (
    id SERIAL PRIMARY KEY,
    poi_id INTEGER REFERENCES pois(id),
    sender_name TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT
);
"""


class PostgresRepository:
    def __init__(self, dsn: str) -> None:
        if psycopg is None:  # pragma: no cover
            raise ImportError(
                'psycopg is required for database persistence. ' 'Install psycopg[binary].',
            )
        self._dsn = dsn
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._source_id = self._ensure_schema()

    def _ensure_schema(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            cur.execute("SELECT id FROM data_source WHERE name = 'blitzer_de'")
            row = cur.fetchone()
            if not row:
                raise RuntimeError('Failed to init data_source')
            return int(row[0])

    def store_raw_snapshot(self, response: AtudoResponse) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw_snapshots (
                    source_id,
                    requested_at,
                    request_key,
                    response_body,
                    response_hash
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    self._source_id,
                    response.requested_at,
                    response.request_key,
                    json.dumps(response.response_body),
                    response.raw_hash,
                ),
            )

    def upsert_poi(self, poi: NormalizedPoi, now: datetime) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pois (
                    source_id,
                    source_poi_id,
                    lat,
                    lng,
                    poi_type,
                    vmax,
                    address,
                    create_date,
                    confirm_date,
                    first_seen_at,
                    last_seen_at,
                    raw_payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_id, source_poi_id) DO UPDATE
                SET lat = EXCLUDED.lat,
                    lng = EXCLUDED.lng,
                    poi_type = EXCLUDED.poi_type,
                    vmax = EXCLUDED.vmax,
                    address = EXCLUDED.address,
                    create_date = EXCLUDED.create_date,
                    confirm_date = EXCLUDED.confirm_date,
                    last_seen_at = EXCLUDED.last_seen_at,
                    raw_payload = EXCLUDED.raw_payload
                RETURNING id
                """,
                (
                    self._source_id,
                    poi.source_poi_id,
                    poi.lat,
                    poi.lng,
                    poi.poi_type,
                    poi.vmax,
                    json.dumps(poi.address),
                    poi.create_date,
                    poi.confirm_date,
                    now,
                    now,
                    json.dumps(poi.raw_payload),
                ),
            )
            row = cur.fetchone()
            return int(row[0])

    def add_observation(
        self,
        poi_db_id: int,
        observed_at: datetime,
        raw_payload: dict[str, Any],
        request_key: str | None,
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO poi_observations (poi_id, observed_at, raw_payload, request_key)
                VALUES (%s, %s, %s, %s)
                """,
                (poi_db_id, observed_at, json.dumps(raw_payload), request_key),
            )

    def add_notification(
        self,
        poi_db_id: int | None,
        sender_name: str,
        notification_type: str,
        sent_at: datetime,
        success: bool,
        error_message: str | None,
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO poi_notifications (
                    poi_id,
                    sender_name,
                    notification_type,
                    sent_at,
                    success,
                    error_message
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (poi_db_id, sender_name, notification_type, sent_at, success, error_message),
            )
            log.debug(
                'DB insert poi_notifications',
                extra={
                    'poi_db_id': poi_db_id,
                    'sender': sender_name,
                    'type': notification_type,
                    'success': success,
                },
            )

    def load_poi_state(self) -> list[PersistedPoiState]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_poi_id, lat, lng, poi_type, vmax, address,
                       create_date, confirm_date, first_seen_at, last_seen_at, raw_payload
                FROM pois
                WHERE source_id = %s
                """,
                (self._source_id,),
            )
            fetched_rows = cur.fetchall()
            rows: list[tuple[Any, ...]] = fetched_rows if fetched_rows is not None else []

        poi_ids = [int(row[0]) for row in rows]
        notifications_by_poi: dict[int, dict[str, set[str]]] = {}
        reminder_days_by_poi: dict[int, set[int]] = {}
        if poi_ids:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT poi_id, sender_name, notification_type
                    FROM poi_notifications
                    WHERE poi_id = ANY(%s)
                    """,
                    (poi_ids,),
                )
                for poi_id, sender_name, notification_type in cur.fetchall() or []:
                    poi_id = int(poi_id)
                    notifications_by_poi.setdefault(poi_id, {}).setdefault(sender_name, set()).add(
                        notification_type,
                    )
                    if isinstance(notification_type, str) and notification_type.startswith(
                        'reminder_day'
                    ):
                        day_raw = notification_type.removeprefix('reminder_day')
                        try:
                            reminder_days_by_poi.setdefault(poi_id, set()).add(int(day_raw))
                        except ValueError:
                            continue

        states: list[PersistedPoiState] = []
        for (
            poi_id,
            source_poi_id,
            lat,
            lng,
            poi_type,
            vmax,
            address,
            create_date,
            confirm_date,
            first_seen_at,
            last_seen_at,
            raw_payload,
        ) in rows:
            poi = NormalizedPoi(
                source='blitzer_de',
                source_poi_id=str(source_poi_id),
                lat=float(lat),
                lng=float(lng),
                poi_type=str(poi_type),
                vmax=int(vmax) if vmax is not None else None,
                address=address or {},
                create_date=str(create_date) if create_date is not None else None,
                confirm_date=str(confirm_date) if confirm_date is not None else None,
                raw_payload=raw_payload or {},
            )
            states.append(
                PersistedPoiState(
                    poi=poi,
                    first_seen_at=first_seen_at,
                    last_seen_at=last_seen_at,
                    db_id=int(poi_id),
                    notifications=notifications_by_poi.get(int(poi_id), {}),
                    reminder_days=reminder_days_by_poi.get(int(poi_id), set()),
                )
            )
        return states
