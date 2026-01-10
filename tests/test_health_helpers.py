from __future__ import annotations

from pathlib import Path

from app.health_state import check_heartbeat, write_heartbeat


def test_check_heartbeat_missing(tmp_path: Path) -> None:
    missing = tmp_path / 'missing.json'
    result = check_heartbeat(missing, loop_sleep_seconds=5.0, now=100.0)
    assert 'health file missing' in result


def test_check_heartbeat_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / 'health.json'
    path.write_text('bad', encoding='utf-8')
    result = check_heartbeat(path, loop_sleep_seconds=5.0, now=100.0)
    assert 'health file unreadable' in result


def test_check_heartbeat_stale(tmp_path: Path) -> None:
    path = tmp_path / 'health.json'
    write_heartbeat(path, now=0.0)
    result = check_heartbeat(path, loop_sleep_seconds=5.0, now=100.0)
    assert 'last iteration too old' in result


def test_check_heartbeat_ok(tmp_path: Path) -> None:
    path = tmp_path / 'health.json'
    write_heartbeat(path, now=100.0)
    assert check_heartbeat(path, loop_sleep_seconds=5.0, now=105.0) is None
