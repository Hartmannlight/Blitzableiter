from __future__ import annotations

from app.atudo_client import NormalizedPoi
from app.notifications import _build_discord_embed
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
    embed = _build_discord_embed(intent, 'de')
    assert embed['title'] == 'Mobiler Blitzer'
    fields = {field['name']: field['value'] for field in embed['fields']}
    assert fields['Geschwindigkeitsbegrenzung'] == '50 km/h'
    assert fields['Straße'] == 'A8'
    assert fields['Ort'] == 'Karlsruhe'
