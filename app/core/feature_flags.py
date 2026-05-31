from __future__ import annotations


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def parse_bool_env(raw_value: str | None, *, default: bool) -> bool:
    if raw_value is None:
        return default
    normalized = str(raw_value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def use_qml_customers_enabled(raw_value: str | None, *, default_flag: bool) -> bool:
    return parse_bool_env(raw_value, default=default_flag)

