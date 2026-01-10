from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from app.atudo_client import NormalizedPoi
from app.metrics import (
    mark_active_pois,
    mark_new_poi,
    mark_pois_seen,
    mark_reminders_pending,
)

log = logging.getLogger(__name__)


@dataclass
class NotificationIntent:
    poi: NormalizedPoi
    senders: tuple[str, ...]
    notification_type: str
    area_names: tuple[str, ...]
    is_final_reminder: bool = False
    db_id: int | None = None


@dataclass(frozen=True)
class PersistedPoiState:
    poi: NormalizedPoi
    first_seen_at: datetime
    last_seen_at: datetime
    db_id: int
    notifications: dict[str, set[str]]
    reminder_days: set[int]


@dataclass
class PoiRecord:
    poi: NormalizedPoi
    first_seen_at: datetime
    last_seen_at: datetime
    active: bool = True
    reminder_days_sent: set[int] = field(default_factory=set)
    notification_types_sent: dict[str, set[str]] = field(default_factory=dict)
    area_names: set[str] = field(default_factory=set)
    current_senders: set[str] = field(default_factory=set)
    db_id: int | None = None

    def mark_notified(self, sender: str, notification_type: str) -> None:
        self.notification_types_sent.setdefault(sender, set()).add(notification_type)

    def has_notified(self, sender: str, notification_type: str) -> bool:
        return notification_type in self.notification_types_sent.get(sender, set())


class PoiStateStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], PoiRecord] = {}

    def hydrate(
        self,
        persisted: Iterable[PersistedPoiState],
        now: datetime,
        active_grace: timedelta,
    ) -> None:
        for state in persisted:
            key = self._make_key(state.poi)
            is_active = state.last_seen_at >= now - active_grace
            record = PoiRecord(
                poi=state.poi,
                first_seen_at=state.first_seen_at,
                last_seen_at=state.last_seen_at,
                active=is_active,
                reminder_days_sent=set(state.reminder_days),
                notification_types_sent={k: set(v) for k, v in state.notifications.items()},
                area_names=set(),
                current_senders=set(),
                db_id=state.db_id,
            )
            self._records[key] = record

    @staticmethod
    def _make_key(poi: NormalizedPoi) -> tuple[str, str]:
        return (poi.source, poi.source_poi_id)

    def process_observations(
        self,
        observations: Iterable[tuple[NormalizedPoi, tuple[str, ...], tuple[str, ...], int | None]],
        now: datetime,
        reminder_time: time,
        max_reminder_days: int,
        reminders_enabled: bool,
    ) -> list[NotificationIntent]:
        notifications: list[NotificationIntent] = []
        seen_keys: set[tuple[str, str]] = set()

        for poi, sender_names, area_names, db_id in observations:
            key = self._make_key(poi)
            seen_keys.add(key)
            record = self._records.get(key)
            if record is None or not record.active:
                record = PoiRecord(
                    poi=poi,
                    first_seen_at=now,
                    last_seen_at=now,
                    active=True,
                    area_names=set(area_names),
                    current_senders=set(sender_names),
                    db_id=db_id,
                )
                self._records[key] = record
                notifications.extend(
                    self._build_notifications(record, sender_names, area_names, 'initial')
                )
                mark_new_poi(source=poi.source)
            else:
                record.poi = poi
                record.last_seen_at = now
                record.active = True
                record.area_names.update(area_names)
                record.current_senders = set(sender_names)
                record.db_id = db_id

            mark_pois_seen(source=poi.source)

        for key, record in list(self._records.items()):
            if key not in seen_keys and record.active:
                record.active = False
                record.last_seen_at = now

        notifications.extend(
            self._collect_reminders(now, reminder_time, max_reminder_days, reminders_enabled)
        )
        self._refresh_active_metric()
        return notifications

    def _collect_reminders(
        self,
        now: datetime,
        reminder_time: time,
        max_days: int,
        reminders_enabled: bool,
    ) -> list[NotificationIntent]:
        if not reminders_enabled:
            mark_reminders_pending(count=0)
            return []

        today = now.date()
        due_notifications: list[NotificationIntent] = []
        pending = 0

        for record in self._records.values():
            if not record.active:
                continue
            days_active = (today - record.first_seen_at.date()).days
            if days_active <= 0:
                continue
            if days_active > max_days:
                continue
            if now.time() < reminder_time:
                pending += 1
                continue
            if days_active in record.reminder_days_sent:
                continue

            record.reminder_days_sent.add(days_active)
            notification_type = f'reminder_day{days_active}'
            is_final = days_active == max_days
            due_notifications.extend(
                self._build_notifications(
                    record,
                    tuple(record.current_senders),
                    tuple(record.area_names),
                    notification_type,
                    is_final,
                )
            )
        mark_reminders_pending(count=pending)
        return due_notifications

    def _build_notifications(
        self,
        record: PoiRecord,
        senders: tuple[str, ...],
        area_names: tuple[str, ...],
        notification_type: str,
        is_final: bool = False,
    ) -> list[NotificationIntent]:
        intents: list[NotificationIntent] = []
        for sender in senders:
            if record.has_notified(sender, notification_type):
                continue
            record.mark_notified(sender, notification_type)
            intents.append(
                NotificationIntent(
                    poi=record.poi,
                    senders=(sender,),
                    notification_type=notification_type,
                    area_names=area_names,
                    is_final_reminder=is_final,
                    db_id=record.db_id,
                )
            )
        return intents

    def _refresh_active_metric(self) -> None:
        active_counts: dict[str, int] = {}
        for record in self._records.values():
            if record.active:
                active_counts[record.poi.source] = active_counts.get(record.poi.source, 0) + 1
        for source, count in active_counts.items():
            mark_active_pois(source=source, count=count)

    def snapshot(self) -> dict[str, PoiRecord]:
        return {f'{k[0]}:{k[1]}': v for k, v in self._records.items()}
