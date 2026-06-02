from __future__ import annotations

from app.ui.widgets.recipes_page import _normalize_process_name, _unique_process_names


def test_normalize_process_name_returns_default_for_blank_values() -> None:
    assert _normalize_process_name("") == "Masa final"
    assert _normalize_process_name("   ") == "Masa final"


def test_unique_process_names_keeps_order_and_includes_masa_final() -> None:
    assert _unique_process_names(["Mezcla", "", "Fermentacion", "Mezcla"]) == ["Mezcla", "Masa final", "Fermentacion"]


def test_unique_process_names_preserves_existing_masa_final_at_front() -> None:
    assert _unique_process_names(["Masa final", "Masa final", "Amasado"]) == ["Masa final", "Amasado"]
