from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Protocol

from app.blitz_config import SenderConfig
from app.metrics import mark_notification_result
from app.state import NotificationIntent

log = logging.getLogger(__name__)


class NotificationSender(Protocol):
    name: str

    def send(self, intent: NotificationIntent) -> tuple[bool, str | None]: ...


class NotificationRepository(Protocol):
    def add_notification(
        self,
        poi_db_id: int | None,
        sender_name: str,
        notification_type: str,
        sent_at: datetime,
        success: bool,
        error_message: str | None,
    ) -> None: ...


@dataclass
class TelegramSender:
    name: str
    token: str
    chat_id: str
    language: str = 'en'

    def send(self, intent: NotificationIntent) -> tuple[bool, str | None]:
        text = _format_telegram_message(intent, self.language)
        payload = {'chat_id': self.chat_id, 'text': text}
        data = json.dumps(payload).encode('utf-8')
        url = f'https://api.telegram.org/bot{self.token}/sendMessage'
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Blitzableiter/1.0',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as resp:  # nosec B310
                status = getattr(resp, 'status', resp.getcode())
                if 200 <= status < 300:
                    return True, None
                return False, f'status {status}'
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace') if hasattr(exc, 'read') else ''
            return False, f'http {exc.code}: {body[:200]}'
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)


def _mask_url(url: str) -> str:
    if not url:
        return ''
    if '/' not in url:
        return '***'
    tail = url[-6:]
    host = url.split('/', 3)[2]
    return f'{host}/***{tail}'


@dataclass
class DiscordWebhookSender:
    name: str
    url: str
    language: str = 'en'
    mention_user_id: str | None = None
    map_enabled: bool = True

    def send(self, intent: NotificationIntent) -> tuple[bool, str | None]:
        return self.send_embeds([intent])

    def send_embeds(self, intents: list[NotificationIntent]) -> tuple[bool, str | None]:
        embeds = [
            _build_discord_embed(intent, self.language, map_enabled=self.map_enabled)
            for intent in intents
        ]
        payload: dict[str, object] = {'embeds': embeds}
        if self.mention_user_id:
            payload['content'] = f'<@{self.mention_user_id}>'
            payload['allowed_mentions'] = {'users': [self.mention_user_id]}
        data = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(
            self.url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Blitzableiter/1.0',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as resp:  # nosec B310
                status = getattr(resp, 'status', resp.getcode())
                if 200 <= status < 300:
                    return True, None
                return False, f'status {status}'
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace') if hasattr(exc, 'read') else ''
            return False, f'http {exc.code}: {body[:200]}'
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)


@dataclass
class EmailSender:
    name: str
    smtp_host: str
    smtp_user: str | None
    smtp_pass: str | None
    from_addr: str
    to_addr: str

    def send(self, intent: NotificationIntent) -> tuple[bool, str | None]:
        subject = f'[Blitzableiter] {intent.notification_type} for POI {intent.poi.source_poi_id}'
        body_lines = [
            f'POI {intent.poi.source_poi_id} ({intent.poi.poi_type})',
            f'Location: {intent.poi.lat},{intent.poi.lng}',
        ]
        if intent.area_names:
            body_lines.append(f'Areas: {", ".join(intent.area_names)}')
        if intent.is_final_reminder:
            body_lines.append(
                'Note: This is the final reminder; no further notifications will be sent.',
            )
        body = '\n'.join(body_lines)

        message = EmailMessage()
        message['From'] = self.from_addr
        message['To'] = self.to_addr
        message['Subject'] = subject
        message.set_content(body)

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, 587) as server:  # nosec B101
                server.starttls(context=context)
                if self.smtp_user and self.smtp_pass:
                    server.login(self.smtp_user, self.smtp_pass)
                server.send_message(message)
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
        return True, None


class NotificationDispatcher:
    def __init__(
        self,
        sender_configs: dict[str, SenderConfig],
        language: str = 'en',
        repository: NotificationRepository | None = None,
    ) -> None:
        self._sender_configs = sender_configs
        self._senders: dict[str, NotificationSender | None] = {}
        self._delivery_enabled = not _parse_bool(os.getenv('BLITZ_DISABLE_NOTIFICATIONS'), False)
        self._language = language if language in {'en', 'de'} else 'en'
        self._repository = repository
        if self._repository:
            log.info('Notification persistence enabled', extra={'language': self._language})

    def send_all(self, intents: list[NotificationIntent]) -> None:
        intents_by_sender: dict[str, list[NotificationIntent]] = {}
        for intent in intents:
            for sender_name in intent.senders:
                intents_by_sender.setdefault(sender_name, []).append(intent)

        for sender_name, sender_intents in intents_by_sender.items():
            sender = self._get_sender(sender_name)
            if sender is None:
                for intent in sender_intents:
                    mark_notification_result(sender_name, intent.notification_type, success=False)
                continue

            if not self._delivery_enabled:
                for intent in sender_intents:
                    log.info(
                        'Notification delivery disabled; skipping send',
                        extra={'sender': sender_name, 'poi': intent.poi.source_poi_id},
                    )
                    self._record_result(intent, sender_name, True, None)
                continue

            if isinstance(sender, DiscordWebhookSender):
                reminders = [intent for intent in sender_intents if _is_reminder(intent)]
                others = [intent for intent in sender_intents if not _is_reminder(intent)]

                for intent in others:
                    success, error = sender.send(intent)
                    self._record_result(intent, sender_name, success, error)

                if reminders:
                    success, error = sender.send_embeds(reminders)
                    for intent in reminders:
                        self._record_result(intent, sender_name, success, error)
                continue

            for intent in sender_intents:
                success, error = sender.send(intent)
                self._record_result(intent, sender_name, success, error)

    def _get_sender(self, name: str) -> NotificationSender | None:
        if name in self._senders:
            return self._senders[name]

        config = self._sender_configs.get(name)
        if config is None:
            log.error('Unknown sender requested', extra={'sender': name})
            self._senders[name] = None
            return None

        sender = _build_sender(config, language=self._language)
        self._senders[name] = sender
        return sender

    def _record_result(
        self,
        intent: NotificationIntent,
        sender_name: str,
        success: bool,
        error: str | None,
    ) -> None:
        if success:
            mark_notification_result(sender_name, intent.notification_type, success=True)
        else:
            log.error(
                'Notification failed',
                extra={
                    'sender': sender_name,
                    'poi': intent.poi.source_poi_id,
                    'error': error,
                    'type': intent.notification_type,
                },
            )
            mark_notification_result(sender_name, intent.notification_type, success=False)

        if self._repository:
            try:
                self._repository.add_notification(
                    poi_db_id=intent.db_id,
                    sender_name=sender_name,
                    notification_type=intent.notification_type,
                    sent_at=datetime.now(UTC),
                    success=success,
                    error_message=error,
                )
            except Exception:  # noqa: BLE001
                log.exception(
                    'Failed to persist notification',
                    extra={'sender': sender_name, 'poi': intent.poi.source_poi_id},
                )


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    text = value.strip().lower()
    if text in {'1', 'true', 'yes', 'y'}:
        return True
    if text in {'0', 'false', 'no', 'n'}:
        return False
    return default


def _is_reminder(intent: NotificationIntent) -> bool:
    return intent.notification_type.startswith('reminder_day')


def _build_sender(sender_config: SenderConfig, language: str = 'en') -> NotificationSender | None:
    if sender_config.kind == 'telegram':
        token = sender_config.resolve_secret(sender_config.token_env or '')
        chat_id = sender_config.chat_id or ''
        if not token or not chat_id:
            log.warning(
                'Telegram sender missing token/chat_id',
                extra={'sender': sender_config.name},
            )
            return None
        return TelegramSender(
            name=sender_config.name,
            token=token,
            chat_id=chat_id,
            language=language,
        )

    if sender_config.kind == 'discord_webhook':
        raw_url = sender_config.url_env or ''
        url = sender_config.resolve_secret(raw_url) or (
            raw_url if raw_url.startswith(('http://', 'https://')) else None
        )
        if not url:
            log.warning('Discord sender missing URL', extra={'sender': sender_config.name})
            return None
        log.debug(
            'Discord sender configured',
            extra={'sender': sender_config.name, 'url': _mask_url(url)},
        )
        return DiscordWebhookSender(
            name=sender_config.name,
            url=url,
            language=language,
            mention_user_id=sender_config.mention_user_id,
            map_enabled=sender_config.enable_map,
        )

    if sender_config.kind == 'email':
        smtp_host = sender_config.resolve_secret(sender_config.smtp_host_env or '') or ''
        smtp_user = sender_config.resolve_secret(sender_config.smtp_user_env or '')
        smtp_pass = sender_config.resolve_secret(sender_config.smtp_pass_env or '')
        if not smtp_host or not sender_config.from_addr or not sender_config.to_addr:
            log.warning('Email sender missing config', extra={'sender': sender_config.name})
            return None
        return EmailSender(
            name=sender_config.name,
            smtp_host=smtp_host,
            smtp_user=smtp_user,
            smtp_pass=smtp_pass,
            from_addr=sender_config.from_addr,
            to_addr=sender_config.to_addr,
        )

    log.warning(
        'Unknown sender kind',
        extra={'sender': sender_config.name, 'kind': sender_config.kind},
    )
    return None


def _notification_label(intent: NotificationIntent, lang: str) -> str:
    nt = intent.notification_type
    if nt == 'initial':
        return _label('new_alert', lang)
    if nt.startswith('reminder_day'):
        day = nt.removeprefix('reminder_day')
        if intent.is_final_reminder:
            return _label('final_reminder', lang).format(day=day)
        return _label('reminder', lang).format(day=day)
    return nt.replace('_', ' ').title()


def _poi_type_label(poi_type: str, lang: str) -> str:
    mapping_en = {
        '1': 'Mobile speed trap',
        '0': 'Fixed speed trap',
        '2': 'Traffic control',
        '3': 'Red light camera',
        '4': 'Average speed check',
        '5': 'Speed trap',
        '6': 'Speed trap',
        'vwd': 'Hazard',
    }
    mapping_de = {
        '1': 'Mobiler Blitzer',
        '0': 'Fester Blitzer',
        '2': 'Verkehrskontrolle',
        '3': 'Ampelblitzer',
        '4': 'Section Control',
        '5': 'Blitzer',
        '6': 'Blitzer',
        'vwd': 'Gefahrenmeldung',
    }
    mapping = mapping_de if lang == 'de' else mapping_en
    return mapping.get(poi_type, f'Alert type {poi_type}')


def _label(key: str, lang: str) -> str:
    labels = {
        'en': {
            'location': 'Location',
            'street': 'Street',
            'speed_limit': 'Speed limit',
            'areas': 'Areas',
            'new_alert': 'New alert',
            'reminder': 'Reminder (day {day})',
            'final_reminder': 'Final reminder (day {day})',
            'final_note': (
                'Note: This is the final reminder; no further notifications will be sent.'
            ),
            'unknown': 'unknown',
        },
        'de': {
            'location': 'Ort',
            'street': 'Straße',
            'speed_limit': 'Geschwindigkeitsbegrenzung',
            'areas': 'Gebiete',
            'new_alert': 'Neue Meldung',
            'reminder': 'Erinnerung (Tag {day})',
            'final_reminder': 'Letzte Erinnerung (Tag {day})',
            'final_note': (
                'Hinweis: Dies ist die letzte Erinnerung; es folgen keine weiteren '
                'Benachrichtigungen.'
            ),
            'unknown': 'unbekannt',
        },
    }
    return labels.get(lang, labels['en']).get(key, key)


def _embed_color(intent: NotificationIntent) -> int:
    return 0xF39C12


def _build_discord_embed(
    intent: NotificationIntent,
    lang: str,
    map_enabled: bool = True,
) -> dict[str, object]:
    poi = intent.poi
    address = poi.address or {}
    city = address.get('city') or address.get('city_district') or ''
    street = address.get('street') or ''
    location = ', '.join(part for part in (street, city) if part) or f'{poi.lat:.4f},{poi.lng:.4f}'
    areas = ', '.join(intent.area_names) if intent.area_names else _label('unknown', lang)
    poi_label = _poi_type_label(poi.poi_type, lang)

    speed_text = f'{poi.vmax} km/h' if poi.vmax else _label('unknown', lang)
    fields = []
    fields.append(
        {
            'name': _label('street', lang),
            'value': street or _label('unknown', lang),
            'inline': False,
        },
    )
    if city:
        fields.append({'name': _label('location', lang), 'value': city, 'inline': True})
    elif not street:
        fields.append({'name': _label('location', lang), 'value': location, 'inline': True})
    fields.append({'name': _label('speed_limit', lang), 'value': speed_text, 'inline': True})
    if intent.area_names:
        fields.append({'name': _label('areas', lang), 'value': areas, 'inline': False})

    description = None
    if _is_reminder(intent):
        note = _label('final_note', lang) if intent.is_final_reminder else None
        parts = [_notification_label(intent, lang)]
        if note:
            parts.append(note)
        description = '\n'.join(parts)

    embed: dict[str, object] = {
        'title': poi_label,
        'fields': fields,
        'color': _embed_color(intent),
    }
    if map_enabled:
        embed['image'] = {'url': _osm_staticmap_url(poi.lat, poi.lng)}
    if description:
        embed['description'] = description
    return embed


def _osm_staticmap_url(lat: float, lng: float) -> str:
    lat_text = f'{lat:.5f}'
    lng_text = f'{lng:.5f}'
    return (
        'https://haukauntrie.de/online/api/staticmaps/staticmap.php'
        f'?center={lat_text},{lng_text}'
        '&zoom=16&size=640x360'
        f'&markers={lat_text},{lng_text},orange-pushpin'
    )


def _format_discord_message(intent: NotificationIntent, lang: str) -> str:
    poi = intent.poi
    address = poi.address or {}
    city = address.get('city') or address.get('city_district') or ''
    street = address.get('street') or ''
    location = ', '.join(part for part in (street, city) if part) if (street or city) else ''
    areas = ', '.join(intent.area_names) if intent.area_names else _label('unknown', lang)
    notif_label = _notification_label(intent, lang)
    poi_label = _poi_type_label(poi.poi_type, lang)

    lines = [f'{notif_label}: {poi_label}']
    if location:
        lines.append(f'{_label("location", lang)}: {location}')
    else:
        lines.append(f'{_label("location", lang)}: {poi.lat:.4f},{poi.lng:.4f}')
    if poi.vmax:
        lines.append(f'{_label("speed_limit", lang)}: {poi.vmax} km/h')
    lines.append(f'{_label("areas", lang)}: {areas}')
    lines.append(f'POI: {poi.source_poi_id}')
    if intent.is_final_reminder:
        lines.append(_label('final_note', lang))
    return '\n'.join(lines)


def _format_telegram_message(intent: NotificationIntent, lang: str) -> str:
    return _format_discord_message(intent, lang)
