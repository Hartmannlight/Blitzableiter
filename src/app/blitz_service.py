from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from app.atudo_client import (
    AtudoClient,
    AtudoResponse,
    BoundingBox,
    NormalizedPoi,
    RawSnapshotStore,
    normalize_poi,
)
from app.blitz_config import AreaConfig, load_blitz_config
from app.db import PostgresRepository
from app.notifications import NotificationDispatcher
from app.state import PoiStateStore

log = logging.getLogger(__name__)

Observation = tuple[NormalizedPoi, tuple[str, ...], tuple[str, ...], dict[str, Any], str]
AggregatedObservation = tuple[NormalizedPoi, set[str], set[str], dict[str, Any], str]
ObservationWithDb = tuple[NormalizedPoi, tuple[str, ...], tuple[str, ...], int | None]


class BlitzableiterService:
    def __init__(self) -> None:
        self._client = AtudoClient()
        self._snapshots = RawSnapshotStore()
        self._state = PoiStateStore()
        self._config = load_blitz_config()
        db_url = os.getenv('BLITZ_DATABASE_URL') or os.getenv('DATABASE_URL')
        self._repository = None
        if db_url:
            try:
                self._repository = PostgresRepository(db_url)
                log.info('Database connected')
            except Exception:  # noqa: BLE001
                log.exception('Database initialization failed; continuing without persistence')
        self._dispatcher = NotificationDispatcher(
            self._config.senders,
            language=self._config.language,
            repository=self._repository,
        )
        self._last_interval = self._config.polling.default_interval_seconds
        self._hydrate_state()

    def _hydrate_state(self) -> None:
        if not self._repository:
            return
        grace_seconds = (
            max(
                self._config.polling.default_interval_seconds,
                self._config.polling.peak_interval_seconds,
            )
            * 2
        )
        try:
            persisted = self._repository.load_poi_state()
            if not persisted:
                return
            self._state.hydrate(
                persisted,
                now=datetime.now(UTC),
                active_grace=timedelta(seconds=grace_seconds),
            )
            log.info('Hydrated POI state', extra={'count': len(persisted)})
        except Exception:  # noqa: BLE001
            log.exception('Failed to hydrate persisted POI state')

    def reload_config(self) -> None:
        config = load_blitz_config()
        self._config = config
        self._dispatcher = NotificationDispatcher(
            config.senders,
            language=config.language,
            repository=self._repository,
        )

    def run_cycle(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        try:
            self.reload_config()
        except Exception:  # noqa: BLE001
            log.exception('Failed to reload configuration')

        interval = self._config.polling.current_interval(now.time())
        self._last_interval = interval

        aggregated: dict[tuple[str, str], AggregatedObservation] = {}
        for area in self._config.areas.values():
            for poi, senders, areas, raw_payload, request_key in self._process_area(area):
                poi_key = (poi.source, poi.source_poi_id)
                if poi_key not in aggregated:
                    aggregated[poi_key] = (poi, set(senders), set(areas), raw_payload, request_key)
                else:
                    agg_poi, agg_senders, agg_areas, agg_raw, agg_req = aggregated[poi_key]
                    agg_senders.update(senders)
                    agg_areas.update(areas)
                    aggregated[poi_key] = (agg_poi, agg_senders, agg_areas, agg_raw, agg_req)

        observations_with_db: list[ObservationWithDb] = []
        for poi, agg_senders, agg_areas, raw_payload, request_key in aggregated.values():
            db_id = None
            if self._repository:
                try:
                    db_id = self._repository.upsert_poi(poi, now)
                    self._repository.add_observation(db_id, now, raw_payload, request_key)
                except Exception:  # noqa: BLE001
                    log.exception(
                        'Database persistence failed for POI',
                        extra={'poi': poi.source_poi_id},
                    )
            observations_with_db.append((poi, tuple(agg_senders), tuple(agg_areas), db_id))

        notifications = self._state.process_observations(
            observations=observations_with_db,
            now=now,
            reminder_time=self._config.reminder.time_of_day,
            max_reminder_days=self._config.reminder.max_days,
            reminders_enabled=self._config.reminder.enabled,
        )

        if notifications:
            self._dispatcher.send_all(notifications)

        return interval

    def _process_area(
        self,
        area: AreaConfig,
    ) -> list[Observation]:
        matches: list[Observation] = []
        for bbox_values in area.bounding_boxes():
            bbox = BoundingBox(
                south=bbox_values[0],
                west=bbox_values[1],
                north=bbox_values[2],
                east=bbox_values[3],
            )
            for tile in bbox.split():
                try:
                    response = self._client.fetch(
                        bbox=tile,
                        poi_types=self._config.global_filters.poi_types,
                        zoom=14,
                    )
                except Exception:  # noqa: BLE001
                    log.exception(
                        'API request failed',
                        extra={'area': area.name, 'bbox': tile.to_param()},
                    )
                    continue

                stored = self._snapshots.maybe_store(response)
                if stored and self._repository:
                    try:
                        self._repository.store_raw_snapshot(response)
                    except Exception:  # noqa: BLE001
                        log.exception('Failed to store raw snapshot')
                matches.extend(self._handle_response(response, area))
        return matches

    def _handle_response(
        self,
        response: AtudoResponse,
        area: AreaConfig,
    ) -> list[Observation]:
        observations: list[Observation] = []
        for raw_poi in response.pois():
            poi = normalize_poi(raw_poi)
            if not self._matches_area(poi, area):
                continue
            observations.append((poi, area.senders, (area.name,), raw_poi, response.request_key))
        return observations

    def _matches_area(self, poi: NormalizedPoi, area: AreaConfig) -> bool:
        for region in area.regions:
            if region.contains(poi.lat, poi.lng):
                return True
        return False

    @property
    def last_interval(self) -> int:
        return self._last_interval
