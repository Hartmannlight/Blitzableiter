# src/app/config.py
from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    service_name: str
    env: str
    log_level: str
    metrics_enabled: bool
    metrics_port: int
    loop_sleep_seconds: float
    version: str
    commit: str
    config_source: str
    instance: str


_ENV_MAP: dict[str, str] = {
    'service_name': 'APP_SERVICE_NAME',
    'env': 'APP_ENV',
    'log_level': 'APP_LOG_LEVEL',
    'metrics_enabled': 'APP_METRICS_ENABLED',
    'metrics_port': 'APP_METRICS_PORT',
    'loop_sleep_seconds': 'APP_LOOP_SLEEP_SECONDS',
}


def _load_yaml_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        return {}

    with config_path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError('Top-level YAML config must be a mapping')

    return data


def _get_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'y'}:
        return True
    if text in {'0', 'false', 'no', 'n'}:
        return False
    return default


def _get_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _get_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def load_config() -> AppConfig:
    config_path_env = os.getenv('APP_CONFIG_PATH', 'config.yml')
    config_path = Path(config_path_env).expanduser()
    yaml_config = _load_yaml_config(config_path)

    def from_env_or_yaml(key: str, default: Any) -> Any:
        env_name = _ENV_MAP.get(key)
        env_value = os.getenv(env_name) if env_name else None
        if env_value is not None:
            return env_value
        return yaml_config.get(key, default)

    service_name = str(from_env_or_yaml('service_name', 'python-service'))
    env = str(from_env_or_yaml('env', 'dev'))
    log_level = str(from_env_or_yaml('log_level', 'INFO'))

    metrics_enabled_raw = from_env_or_yaml('metrics_enabled', True)
    metrics_enabled = _get_bool(metrics_enabled_raw, True)

    metrics_port_raw = from_env_or_yaml('metrics_port', 8000)
    metrics_port = _get_int(metrics_port_raw, 8000)

    loop_sleep_raw = from_env_or_yaml('loop_sleep_seconds', 5.0)
    loop_sleep_seconds = _get_float(loop_sleep_raw, 5.0)

    version = os.getenv('APP_VERSION', str(yaml_config.get('version', '0.0.0')))
    commit = os.getenv('APP_COMMIT', str(yaml_config.get('commit', 'unknown')))

    if yaml_config:
        config_source = str(config_path.resolve())
    else:
        config_source = 'env-only'

    instance = os.getenv('APP_INSTANCE', socket.gethostname())

    return AppConfig(
        service_name=service_name,
        env=env,
        log_level=log_level,
        metrics_enabled=metrics_enabled,
        metrics_port=metrics_port,
        loop_sleep_seconds=loop_sleep_seconds,
        version=version,
        commit=commit,
        config_source=config_source,
        instance=instance,
    )
