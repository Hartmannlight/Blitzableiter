from __future__ import annotations

import os
from pathlib import Path

import pytest

CACHE_DIR = Path.cwd() / '.test-work' / 'pytest_cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True, scope='session')
def _default_app_config() -> None:
    if os.getenv('APP_CONFIG_PATH'):
        return

    base = Path.cwd() / '.test-work' / 'config'
    base.mkdir(parents=True, exist_ok=True)
    config_path = base / 'config.yml'
    geo_path = Path.cwd() / 'geo' / 'example_city.geojson'
    config_path.write_text(
        'global:\n'
        '  default_interval: 5\n'
        'senders:\n'
        '  test_sender:\n'
        '    kind: telegram\n'
        '    chat_id: "1"\n'
        '    token_env: "TEST_TELEGRAM_TOKEN"\n'
        'areas:\n'
        '  example_city:\n'
        f'    geojson_path: "{geo_path.as_posix()}"\n'
        '    senders:\n'
        '      - test_sender\n',
        encoding='utf-8',
    )
    os.environ['APP_CONFIG_PATH'] = str(config_path)
