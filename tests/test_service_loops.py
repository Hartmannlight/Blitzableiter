from __future__ import annotations

from app.config import AppConfig
from app.service_sync import Service


def _config() -> AppConfig:
    return AppConfig(
        service_name='svc',
        env='test',
        log_level='INFO',
        metrics_enabled=False,
        metrics_port=8000,
        loop_sleep_seconds=0.01,
        health_file='test-health.json',
        version='0.0.0',
        commit='test',
        config_source='test',
        instance='unit',
    )


def test_service_run_once_delegates() -> None:
    service = Service(_config())

    class Engine:
        def run_cycle(self) -> int:
            return 7

    service._engine = Engine()  # type: ignore[assignment]

    assert service.run_once() == 7


def test_service_start_stops_after_one_iteration() -> None:
    service = Service(_config())

    def _run_once() -> float:
        service.stop()
        return 0.0

    service.run_once = _run_once  # type: ignore[assignment]

    service.start()

    assert service._running is False


def test_service_start_handles_iteration_error() -> None:
    service = Service(_config())
    called = {'count': 0}

    def _run_once() -> float:
        called['count'] += 1
        service.stop()
        raise RuntimeError('boom')

    service.run_once = _run_once  # type: ignore[assignment]

    service.start()
    assert called['count'] == 1


def test_service_start_breaks_on_wait(monkeypatch) -> None:
    service = Service(_config())

    class FakeEvent:
        def __init__(self) -> None:
            self._set = False

        def clear(self) -> None:
            self._set = False

        def is_set(self) -> bool:
            return self._set

        def wait(self, timeout=None) -> bool:  # noqa: ARG002
            self._set = True
            return True

        def set(self) -> None:
            self._set = True

    service._stop_event = FakeEvent()  # type: ignore[assignment]
    service.run_once = lambda: 0.0  # type: ignore[assignment]

    service.start()
