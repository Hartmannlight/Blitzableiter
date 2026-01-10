from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from app.atudo_client import NormalizedPoi
from app.state import PersistedPoiState, PoiStateStore


def make_poi(poi_id: str = '1') -> NormalizedPoi:
    return NormalizedPoi(
        source='blitzer_de',
        source_poi_id=poi_id,
        lat=0.5,
        lng=0.5,
        poi_type='1',
        vmax=None,
        address={},
        create_date=None,
        confirm_date=None,
        raw_payload={},
    )


def test_poi_lifecycle_new_and_reminder() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 1, 7, 0, tzinfo=UTC)
    observations = [(make_poi(), ('sender-a',), ('area-a',), None)]

    intents = store.process_observations(
        observations=observations,
        now=now,
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    assert any(intent.notification_type == 'initial' for intent in intents)

    next_day = now + timedelta(days=1, hours=2)
    intents = store.process_observations(
        observations=observations,
        now=next_day,
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    assert any(intent.notification_type == 'reminder_day1' for intent in intents)

    final_day = now + timedelta(days=2, hours=2)
    intents = store.process_observations(
        observations=observations,
        now=final_day,
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    assert any(intent.is_final_reminder for intent in intents)


def test_hydrate_state_restores_notification_history() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 2, 9, 0, tzinfo=UTC)
    poi = make_poi('persisted-1')
    persisted = PersistedPoiState(
        poi=poi,
        first_seen_at=now - timedelta(days=1),
        last_seen_at=now - timedelta(seconds=30),
        db_id=11,
        notifications={'sender-a': {'initial', 'reminder_day1'}},
        reminder_days={1},
    )

    store.hydrate([persisted], now=now, active_grace=timedelta(minutes=5))
    snapshot = store.snapshot()
    record = snapshot['blitzer_de:persisted-1']

    assert record.active is True
    assert record.has_notified('sender-a', 'initial')
    assert 1 in record.reminder_days_sent


def test_hydrate_marks_stale_as_inactive_and_realerts_on_reappear() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 2, 9, 0, tzinfo=UTC)
    poi = make_poi('persisted-2')
    persisted = PersistedPoiState(
        poi=poi,
        first_seen_at=now - timedelta(days=2),
        last_seen_at=now - timedelta(hours=2),
        db_id=22,
        notifications={'sender-a': {'initial'}},
        reminder_days=set(),
    )

    store.hydrate([persisted], now=now, active_grace=timedelta(minutes=10))
    snapshot = store.snapshot()
    record = snapshot['blitzer_de:persisted-2']
    assert record.active is False

    observations = [(poi, ('sender-a',), ('area-a',), 22)]
    intents = store.process_observations(
        observations=observations,
        now=now + timedelta(minutes=1),
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    assert any(intent.notification_type == 'initial' for intent in intents)


def test_process_observations_marks_missing_as_inactive() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    poi = make_poi('gone-1')
    store.process_observations(
        observations=[(poi, ('sender-a',), ('area-a',), None)],
        now=now,
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    store.process_observations(
        observations=[],
        now=now + timedelta(hours=1),
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    snapshot = store.snapshot()
    assert snapshot['blitzer_de:gone-1'].active is False


def test_reminders_disabled_returns_empty() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    poi = make_poi('p1')
    store.process_observations(
        observations=[(poi, ('s1',), ('a1',), None)],
        now=now - timedelta(days=1),
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    intents = store._collect_reminders(
        now=now,
        reminder_time=time(8, 0),
        max_days=2,
        reminders_enabled=False,
    )

    assert intents == []


def test_reminder_pending_when_before_time() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 2, 7, 0, tzinfo=UTC)
    poi = make_poi('reminder-1')
    store.process_observations(
        observations=[(poi, ('s1',), ('a1',), None)],
        now=now - timedelta(days=1),
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    intents = store.process_observations(
        observations=[(poi, ('s1',), ('a1',), None)],
        now=now,
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    assert intents == []


def test_reminder_skips_when_already_sent() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 3, 9, 0, tzinfo=UTC)
    poi = make_poi('reminder-2')
    store.process_observations(
        observations=[(poi, ('s1',), ('a1',), None)],
        now=now - timedelta(days=1),
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )
    record = store._records[('blitzer_de', 'reminder-2')]
    record.reminder_days_sent.add(1)

    intents = store.process_observations(
        observations=[(poi, ('s1',), ('a1',), None)],
        now=now,
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    assert intents == []


def test_reminder_skips_after_max_days() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 10, 9, 0, tzinfo=UTC)
    poi = make_poi('reminder-3')
    store.process_observations(
        observations=[(poi, ('s1',), ('a1',), None)],
        now=now - timedelta(days=10),
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )

    intents = store._collect_reminders(
        now=now,
        reminder_time=time(8, 0),
        max_days=2,
        reminders_enabled=True,
    )

    assert intents == []


def test_build_notifications_skips_already_sent() -> None:
    store = PoiStateStore()
    now = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
    poi = make_poi('dup')
    store.process_observations(
        observations=[(poi, ('s1',), ('a1',), None)],
        now=now,
        reminder_time=time(8, 0),
        max_reminder_days=2,
        reminders_enabled=True,
    )
    record = store._records[('blitzer_de', 'dup')]
    record.mark_notified('s1', 'initial')

    intents = store._build_notifications(record, ('s1',), ('a1',), 'initial')
    assert intents == []
