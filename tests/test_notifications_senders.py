from __future__ import annotations

import urllib.error

from app.atudo_client import NormalizedPoi
from app.blitz_config import SenderConfig
from app.notifications import (
    DiscordWebhookSender,
    EmailSender,
    TelegramSender,
    _build_sender,
    _format_discord_message,
    _mask_url,
    _notification_label,
    _parse_bool,
)
from app.state import NotificationIntent


def _intent(notification_type: str = 'initial', final: bool = False) -> NotificationIntent:
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
    return NotificationIntent(
        poi=poi,
        senders=('s1',),
        notification_type=notification_type,
        area_names=(),
        is_final_reminder=final,
    )


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def read(self) -> bytes:
        return b'ok'

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSMTP:
    def __init__(self, host: str, port: int) -> None:  # noqa: ARG002
        self.started = False
        self.logged_in = False
        self.sent = False

    def starttls(self, context=None) -> None:  # noqa: ARG002
        self.started = True

    def login(self, user: str, password: str) -> None:  # noqa: ARG002
        self.logged_in = True

    def send_message(self, message) -> None:  # noqa: ARG002
        self.sent = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_mask_url_variants() -> None:
    assert _mask_url('') == ''
    assert _mask_url('token') == '***'
    assert _mask_url('https://discord.com/api/webhooks/abc123') == 'discord.com/***abc123'


def test_parse_bool_variants() -> None:
    assert _parse_bool('1', False) is True
    assert _parse_bool('0', True) is False
    assert _parse_bool('maybe', True) is True


def test_telegram_sender_success(monkeypatch) -> None:
    sender = TelegramSender(name='t1', token='tok', chat_id='1')
    monkeypatch.setattr('urllib.request.urlopen', lambda request, timeout=5: _FakeResponse(200))

    success, error = sender.send(_intent())
    assert success is True
    assert error is None


def test_telegram_sender_http_error(monkeypatch) -> None:
    sender = TelegramSender(name='t1', token='tok', chat_id='1')

    def _boom(request, timeout=5):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 403, 'nope', None, None)

    monkeypatch.setattr('urllib.request.urlopen', _boom)

    success, error = sender.send(_intent())
    assert success is False
    assert 'http 403' in (error or '')


def test_telegram_sender_non_2xx(monkeypatch) -> None:
    sender = TelegramSender(name='t1', token='tok', chat_id='1')
    monkeypatch.setattr('urllib.request.urlopen', lambda request, timeout=5: _FakeResponse(500))

    success, error = sender.send(_intent())
    assert success is False
    assert error == 'status 500'


def test_telegram_sender_generic_error(monkeypatch) -> None:
    sender = TelegramSender(name='t1', token='tok', chat_id='1')

    def _boom(request, timeout=5):  # noqa: ARG001
        raise OSError('nope')

    monkeypatch.setattr('urllib.request.urlopen', _boom)

    success, error = sender.send(_intent())
    assert success is False
    assert error == 'nope'


def test_discord_sender_non_2xx(monkeypatch) -> None:
    sender = DiscordWebhookSender(name='d1', url='https://discord.com/api/webhooks/example')
    monkeypatch.setattr('urllib.request.urlopen', lambda request, timeout=5: _FakeResponse(500))

    success, error = sender.send(_intent())
    assert success is False
    assert error == 'status 500'


def test_discord_sender_http_error(monkeypatch) -> None:
    sender = DiscordWebhookSender(name='d1', url='https://discord.com/api/webhooks/example')

    def _boom(request, timeout=5):  # noqa: ARG001
        raise urllib.error.HTTPError(request.full_url, 400, 'no', None, None)

    monkeypatch.setattr('urllib.request.urlopen', _boom)

    success, error = sender.send(_intent())
    assert success is False
    assert 'http 400' in (error or '')


def test_email_sender_success(monkeypatch) -> None:
    sender = EmailSender(
        name='e1',
        smtp_host='smtp',
        smtp_user='u',
        smtp_pass='p',
        from_addr='a@example.com',
        to_addr='b@example.com',
    )
    monkeypatch.setattr('smtplib.SMTP', _FakeSMTP)

    success, error = sender.send(_intent())
    assert success is True
    assert error is None


def test_email_sender_success_without_login(monkeypatch) -> None:
    sender = EmailSender(
        name='e2',
        smtp_host='smtp',
        smtp_user=None,
        smtp_pass=None,
        from_addr='a@example.com',
        to_addr='b@example.com',
    )
    monkeypatch.setattr('smtplib.SMTP', _FakeSMTP)

    success, error = sender.send(_intent())
    assert success is True
    assert error is None


def test_email_sender_failure(monkeypatch) -> None:
    sender = EmailSender(
        name='e1',
        smtp_host='smtp',
        smtp_user=None,
        smtp_pass=None,
        from_addr='a@example.com',
        to_addr='b@example.com',
    )

    def _boom(host, port):  # noqa: ARG001
        raise OSError('nope')

    monkeypatch.setattr('smtplib.SMTP', _boom)

    success, error = sender.send(_intent())
    assert success is False
    assert error is not None


def test_build_sender_missing_config() -> None:
    telegram = SenderConfig(name='t', kind='telegram', token_env='TOKEN', chat_id=None)
    assert _build_sender(telegram) is None

    discord = SenderConfig(name='d', kind='discord_webhook', url_env='')
    assert _build_sender(discord) is None

    email = SenderConfig(name='e', kind='email', smtp_host_env='HOST')
    assert _build_sender(email) is None

    unknown = SenderConfig(name='x', kind='sms')
    assert _build_sender(unknown) is None


def test_build_sender_success(monkeypatch) -> None:
    monkeypatch.setenv('TOKEN', 'secret')
    monkeypatch.setenv('SMTP_HOST', 'smtp.local')
    telegram = SenderConfig(name='t', kind='telegram', token_env='TOKEN', chat_id='123')
    email = SenderConfig(
        name='e',
        kind='email',
        smtp_host_env='SMTP_HOST',
        from_addr='a@example.com',
        to_addr='b@example.com',
    )

    assert isinstance(_build_sender(telegram), TelegramSender)
    assert isinstance(_build_sender(email), EmailSender)


def test_notification_label_final_reminder() -> None:
    intent = _intent(notification_type='reminder_day2', final=True)
    label = _notification_label(intent, 'en')
    assert 'Final reminder' in label


def test_notification_label_fallback() -> None:
    intent = _intent(notification_type='custom_type', final=False)
    label = _notification_label(intent, 'en')
    assert label == 'Custom Type'


def test_format_discord_message_final_note() -> None:
    intent = _intent(notification_type='reminder_day1', final=True)
    message = _format_discord_message(intent, 'en')
    assert 'Final reminder' in message
    assert 'no further notifications' in message
