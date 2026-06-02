from __future__ import annotations

from app.ui.widgets.warehouse_page import (
    InventoryTabView,
    _count_template_column_indexes,
    _count_template_mapping,
)


def test_count_template_column_indexes_detects_required_columns() -> None:
    header = ["articulo_id", "lote", "conteo_uds", "otra"]

    assert _count_template_column_indexes(header) == (0, 1, 2)


def test_count_template_mapping_skips_blank_rows_and_uses_pair_key() -> None:
    rows = [
        ("A1", "L1", "10"),
        ("A1", "L2", ""),
        ("", "L3", "5"),
        ("A2", "", "7"),
    ]

    assert _count_template_mapping(rows, 0, 1, 2) == {("A1", "L1"): "10", ("A2", ""): "7"}


def test_inventory_tab_view_defaults_cover_labels_used_by_ui() -> None:
    view = InventoryTabView()

    assert view.intro_text == "Conteo físico por producto/lote. Edita 'Conteo Uds' y pulsa Aplicar ajustes."
    assert view.export_template_button_label == "Exportar plantilla"
    assert view.import_count_button_label == "Importar conteo"
    assert view.history_title == "Historial de inventarios"
    assert view.export_history_button_label == "Exportar historial"
