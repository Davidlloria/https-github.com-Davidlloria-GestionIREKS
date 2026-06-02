from __future__ import annotations

from app.ui.widgets.recipes_page import _json_to_string_dict


def test_json_to_string_dict_returns_empty_for_blank_and_invalid_payloads() -> None:
    assert _json_to_string_dict("") == {}
    assert _json_to_string_dict("not json") == {}
    assert _json_to_string_dict('[1, 2]') == {}


def test_json_to_string_dict_stringifies_keys_and_values() -> None:
    raw = '{"a": 1, "b": true, "c": null}'

    assert _json_to_string_dict(raw) == {"a": "1", "b": "True", "c": "None"}
