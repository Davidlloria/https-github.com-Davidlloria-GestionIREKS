import fitz
import pytest

from app.services.order_document_parser import OrderDocumentParser as Parser


def invoice_page(document, number, code="8102", lot="L000001", total="20,00", price="1,00", continued=False):
    page = document.new_page(width=595, height=842)
    for x, y, text in ((40, 180, "Número:"), (90, 180, number),
                       (40, 192, "Fecha:"), (90, 192, "13/10/26"),
                       (276, 222, "Albarán:"), (336, 222, "2026090131"),
                       (20, 240, "Código"), (70, 240, "Descripción"),
                       (20, 270, code), (70, 270, "PRODUCTO PRUEBA"), (260, 270, "KG"),
                       (305, 270, "2"), (335, 270, "12,50"), (380, 270, "25,00"),
                       (430, 270, price), (470, 270, "20,0"), (510, 270, total), (550, 270, "0,0"),
                       (73, 282, "Lote:"), (115, 282, lot),
                       (73, 294, "Caducidad:"), (125, 294, "09/02/28")):
        page.insert_text((x, y), text, fontsize=8)
    if not continued:
        for x, y, text in ((40, 620, "IMPORTE NETO:"), (310, 620, total),
                           (430, 740, "TOTAL:"), (480, 740, total)):
            page.insert_text((x, y), text, fontsize=8)


def test_bundle_keeps_invoice_headers_totals_and_ignores_delivery_instructions(tmp_path):
    source = tmp_path / "facturas.pdf"
    with fitz.open() as document:
        invoice_page(document, "60062")
        invoice_page(document, "60063", lot="L000002", continued=True)
        invoice_page(document, "60063", lot="L000003", total="40,00", price="2,00")
        document.new_page().insert_text((40, 180), "INSTRUCCIONES DE ENTREGA")
        document.save(source)
    header, rows = Parser.parse_facturas_pdf(source)
    assert header["factura_numero"] == "60062, 60063"
    assert header["albaran_numero"] == "2026090131"
    assert [row["factura_numero"] for row in rows] == ["60062", "60063", "60063"]
    assert [row["articulo_lote"] for row in rows] == ["L000001", "L000002", "L000003"]
    assert rows[0]["_factura_header"]["total_factura"] == "20,00"
    assert rows[-1]["_factura_header"]["total_factura"] == "40,00"


def test_unknown_non_instruction_page_is_rejected(tmp_path):
    source = tmp_path / "ilegible.pdf"
    with fitz.open() as document:
        invoice_page(document, "60062")
        document.new_page().insert_text((40, 180), "Documento sin cabecera identificable")
        document.save(source)
    with pytest.raises(ValueError, match="página 2"):
        Parser.parse_facturas_pdf(source)


def test_missing_price_is_recovered_from_amount_and_discount_and_flagged(tmp_path):
    source = tmp_path / "precio.pdf"
    with fitz.open() as document:
        invoice_page(document, "60062", price="")
        document.save(source)
    _, rows = Parser.parse_facturas_pdf(source)
    assert rows[0]["precio_unitario"] == "1,00"
    assert rows[0]["_numeric_recovered"] is True


def test_split_lot_is_preserved_and_explicit_zero_is_not_a_missing_price(tmp_path):
    source = tmp_path / "promocion.pdf"
    with fitz.open() as document:
        invoice_page(document, "60062", lot="111", price="0,00", total="0,00")
        document[0].insert_text((133, 282), ".260827", fontsize=8)
        document.save(source)
    _, rows = Parser.parse_facturas_pdf(source)
    assert rows[0]["articulo_lote"] == "111.260827"
    assert rows[0]["_precio_cero_explicito"] is True
