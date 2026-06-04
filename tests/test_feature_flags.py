from __future__ import annotations

from app.core.feature_flags import parse_bool_env, use_qml_customers_enabled


def test_parse_bool_env_uses_default_for_none_and_unknown_values() -> None:
    assert parse_bool_env(None, default=False) is False
    assert parse_bool_env(None, default=True) is True
    assert parse_bool_env("maybe", default=False) is False
    assert parse_bool_env("maybe", default=True) is True


def test_parse_bool_env_supports_common_true_false_values() -> None:
    for value in ("1", "true", "TRUE", "yes", "on"):
        assert parse_bool_env(value, default=False) is True
    for value in ("0", "false", "FALSE", "no", "off"):
        assert parse_bool_env(value, default=True) is False


def test_use_qml_customers_enabled_respects_env_and_default() -> None:
    assert use_qml_customers_enabled("1", default_flag=False) is True
    assert use_qml_customers_enabled("0", default_flag=True) is False
    assert use_qml_customers_enabled(None, default_flag=False) is False
    assert use_qml_customers_enabled(None, default_flag=True) is True

