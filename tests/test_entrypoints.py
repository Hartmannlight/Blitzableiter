from __future__ import annotations

from app.config import AppConfig


def _config() -> AppConfig:
    return AppConfig(
        service_name='svc',
        env='test',
        log_level='INFO',
        metrics_enabled=False,
        metrics_port=8000,
        loop_sleep_seconds=1.0,
        health_file='test-health.json',
        version='0.0.0',
        commit='test',
        config_source='test',
        instance='unit',
    )


def test_main_sync_happy_path(monkeypatch) -> None:
    from app import main_sync

    class FakeService:
        def __init__(self, config):  # noqa: ARG002
            self.started = False

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            pass

    fake_service = FakeService(_config())

    monkeypatch.setattr(main_sync, 'load_dotenv', lambda: None)
    monkeypatch.setattr(main_sync, 'load_config', lambda: _config())
    monkeypatch.setattr(main_sync, 'configure_logging', lambda config: None)
    monkeypatch.setattr(main_sync, 'start_metrics_server', lambda config: None)
    monkeypatch.setattr(main_sync, 'Service', lambda config: fake_service)

    main_sync.main()

    assert fake_service.started is True


def test_main_sync_keyboard_interrupt_calls_shutdown(monkeypatch) -> None:
    from app import main_sync

    state = {'stopped': False, 'shutdown': False}

    class FakeService:
        def __init__(self, config):  # noqa: ARG002
            pass

        def start(self) -> None:
            raise KeyboardInterrupt

        def stop(self) -> None:
            state['stopped'] = True

    monkeypatch.setattr(main_sync, 'load_dotenv', lambda: None)
    monkeypatch.setattr(main_sync, 'load_config', lambda: _config())
    monkeypatch.setattr(main_sync, 'configure_logging', lambda config: None)
    monkeypatch.setattr(main_sync, 'start_metrics_server', lambda config: None)
    monkeypatch.setattr(main_sync, 'mark_shutdown', lambda: state.__setitem__('shutdown', True))
    monkeypatch.setattr(main_sync, 'Service', FakeService)

    main_sync.main()

    assert state['stopped'] is True
    assert state['shutdown'] is True


def test_main_sync_crash_exits(monkeypatch) -> None:
    from app import main_sync

    class FakeService:
        def __init__(self, config):  # noqa: ARG002
            pass

        def start(self) -> None:
            raise RuntimeError('boom')

        def stop(self) -> None:
            pass

    monkeypatch.setattr(main_sync, 'load_dotenv', lambda: None)
    monkeypatch.setattr(main_sync, 'load_config', lambda: _config())
    monkeypatch.setattr(main_sync, 'configure_logging', lambda config: None)
    monkeypatch.setattr(main_sync, 'start_metrics_server', lambda config: None)
    monkeypatch.setattr(main_sync, 'Service', FakeService)
    monkeypatch.setattr(main_sync.sys, 'exit', lambda code: (_ for _ in ()).throw(SystemExit(code)))

    try:
        main_sync.main()
        assert False, 'Expected SystemExit'
    except SystemExit as exc:
        assert exc.code == 1


def test_main_sync_signal_handler(monkeypatch) -> None:
    from app import main_sync

    state = {'stopped': False, 'shutdown': False}

    class FakeService:
        def __init__(self, config):  # noqa: ARG002
            pass

        def start(self) -> None:
            return None

        def stop(self) -> None:
            state['stopped'] = True

    handlers = {}

    def _signal(sig, handler):
        handlers[sig] = handler

    monkeypatch.setattr(main_sync, 'load_dotenv', lambda: None)
    monkeypatch.setattr(main_sync, 'load_config', lambda: _config())
    monkeypatch.setattr(main_sync, 'configure_logging', lambda config: None)
    monkeypatch.setattr(main_sync, 'start_metrics_server', lambda config: None)
    monkeypatch.setattr(main_sync, 'mark_shutdown', lambda: state.__setitem__('shutdown', True))
    monkeypatch.setattr(main_sync, 'Service', FakeService)
    monkeypatch.setattr(main_sync.signal, 'signal', _signal)

    main_sync.main()

    handlers[main_sync.signal.SIGTERM](main_sync.signal.SIGTERM, None)
    assert state['stopped'] is True
    assert state['shutdown'] is True


def test_main_sync_signal_registration_failure(monkeypatch) -> None:
    from app import main_sync

    class FakeService:
        def __init__(self, config):  # noqa: ARG002
            pass

        def start(self) -> None:
            return None

        def stop(self) -> None:
            pass

    def _signal(sig, handler):  # noqa: ARG001
        raise RuntimeError('no signal')

    monkeypatch.setattr(main_sync, 'load_dotenv', lambda: None)
    monkeypatch.setattr(main_sync, 'load_config', lambda: _config())
    monkeypatch.setattr(main_sync, 'configure_logging', lambda config: None)
    monkeypatch.setattr(main_sync, 'start_metrics_server', lambda config: None)
    monkeypatch.setattr(main_sync, 'Service', FakeService)
    monkeypatch.setattr(main_sync.signal, 'signal', _signal)

    main_sync.main()
