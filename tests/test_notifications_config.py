from __future__ import annotations

from app.blitz_config import SenderConfig
from app.notifications import _build_sender, DiscordWebhookSender


def test_discord_sender_accepts_literal_url() -> None:
    config = SenderConfig(
        name='discord_alerts',
        kind='discord_webhook',
        url_env='https://discord.com/api/webhooks/example',
    )
    sender = _build_sender(config, language='en')
    assert isinstance(sender, DiscordWebhookSender)
    assert sender.url.startswith('https://discord.com/api/webhooks/')
