from __future__ import annotations

import pytest

from app.config import _get_bool, _get_float, _get_int, _load_yaml_config
from tests.helpers import make_test_dir


def test_get_bool_variants() -> None:
    assert _get_bool('1', False) is True
    assert _get_bool('false', True) is False
    assert _get_bool(None, True) is True
    assert _get_bool(True, False) is True
    assert _get_bool('unknown', True) is True


def test_get_int_and_float_variants() -> None:
    assert _get_int('10', 1) == 10
    assert _get_int(None, 3) == 3
    assert _get_int('nope', 2) == 2
    assert _get_float('1.5', 0.0) == 1.5
    assert _get_float(None, 2.5) == 2.5
    assert _get_float('nope', 2.5) == 2.5


def test_load_yaml_config_returns_empty_when_missing() -> None:
    tmp = make_test_dir()
    path = tmp / 'missing.yml'

    assert _load_yaml_config(path) == {}


def test_load_yaml_config_rejects_non_mapping() -> None:
    tmp = make_test_dir()
    path = tmp / 'bad.yml'
    path.write_text('- bad\n', encoding='utf-8')

    with pytest.raises(ValueError):
        _load_yaml_config(path)
