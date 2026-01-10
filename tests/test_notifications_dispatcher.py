from __future__ import annotations

from datetime import datetime, timezone

from app.atudo_client import NormalizedPoi
from app.blitz_config import SenderConfig
from app.notifications import NotificationDispatcher
from app.state import NotificationIntent


class FakeSender:
    def __init__(self) -> None:
        self.calls: int = 0

    def send(self, intent: NotificationIntent):  # type: ignore[override]
        self.calls += 1
        return True, None


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add_notification(
        self,
        poi_db_id: int | None,
        sender_name: str,
        notification_type: str,
        sent_at: datetime,
        success: bool,
        error_message: str | None,
    ) -> None:
        self.calls.append(
            {
                'poi_db_id': poi_db_id,
                'sender_name': sender_name,
                'notification_type': notification_type,
                'success': success,
                'error_message': error_message,
            }
        )


class FailingRepository:
    def add_notification(self, *args, **kwargs) -> None:  # noqa: ANN001
        raise RuntimeError('db down')


def _intent(sender: str) -> NotificationIntent:
    poi = NormalizedPoi(
        source='blitzer_de',
        source_poi_id='poi-1',
        lat=1.0,
        lng=2.0,
        poi_type='1',
        vmax=None,
        address={},
        create_date=None,
        confirm_date=None,
        raw_payload={},
    )
    return NotificationIntent(
        poi=poi,
        senders=(sender,),
        notification_type='initial',
        area_names=('area-a',),
        is_final_reminder=False,
        db_id=123,
    )


def test_dispatcher_skips_send_when_delivery_disabled(monkeypatch) -> None:
    monkeypatch.setenv('BLITZ_DISABLE_NOTIFICATIONS', '1')
    fake_sender = FakeSender()

    def fake_build_sender(config, language='en'):  # noqa: ARG001
        return fake_sender

    monkeypatch.setattr('app.notifications._build_sender', fake_build_sender)

    repository = FakeRepository()
    dispatcher = NotificationDispatcher(
        {'s1': SenderConfig(name='s1', kind='telegram', token_env='TOKEN', chat_id='1')},
        language='en',
        repository=repository,
    )

    dispatcher.send_all([_intent('s1')])

    assert fake_sender.calls == 0
    assert repository.calls
    assert repository.calls[0]['success'] is True


def test_dispatcher_handles_unknown_sender(monkeypatch) -> None:
    monkeypatch.delenv('BLITZ_DISABLE_NOTIFICATIONS', raising=False)
    dispatcher = NotificationDispatcher({})
    dispatcher.send_all([_intent('missing')])


def test_dispatcher_sender_failure_persists_error(monkeypatch) -> None:
    class FailingSender:
        name = 's1'

        def send(self, intent: NotificationIntent):  # type: ignore[override]
            return False, 'bad'

    monkeypatch.setattr('app.notifications._build_sender', lambda config, language='en': FailingSender())
    repo = FakeRepository()
    dispatcher = NotificationDispatcher(
        {'s1': SenderConfig(name='s1', kind='telegram', token_env='TOKEN', chat_id='1')},
        repository=repo,
    )

    dispatcher.send_all([_intent('s1')])
    assert repo.calls[0]['success'] is False


def test_dispatcher_handles_repository_failure(monkeypatch) -> None:
    monkeypatch.setattr('app.notifications._build_sender', lambda config, language='en': FakeSender())
    dispatcher = NotificationDispatcher(
        {'s1': SenderConfig(name='s1', kind='telegram', token_env='TOKEN', chat_id='1')},
        repository=FailingRepository(),
    )
    dispatcher.send_all([_intent('s1')])
