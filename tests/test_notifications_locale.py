from __future__ import annotations

from app.atudo_client import NormalizedPoi
from app.notifications import _format_discord_message
from app.state import NotificationIntent


def test_discord_message_german_labels() -> None:
    poi = NormalizedPoi(
        source='blitzer_de',
        source_poi_id='123',
        lat=49.0,
        lng=8.4,
        poi_type='1',
        vmax=50,
        address={'city': 'Karlsruhe', 'street': 'A8'},
        create_date=None,
        confirm_date=None,
        raw_payload={},
    )
    intent = NotificationIntent(
        poi=poi,
        senders=('discord',),
        notification_type='initial',
        area_names=('example_city',),
        is_final_reminder=False,
    )
    msg = _format_discord_message(intent, 'de')
    assert 'Neue Meldung' in msg
    assert 'Mobiler Blitzer' in msg
    assert 'Geschwindigkeitsbegrenzung: 50 km/h' in msg
