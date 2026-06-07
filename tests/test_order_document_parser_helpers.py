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
