from __future__ import annotations

from app.ui.widgets.warehouse_page import _count_template_column_indexes, _count_template_mapping


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
