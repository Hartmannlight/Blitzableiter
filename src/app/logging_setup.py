from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.config import AppConfig


class JsonFormatter(logging.Formatter):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'ts': datetime.now(UTC).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
            'level': record.levelname.lower(),
            'service': self._config.service_name,
            'logger': record.name,
            'instance': self._config.instance,
            'env': self._config.env,
            'msg': record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key.startswith('_'):
                continue
            if key in payload:
                continue
            if key in {
                'args',
                'msg',
                'name',
                'levelno',
                'levelname',
                'created',
                'msecs',
                'relativeCreated',
                'pathname',
                'filename',
                'module',
                'exc_info',
                'exc_text',
                'stack_info',
                'lineno',
                'funcName',
                'thread',
                'threadName',
                'processName',
                'process',
            }:
                continue
            payload[key] = value

        if record.levelno >= logging.ERROR and 'error' not in payload:
            payload['error'] = record.getMessage()

        if record.exc_info:
            payload['stack'] = self.formatException(record.exc_info)
            if record.exc_info[0]:
                payload['exception_type'] = record.exc_info[0].__name__

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(config: AppConfig) -> None:
    root = logging.getLogger()

    level_name = (config.log_level or 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(config))

    root.handlers.clear()
    root.addHandler(handler)
