from __future__ import annotations

from datetime import datetime

from app.ui.widgets.recipes_page import RecipesPage, _default_recipe_pdf_filename, _json_to_string_dict


def test_json_to_string_dict_returns_empty_for_blank_and_invalid_payloads() -> None:
    assert _json_to_string_dict("") == {}
    assert _json_to_string_dict("not json") == {}
    assert _json_to_string_dict('[1, 2]') == {}


def test_json_to_string_dict_stringifies_keys_and_values() -> None:
    raw = '{"a": 1, "b": true, "c": null}'

    assert _json_to_string_dict(raw) == {"a": "1", "b": "True", "c": "None"}


def test_parse_decimal_accepts_the_unit_suffixes_shown_in_recipe_totals() -> None:
    assert RecipesPage._parse_decimal("260,00 g") == 260.0
    assert RecipesPage._parse_decimal("12 Uds") == 12.0


def test_technical_escandallo_value_prefers_the_active_process_value() -> None:
    page = RecipesPage.__new__(RecipesPage)
    page.recipe_escandallo_data = {
        "costes_fijos": "2,00",
        "proceso::Masa final::costes_fijos": "3,50",
    }

    assert page._technical_escandallo_value("costes_fijos") == "3,50"


def test_default_recipe_pdf_filename_uses_recipe_customer_and_save_date() -> None:
    filename = _default_recipe_pdf_filename("Pan/Integral", "Cliente: Norte", datetime(2026, 8, 14))

    assert filename == "Pan-Integral-Cliente- Norte[2026-08-14].pdf"
