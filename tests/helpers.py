from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def make_test_dir() -> Path:
    base = Path.cwd() / '.test-work'
    base.mkdir(parents=True, exist_ok=True)
    path = base / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path
