from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Any, Iterable

import yaml

from app.geo import GeoRegion, load_geojson_regions

DEFAULT_POI_TYPES = ('ts', '0', '1', '2', '3', '4', '5', '6', 'vwd')


@dataclass(frozen=True)
class PollingWindow:
    start: time
    end: time

    def contains(self, current: time) -> bool:
        if self.start <= self.end:
            return self.start <= current <= self.end
        # window spans midnight
        return current >= self.start or current <= self.end


@dataclass(frozen=True)
class PollingConfig:
    default_interval_seconds: int = 900
    peak_interval_seconds: int = 300
    peak_windows: tuple[PollingWindow, ...] = ()

    def current_interval(self, current: time) -> int:
        for window in self.peak_windows:
            if window.contains(current):
                return self.peak_interval_seconds
        return self.default_interval_seconds


@dataclass(frozen=True)
class ReminderConfig:
    enabled: bool = True
    max_days: int = 3
    time_of_day: time = time(hour=8, minute=0)


@dataclass(frozen=True)
class SenderConfig:
    name: str
    kind: str
    token_env: str | None = None
    url_env: str | None = None
    smtp_host_env: str | None = None
    smtp_user_env: str | None = None
    smtp_pass_env: str | None = None
    from_addr: str | None = None
    to_addr: str | None = None
    chat_id: str | None = None

    def resolve_secret(self, env_name: str | None) -> str | None:
        if env_name is None:
            return None
        value = os.getenv(env_name)
        if value:
            return value
        if isinstance(env_name, str) and env_name.startswith(('http://', 'https://')):
            return env_name
        return None


@dataclass(frozen=True)
class AreaConfig:
    name: str
    geojson_path: Path
    senders: tuple[str, ...]
    regions: tuple[GeoRegion, ...]

    def bounding_boxes(self) -> list[tuple[float, float, float, float]]:
        return [region.bounding_box for region in self.regions]


@dataclass(frozen=True)
class GlobalFilters:
    poi_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlitzConfig:
    polling: PollingConfig
    reminder: ReminderConfig
    global_filters: GlobalFilters
    language: str
    senders: dict[str, SenderConfig] = field(default_factory=dict)
    areas: dict[str, AreaConfig] = field(default_factory=dict)


def _parse_time(value: Any, default: time) -> time:
    if value is None:
        return default
    if isinstance(value, time):
        return value
    text = str(value).strip()
    try:
        parts = text.split(':')
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
        return time(hour=hour, minute=minute, second=second)
    except (ValueError, IndexError):
        return default


def _parse_bool(value: Any, default: bool) -> bool:
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


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default


def _parse_polling_windows(values: Iterable[Any] | None) -> tuple[PollingWindow, ...]:
    if not values:
        return ()
    windows: list[PollingWindow] = []
    for item in values:
        if not isinstance(item, str):
            continue
        if '-' not in item:
            continue
        start_raw, end_raw = item.split('-', maxsplit=1)
        start = _parse_time(start_raw, default=time(hour=0, minute=0))
        end = _parse_time(end_raw, default=time(hour=23, minute=59))
        windows.append(PollingWindow(start=start, end=end))
    return tuple(windows)


def _load_yaml(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        return {}
    content = config_path.read_text(encoding='utf-8') or ''
    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        raise ValueError('Top-level YAML config must be a mapping')
    return data


def _load_senders(raw: dict[str, Any] | None) -> dict[str, SenderConfig]:
    if not raw:
        return {}
    senders: dict[str, SenderConfig] = {}
    for name, config in raw.items():
        if not isinstance(config, dict):
            continue
        kind = str(config.get('kind', '')).strip().lower()
        if not kind:
            raise ValueError(f'sender {name} is missing a kind')
        senders[name] = SenderConfig(
            name=name,
            kind=kind,
            token_env=config.get('token_env'),
            url_env=config.get('url_env'),
            smtp_host_env=config.get('smtp_host_env'),
            smtp_user_env=config.get('smtp_user_env'),
            smtp_pass_env=config.get('smtp_pass_env'),
            from_addr=config.get('from'),
            to_addr=config.get('to'),
            chat_id=config.get('chat_id'),
        )
    return senders


def _load_areas(raw: dict[str, Any] | None, senders: dict[str, SenderConfig]) -> dict[str, AreaConfig]:
    if not raw:
        return {}
    areas: dict[str, AreaConfig] = {}
    for name, config in raw.items():
        if not isinstance(config, dict):
            continue
        senders_raw = config.get('senders') or []
        sender_names = tuple(str(s).strip() for s in senders_raw if str(s).strip())
        if not sender_names:
            raise ValueError(f'area {name} must specify at least one sender')
        unknown = [s for s in sender_names if s not in senders]
        if unknown:
            raise ValueError(f'area {name} references undefined senders: {", ".join(unknown)}')

        geojson_raw = config.get('geojson_path')
        if not geojson_raw:
            raise ValueError(f'area {name} is missing geojson_path')
        geojson_path = Path(str(geojson_raw)).expanduser()
        regions = load_geojson_regions(geojson_path)
        if not regions:
            raise ValueError(f'area {name} contains no polygons in {geojson_path}')

        areas[name] = AreaConfig(
            name=name,
            geojson_path=geojson_path,
            senders=sender_names,
            regions=tuple(regions),
        )
    return areas


def load_blitz_config(path: str | Path | None = None) -> BlitzConfig:
    config_path = Path(path or os.getenv('APP_CONFIG_PATH', 'config.yml')).expanduser()
    raw = _load_yaml(config_path)

    global_raw = raw.get('global', {}) if isinstance(raw, dict) else {}

    default_interval_env = os.getenv('BLITZ_DEFAULT_INTERVAL')
    peak_interval_env = os.getenv('BLITZ_PEAK_INTERVAL')
    peak_hours_env = os.getenv('BLITZ_PEAK_HOURS_UTC')
    if peak_hours_env:
        peak_hours_raw: Iterable[Any] | None = [p.strip() for p in peak_hours_env.split(',') if p.strip()]
    else:
        peak_hours_raw = global_raw.get('peak_hours_utc')
        if peak_hours_raw is None:
            peak_hours_raw = global_raw.get('peak_hours')

    polling = PollingConfig(
        default_interval_seconds=_parse_int(
            default_interval_env if default_interval_env is not None else global_raw.get('default_interval'),
            900,
        ),
        peak_interval_seconds=_parse_int(
            peak_interval_env if peak_interval_env is not None else global_raw.get('peak_interval'),
            300,
        ),
        peak_windows=_parse_polling_windows(peak_hours_raw),
    )

    reminder_raw = (global_raw or {}).get('reminder', {}) if isinstance(global_raw, dict) else {}
    reminder_enabled_env = os.getenv('BLITZ_REMINDER_ENABLE')
    reminder_max_days_env = os.getenv('BLITZ_REMINDER_MAX_DAYS')
    reminder_time_env = os.getenv('BLITZ_REMINDER_TIME_UTC')
    if reminder_time_env:
        reminder_time_value: Any = reminder_time_env
    else:
        reminder_time_value = reminder_raw.get('time_of_day_utc')
        if reminder_time_value is None:
            reminder_time_value = reminder_raw.get('time_of_day')

    reminder = ReminderConfig(
        enabled=_parse_bool(
            reminder_enabled_env if reminder_enabled_env is not None else reminder_raw.get('enable'),
            True,
        ),
        max_days=_parse_int(
            reminder_max_days_env if reminder_max_days_env is not None else reminder_raw.get('maximum_days'),
            3,
        ),
        time_of_day=_parse_time(reminder_time_value, time(hour=8, minute=0)),
    )

    poi_types_env = os.getenv('BLITZ_POI_TYPES')
    if poi_types_env:
        poi_types = tuple(t.strip() for t in poi_types_env.split(',') if t.strip()) or DEFAULT_POI_TYPES
    else:
        filters_raw = (global_raw or {}).get('filters') if isinstance(global_raw, dict) else None
        if isinstance(filters_raw, dict):
            parsed = tuple(str(t).strip() for t in filters_raw.get('types', []) if str(t).strip())
            poi_types = parsed or DEFAULT_POI_TYPES
        else:
            poi_types = DEFAULT_POI_TYPES
    global_filters = GlobalFilters(poi_types=poi_types)

    language_raw = os.getenv('BLITZ_LANGUAGE') or global_raw.get('language', 'en')
    language = str(language_raw).lower()
    if language not in {'en', 'de'}:
        language = 'en'

    senders = _load_senders(raw.get('senders') if isinstance(raw, dict) else {})
    areas = _load_areas(raw.get('areas') if isinstance(raw, dict) else {}, senders)

    return BlitzConfig(
        polling=polling,
        reminder=reminder,
        global_filters=global_filters,
        language=language,
        senders=senders,
        areas=areas,
    )
