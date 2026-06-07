from app.services.order_document_parser import OrderDocumentParser


def test_words_to_factura_lines_groups_words_by_y_coordinate() -> None:
    words = [
        (10.0, 200.0, 20.0, 210.0, "A"),
        (30.0, 201.5, 40.0, 211.5, "B"),
        (15.0, 250.0, 25.0, 260.0, "C"),
    ]

    lines = OrderDocumentParser._words_to_factura_lines(words)

    assert len(lines) == 2
    assert [str(word[4]) for word in lines[0]["words"]] == ["A", "B"]
    assert [str(word[4]) for word in lines[1]["words"]] == ["C"]


def test_extract_factura_lote_from_follow_line_prefers_explicit_label() -> None:
    line = {
        "words": [
            (70.0, 100.0, 80.0, 110.0, "Lote:"),
            (110.0, 100.0, 150.0, 110.0, "2510061"),
            (190.0, 100.0, 220.0, 110.0, "Carga:"),
        ]
    }

    assert OrderDocumentParser._extract_factura_lote_from_follow_line(line) == "2510061"


def test_extract_factura_caducidad_from_follow_line_joins_split_date_parts() -> None:
    line = {
        "words": [
            (70.0, 100.0, 80.0, 110.0, "Caducidad:"),
            (110.0, 100.0, 125.0, 110.0, "01/10"),
            (132.0, 100.0, 155.0, 110.0, "/26"),
        ]
    }

    assert OrderDocumentParser._extract_factura_caducidad_from_follow_line(line) == "01/10/26"


def test_factura_column_text_normalizes_numeric_columns() -> None:
    line = {
        "words": [
            (430.0, 100.0, 440.0, 110.0, "4.910"),
            (445.0, 100.0, 455.0, 110.0, ",40"),
        ]
    }

    assert OrderDocumentParser._factura_column_text(line, 420, 460) == "4.910,40"


def test_factura_orphan_recovery_helpers_detect_candidate_and_follow_date() -> None:
    line = {
        "text": "Lote: 2510061 Carga:",
        "words": [
            (70.0, 100.0, 80.0, 110.0, "Lote:"),
            (110.0, 100.0, 150.0, 110.0, "2510061"),
            (190.0, 100.0, 220.0, 110.0, "Carga:"),
        ],
    }
    follow_lines = [
        line,
        {
            "words": [
                (70.0, 120.0, 80.0, 130.0, "Caducidad:"),
                (110.0, 120.0, 125.0, 130.0, "01/10"),
                (132.0, 120.0, 155.0, 130.0, "/26"),
            ]
        },
    ]

    assert OrderDocumentParser._factura_candidate_lote_from_line(line) == "2510061"
    assert OrderDocumentParser._factura_candidate_caducidad_from_follow_lines(follow_lines, 0) == "01/10/26"
    assert OrderDocumentParser._factura_has_core_fields(
        {
            "articulo_codigo": "123",
            "articulo_descripcion": "Producto",
            "articulo_cantidad": "1",
            "articulo_envase": "2",
            "articulo_kilos": "3",
            "precio_unitario": "4",
            "total_linea": "5",
        }
    )


def test_recover_factura_orphan_rows_with_ocr_uses_fake_ocr_and_dedupes(monkeypatch) -> None:
    calls: list[tuple[object, float, dict[str, str], str, str]] = []

    def fake_ocr(page: object, lote_line_y: float, header: dict[str, str], lote: str, caducidad: str) -> dict[str, object]:
        calls.append((page, lote_line_y, header, lote, caducidad))
        return {
            "factura_numero": header["factura_numero"],
            "factura_fecha": header["factura_fecha"],
            "albaran_numero": header["albaran_numero"],
            "factura_referencia": header["factura_referencia"],
            "articulo_codigo": "X001",
            "articulo_descripcion": "RECUPERADO",
            "articulo_cantidad": "1",
            "articulo_envase": "2",
            "articulo_kilos": "3",
            "articulo_lote": lote,
            "articulo_caducidad": caducidad,
            "precio_unitario": "4",
            "dto_pct": "20",
            "iva_pct": "0",
            "total_linea": "5",
        }

    monkeypatch.setattr(OrderDocumentParser, "_ocr_factura_article_line", fake_ocr)

    doc = [object()]
    header = {
        "factura_numero": "F001",
        "factura_fecha": "01/01/2026",
        "albaran_numero": "A001",
        "factura_referencia": "REF",
    }
    all_item_lines = [
        {
            "global_y": 100.0,
            "y": 100.0,
            "text": "Lote: 2510061",
            "words": [
                (70.0, 100.0, 80.0, 110.0, "Lote:"),
                (110.0, 100.0, 150.0, 110.0, "2510061"),
            ],
        },
        {
            "global_y": 120.0,
            "y": 120.0,
            "text": "Caducidad: 01/10/26",
            "words": [
                (70.0, 120.0, 80.0, 130.0, "Caducidad:"),
                (110.0, 120.0, 125.0, 130.0, "01/10"),
                (132.0, 120.0, 155.0, 130.0, "/26"),
            ],
        },
        {
            "global_y": 210.0,
            "y": 210.0,
            "text": "Lote: 2510061",
            "words": [
                (70.0, 210.0, 80.0, 220.0, "Lote:"),
                (110.0, 210.0, 150.0, 220.0, "2510061"),
            ],
        },
    ]
    rows = [
        {
            "articulo_codigo": "P001",
            "articulo_descripcion": "ORIGINAL",
            "articulo_cantidad": "1",
            "articulo_envase": "1",
            "articulo_kilos": "1",
            "precio_unitario": "1",
            "total_linea": "1",
            "articulo_lote": "P001",
        }
    ]

    merged = OrderDocumentParser._recover_factura_orphan_rows_with_ocr(doc, header, all_item_lines, rows)

    assert len(calls) == 1
    assert calls[0][3] == "2510061"
    assert calls[0][4] == "01/10/26"
    assert [row.get("articulo_lote") for row in merged].count("2510061") == 1
    assert [row.get("articulo_lote") for row in merged].count("P001") == 1
