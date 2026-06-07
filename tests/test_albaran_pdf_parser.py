import inspect
from pathlib import Path

from reportlab.pdfgen import canvas

import app.services.order_document_parser as order_document_parser
import app.services.order_document_factura_sidecar_service as order_document_factura_sidecar_service
import app.services.order_document_ocr_runtime_service as order_document_ocr_runtime_service
import app.services.address_catalog_service as address_catalog_service
import app.services.order_document_import_service as order_document_import_service
import app.services.order_service as order_service
import app.services.order_export_service as order_export_service
import app.services.order_query_service as order_query_service
import app.services.monthly_orders_service as monthly_orders_service
import app.services.ingredient_entity_service as ingredient_entity_service
import app.services.ingredient_ireks_service as ingredient_ireks_service
import app.services.ingredient_std_service as ingredient_std_service
import app.services.technician_service as technician_service
import app.services.distributor_service as distributor_service
import app.services.contact_service as contact_service
import app.services.course_service as course_service
import app.services.customer_service as customer_service
import app.services.provider_service as provider_service
import app.services.recipe_service as recipe_service
import app.services.settings_import_service as settings_import_service
import app.services.settings_maintenance_service as settings_maintenance_service
import app.services.warehouse_catalog_service as warehouse_catalog_service
import app.services.warehouse_inventory_service as warehouse_inventory_service
import app.services.warehouse_movement_service as warehouse_movement_service
import app.services.warehouse_reference_service as warehouse_reference_service
from app.services.order_document_parser import OrderDocumentParser


def _write_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path))
    y = 800
    for line in lines:
        pdf.drawString(40, y, line)
        y -= 14
    pdf.save()


def _write_factura_layout_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(40, 700, "Número: 60003")
    pdf.drawString(40, 684, "Fecha: 19/01/26")
    pdf.drawString(40, 668, "Página: 1")
    pdf.drawString(360, 700, "NIF: A38058947")
    pdf.drawString(360, 684, "Zona: 11")
    pdf.drawString(360, 668, "Referencia: DEPOSITO")
    pdf.drawString(360, 652, "Albarn: 2026090005")
    pdf.drawString(25, 570, "Código")
    pdf.drawString(73, 570, "Descripción")
    pdf.drawString(258, 570, "UM")
    pdf.drawString(303, 570, "Uds.")
    pdf.drawString(338, 570, "Env.")
    pdf.drawString(382, 570, "Kg/Lit.")
    pdf.drawString(434, 570, "Precio")
    pdf.drawString(468, 570, "Dto.")
    pdf.drawString(506, 570, "Total")
    pdf.drawString(552, 570, "IVA")
    pdf.drawString(25, 545, "D1329086")
    pdf.drawString(90, 545, "POWERFULLUNG MELOCOTON - MARACUYA")
    pdf.drawString(258, 545, "KG")
    pdf.drawString(303, 545, "198")
    pdf.drawString(338, 545, "5,00")
    pdf.drawString(382, 545, "990,00")
    pdf.drawString(434, 545, "6,20")
    pdf.drawString(468, 545, "20,0")
    pdf.drawString(506, 545, "4.910,40")
    pdf.drawString(552, 545, "0,0")
    pdf.drawString(73, 530, "Lote:")
    pdf.drawString(115, 530, "2510061")
    pdf.drawString(188, 530, "Carga:")
    pdf.showPage()
    pdf.drawString(73, 545, "Caducidad:")
    pdf.drawString(121, 545, "01/10/26")
    pdf.drawString(73, 250, "TOTAL KILOS:")
    pdf.drawString(148, 250, "990,00")
    pdf.drawString(73, 230, "IMPORTE NETO:")
    pdf.drawString(148, 230, "4.910,40")
    pdf.save()


def test_order_document_parser_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(order_document_parser)


def test_order_document_ocr_runtime_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(order_document_ocr_runtime_service)


def test_order_document_factura_sidecar_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(order_document_factura_sidecar_service)


def test_address_catalog_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(address_catalog_service)


def test_order_document_import_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(order_document_import_service)


def test_order_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(order_service)


def test_order_export_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(order_export_service)


def test_order_query_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(order_query_service)


def test_monthly_orders_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(monthly_orders_service)


def test_ingredient_entity_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(ingredient_entity_service)


def test_ingredient_ireks_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(ingredient_ireks_service)


def test_ingredient_std_service_is_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(ingredient_std_service)


def test_small_entity_services_are_ui_free() -> None:
    assert "PySide6" not in inspect.getsource(technician_service)
    assert "PySide6" not in inspect.getsource(distributor_service)
    assert "PySide6" not in inspect.getsource(contact_service)
    assert "PySide6" not in inspect.getsource(course_service)
    assert "PySide6" not in inspect.getsource(customer_service)
    assert "PySide6" not in inspect.getsource(provider_service)
    assert "PySide6" not in inspect.getsource(recipe_service)
    assert "PySide6" not in inspect.getsource(settings_import_service)
    assert "PySide6" not in inspect.getsource(settings_maintenance_service)
    assert "PySide6" not in inspect.getsource(warehouse_catalog_service)
    assert "PySide6" not in inspect.getsource(warehouse_inventory_service)
    assert "PySide6" not in inspect.getsource(warehouse_movement_service)
    assert "PySide6" not in inspect.getsource(warehouse_reference_service)


def test_ui_layer_has_no_direct_database_access() -> None:
    ui_root = Path("app/ui")
    forbidden = (
        "from sqlmodel import Session",
        "from sqlmodel import select",
        "from app.core.database import",
        "with Session(",
        "session.exec(",
        "engine.begin(",
    )
    offenders: list[str] = []
    for path in ui_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        matches = [token for token in forbidden if token in source]
        if matches:
            offenders.append(f"{path}: {', '.join(matches)}")
    assert offenders == []


def test_api_layer_uses_services_not_ui_or_database() -> None:
    api_root = Path("app/api")
    forbidden = (
        "app.ui",
        "app.viewmodels",
        "PySide6",
        "from sqlmodel",
        "from app.core.database",
        "with Session(",
        "session.exec(",
        "engine.begin(",
    )
    offenders: list[str] = []
    for path in api_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        matches = [token for token in forbidden if token in source]
        if matches:
            offenders.append(f"{path}: {', '.join(matches)}")
    assert offenders == []


def test_parse_albaran_pdf_keeps_alphanumeric_codes_and_ignores_transport(tmp_path: Path) -> None:
    pdf_path = tmp_path / "albaran.pdf"
    _write_pdf(
        pdf_path,
        [
            "PACKING LIST",
            "Numero:",
            "2026090075",
            "Fecha:",
            "12/05/26",
            "Fecha pedido:",
            "04/05/26",
            "N Pedido:",
            "1244",
            "Cod.Art.",
            "Descripcion",
            "Kilos",
            "Envases",
            "Fecha entrega:",
            "14/05/26",
            "D1749044",
            "AROMA VAINILLA PRIMA",
            "24,00",
            "24",
            "Lote:",
            "60182876",
            "Cons.Pref:",
            "29/07/28",
            "Carga:",
            "22200",
            "MELLA AMAPOLA",
            "25,00",
            "2",
            "Lote:",
            "00214395",
            "Cons.Pref:",
            "16/09/26",
            "Carga:",
            "Datos transporte",
            "Bultos:",
            "1.673",
            "18.644,40",
        ],
    )

    header, rows = OrderDocumentParser.parse_albaran_pdf(pdf_path)

    assert header["albaran_numero"] == "2026090075"
    assert header["albaran_fecha"] == "12/05/26"
    assert [row["articulo_codigo"] for row in rows] == ["D1749044", "22200"]
    assert rows[0]["articulo_lote"] == "60182876"
    assert rows[0]["articulo_caducidad"] == "29/07/28"


def test_article_code_candidates_include_unpadded_numeric_reference() -> None:
    assert OrderDocumentParser.article_code_candidates("08107") == ["08107", "8107", "008107"]


def test_parse_factura_pdf_accepts_three_digit_article_codes(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura_three_digit.pdf"
    _write_pdf(
        pdf_path,
        [
            "Número:",
            "60006",
            "Fecha:",
            "02/02/26",
            "Albarán:",
            "2026090015",
            "Código     Descripción                         UM      Uds.    Env.    Kg/Lit.    Precio  Dto.  Total IVA",
            "300        MALZPERLE PLUS                      KG      1       25,00   25,00      5,15    20,0  103,00 0,0",
            "           Lote: 8320702       Carga:",
        ],
    )

    _header, rows = OrderDocumentParser.parse_factura_pdf(pdf_path)

    assert len(rows) == 1
    assert rows[0]["articulo_codigo"] == "300"
    assert rows[0]["articulo_lote"] == "8320702"


def test_parse_decimal_es_accepts_dot_decimal_without_treating_it_as_thousands() -> None:
    assert OrderDocumentParser.parse_decimal_es("19.40") == 19.4
    assert OrderDocumentParser.parse_decimal_es("20.0") == 20.0
    assert OrderDocumentParser.parse_decimal_es("1.596,00") == 1596.0
    assert OrderDocumentParser.parse_decimal_es("1.596") == 1596.0


def test_parse_factura_ocr_article_line_from_rendered_text() -> None:
    row = OrderDocumentParser.parse_factura_ocr_article_line(
        "00100 MALTA BACKEXTRAKT KG 1 15,00 15,00 3,85 20,0 46,20 0,0",
        {"factura_numero": "60015", "factura_fecha": "16/03/26", "albaran_numero": "2026090040"},
        "M292726",
        "14/09/26",
    )

    assert row is not None
    assert row["articulo_codigo"] == "00100"
    assert row["articulo_descripcion"] == "MALTA BACKEXTRAKT"
    assert row["articulo_lote"] == "M292726"
    assert row["precio_unitario"] == "3,85"
    assert row["total_linea"] == "46,20"


def test_parse_factura_pdf_extracts_header_items_and_totals(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura.pdf"
    _write_pdf(
        pdf_path,
        [
            "Número:",
            "60027",
            "Fecha:",
            "12/05/26",
            "Referencia:",
            "DEP.14/05 +1",
            "Albarán:",
            "2026090075",
            "Código     Descripción                         UM      Uds.    Env.    Kg/Lit.    Precio  IVA   Total",
            "08107      BRIOCHE-MIX GLUTEN FREE              KG      3       12,50   37,50      5,90    20,0  177,00",
            "           Lote: 9080504        Carga:",
            "           Caducidad: 22/07/28",
            "D1749044   AROMA VAINILLA PRIMA                 KG      24      1,00    24,00      10,83   20,0  207,94",
            "           Lote: 60182876       Carga:",
            "           Caducidad: 29/07/28",
            "TOTAL KILOS:",
            "61,50",
            "IMPORTE NETO:",
            "384,94",
            "TOTAL:",
            "384,94",
        ],
    )

    header, rows = OrderDocumentParser.parse_factura_pdf(pdf_path)

    assert header["factura_numero"] == "60027"
    assert header["factura_fecha"] == "12/05/26"
    assert header["albaran_numero"] == "2026090075"
    assert header["total_factura"] == "384,94"
    assert [row["articulo_codigo"] for row in rows] == ["08107", "D1749044"]
    assert rows[0]["articulo_lote"] == "9080504"
    assert rows[0]["articulo_caducidad"] == "22/07/28"


def test_parse_factura_pdf_uses_fixed_layout_and_continued_detail_lines(tmp_path: Path) -> None:
    pdf_path = tmp_path / "factura_layout.pdf"
    _write_factura_layout_pdf(pdf_path)

    header, rows = OrderDocumentParser.parse_factura_pdf(pdf_path)

    assert header["factura_numero"] == "60003"
    assert header["factura_fecha"] == "19/01/26"
    assert header["albaran_numero"] == "2026090005"
    assert header["total_factura"] == "4.910,40"
    assert len(rows) == 1
    assert rows[0]["articulo_codigo"] == "D1329086"
    assert rows[0]["articulo_lote"] == "2510061"
    assert rows[0]["articulo_caducidad"] == "01/10/26"
    assert rows[0]["dto_pct"] == "20,0"
    assert rows[0]["iva_pct"] == "0,0"
