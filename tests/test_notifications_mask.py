from __future__ import annotations

from app.notifications import _mask_url


def test_mask_url_hides_token() -> None:
    masked = _mask_url('https://discord.com/api/webhooks/123/verysecrettoken')
    assert 'discord.com' in masked
    assert 'verysecret' not in masked
    assert masked.endswith('token')
