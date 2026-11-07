from decimal import Decimal
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

import app.services.igsa_monthly_review_service as review_module
import app.services.igsa_sales_pdf_flow_service as pdf_module
import app.services.igsa_sales_workbook_flow_service as workbook_module
from app.services.igsa_monthly_review_service import IgsaMonthlyReviewService


def make_workbook(path: Path):
    book = Workbook()
    sheet = book.active
    sheet.title = "ventas febrero"
    sheet.append(["Año", 2026])
    sheet.append(["Mes", "Febrero"])
    sheet.append([1, "123", "Espelta", 25, 97, "59L.8494305", "30L.8494302", "7L.8736704"])
    sheet.append([2, "555", "Molde", 1, 13])
    sheet.append([3, "777", "Anómalo", 1, 54, "54L..8691003"])
    sheet.append([4, "888", "Sin reparto", 1, 5, "L.0001", "L.0002"])
    sheet.append([5, "999", "Único", 1, 5, "L.0001"])
    sheet = book.create_sheet("muestras")
    sheet.append([6, "111", "Muestra", 1, 1, "L.0001", "01/01/2027"])
    book.create_sheet("promociones")
    book.create_sheet("informe").append([1, "111", "No es una muestra", 1, 100, "L.123"])
    book.save(path)


def test_comparison_preserves_lots_and_repartition_issues(tmp_path, monkeypatch):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    before = path.read_bytes()
    class Page:
        def extract_text(self):
            return ("Ref. pedido: X 28/02/26 Fecha entrega: " + "".join(
                f"123 Espelta {q},00 {q} 1,00 0 1,00 1,00 0Lote:{lot}Cons.Pref:12/05/27Carga:"
                for q, lot in [(59, "8494305"), (30, "8494302"), (7, "8736704")]
            ) + "Datos transporte Bultos:Peso:Portes:96 1.000 Pagados")
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[Page()]))
    def reject_database(*args, **kwargs):
        raise AssertionError("La revisión no debe abrir una sesión de base de datos")
    monkeypatch.setattr(pdf_module, "Session", reject_database)
    monkeypatch.setattr(workbook_module, "Session", reject_database)
    result = IgsaMonthlyReviewService().compare(path, {"venta": tmp_path / "ventas.pdf"}, year=2026, month=2)
    product = next(x for x in result.products if x.product == "123")
    assert (product.igsa, product.ireks, product.difference, product.status) == (Decimal(97), Decimal(96), Decimal(1), "revisar_reparto")
    lots = [x for x in result.lots if x.product == "123"]
    assert len(lots) == 3 and all(x.difference == 0 for x in lots)
    assert any(x.page == 1 and x.item == 2 for x in lots[1].locations + lots[0].locations + lots[2].locations)
    assert {x.code for x in result.issues} >= {"reparto", "sin_lote", "lote_no_reconocido", "reparto_desconocido", "pdf_ausente"}
    assert not any(x.description == "No es una muestra" for x in result.lines)
    assert [x.lot for x in result.lines if x.product == "111"] == ["0001"]
    unknown = [x for x in result.lots if x.product == "888"]
    assert all(x.igsa is None for x in unknown)
    assert all(x.status == "revisar_reparto" for x in unknown)
    assert next(x for x in result.lots if x.product == "999").igsa == 5
    assert path.read_bytes() == before


def test_aliases_are_explicit_and_missing_sources_are_not_zero(tmp_path, monkeypatch):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    class Page:
        def extract_text(self):
            return "Ref. pedido: X 28/02/26 Fecha entrega: D123 Otro nombre 97,00 97 1,00 0 1,00 1,00 0Lote:8494305Cons.Pref:12/05/27Carga:Datos transporte Bultos:Peso:Portes:97 1.000 Pagados"
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[Page()]))
    service = IgsaMonthlyReviewService()
    without = service.compare(path, {"venta": Path("ventas.pdf")}, year=2026, month=2)
    assert next(x for x in without.products if x.product == "123").ireks is None
    with_alias = service.compare(path, {"venta": Path("ventas.pdf")}, year=2026, month=2, aliases={"D123": "123"})
    row = next(x for x in with_alias.products if x.product == "123")
    assert (row.igsa, row.ireks) == (97, 97)
    with pytest.raises(ValueError):
        service.compare(path, {}, year=2026, month=13)


def test_scanned_pdf_and_missing_workbook_sheets(tmp_path, monkeypatch):
    path = tmp_path / "test.xlsx"
    book = Workbook()
    book.active.title = "ventas"
    book.save(path)
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "")]))
    result = IgsaMonthlyReviewService().compare(path, {"venta": Path("scan.pdf")}, year=2026, month=2)
    assert {i.code for i in result.issues} >= {"pdf_sin_texto", "pdf_sin_lineas", "hoja_ausente", "pdf_ausente"}


def test_pdf_short_reference_and_missing_expiry_are_not_discarded(tmp_path, monkeypatch):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    text = ("Ref. pedido: X 28/02/26 Fecha entrega: "
            "555 BANDEJA 13,00 13 1,00 0 1,00 1,00 0Lote:310722Cons.Pref:Carga:"
            "Datos transporte Bultos:Peso:Portes:13 1.000 Pagados")
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text)]))
    result = IgsaMonthlyReviewService().compare(path, {"venta": Path("ventas.pdf")}, year=2026, month=2)
    row = next(r for r in result.lines if r.source == "ireks")
    assert (row.reference, row.quantity, row.lot) == ("555", 13, "310722")
    assert "caducidad_pdf_ausente" in {i.code for i in result.issues}
    assert "total_pdf" not in {i.code for i in result.issues}


def test_incomplete_pdf_does_not_report_a_confirmed_match(tmp_path, monkeypatch):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    text = ("Ref. pedido: X 28/02/26 Fecha entrega: "
            "999 ÚNICO 5,00 5 1,00 0 1,00 1,00 0Lote:0001Cons.Pref:12/05/27Carga:"
            "Datos transporte Bultos:Peso:Portes:6 1.000 Pagados")
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text)]))
    result = IgsaMonthlyReviewService().compare(path, {"venta": Path("ventas.pdf")}, year=2026, month=2)
    assert next(r for r in result.products if r.product == "999").status == "fuente_incompleta"
    assert "total_pdf" in {i.code for i in result.issues}


def test_duplicate_lines_are_reported_and_not_discarded(tmp_path, monkeypatch):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    book = review_module.load_workbook(path)
    book["ventas febrero"].append([5, "999", "Único", 1, 5, "L.0001"])
    book.save(path)
    book.close()
    text = ("Ref. pedido: X 28/02/26 Fecha entrega: "
            "999 ÚNICO 10,00 10 1,00 0 1,00 1,00 0Lote:0001Cons.Pref:12/05/27Carga:"
            "Datos transporte Bultos:Peso:Portes:10 1.000 Pagados")
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text)]))
    result = IgsaMonthlyReviewService().compare(path, {"venta": Path("ventas.pdf")}, year=2026, month=2)
    row = next(r for r in result.products if r.product == "999")
    assert (row.igsa, row.ireks, row.status) == (10, 10, "posible_duplicado")
    assert sum(i.code == "posible_duplicado" for i in result.issues) == 2


def test_conflicting_workbook_period_cannot_be_confirmed(tmp_path, monkeypatch):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    book = review_module.load_workbook(path)
    book["ventas febrero"]["B2"] = "Enero"
    book.save(path)
    book.close()
    text = ("Ref. pedido: X 28/02/26 Fecha entrega: "
            "999 ÚNICO 5,00 5 1,00 0 1,00 1,00 0Lote:0001Cons.Pref:12/05/27Carga:"
            "Datos transporte Bultos:Peso:Portes:5 1.000 Pagados")
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text)]))
    result = IgsaMonthlyReviewService().compare(path, {"venta": Path("ventas.pdf")}, year=2026, month=2)
    assert "periodo" in {i.code for i in result.issues}
    assert next(r for r in result.products if r.product == "999").status == "fuente_incompleta"


def test_wrong_document_type_and_unparsed_lot_are_reported(tmp_path, monkeypatch):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    text = ("Ref. pedido: X 28/02/26 MUESTRAS Nº Pedido: Fecha entrega: "
            "999 ÚNICO 5,00 5 1,00 0 1,00 1,00 0Lote:0001Cons.Pref:12/05/27Carga:"
            "Artículo ilegible Lote:OTRO Datos transporte Bultos:Peso:Portes:5 1.000 Pagados")
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text)]))
    result = IgsaMonthlyReviewService().compare(path, {"venta": Path("ventas.pdf")}, year=2026, month=2)
    assert {i.code for i in result.issues} >= {"tipo_pdf", "lineas_pdf_incompletas"}
    assert next(r for r in result.products if r.product == "999").status == "fuente_incompleta"


def test_invalid_or_negative_workbook_quantity_marks_source_incomplete(tmp_path, monkeypatch):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    book = review_module.load_workbook(path)
    book["ventas febrero"].append([8, "444", "Cantidad inválida", 1, "tres", "L.123"])
    book["ventas febrero"].append([9, "445", "Cantidad negativa", 1, -1, "L.124"])
    book.save(path)
    book.close()
    text = ("Ref. pedido: X 28/02/26 Fecha entrega: "
            "999 ÚNICO 5,00 5 1,00 0 1,00 1,00 0Lote:0001Cons.Pref:12/05/27Carga:"
            "Datos transporte Bultos:Peso:Portes:5 1.000 Pagados")
    monkeypatch.setattr(review_module, "PdfReader", lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text)]))
    result = IgsaMonthlyReviewService().compare(path, {"venta": Path("ventas.pdf")}, year=2026, month=2)
    assert sum(i.code == "cantidad_excel" for i in result.issues) == 2
    assert next(r for r in result.products if r.product == "999").status == "fuente_incompleta"


def test_samples_read_all_lots_and_ignore_expiry_and_recipient(tmp_path):
    path = tmp_path / "febrero 26.xlsx"
    make_workbook(path)
    book = review_module.load_workbook(path)
    sheet = book["muestras"]
    sheet.append([2415, "18921", "SINGLUPLUS", 12.5, 56,
                  "12L.8200116", "17L.8200115", "27L8200116", None, "CAD 04/2026"])
    sheet.append([10, "121", "Muestra con fecha Excel", 1, 3,
                  "1L.0001", datetime(2027, 4, 19), "2L.0002", "DAVID"])
    sheet.append([11, "122", "Muestra con fecha texto", 1, 1,
                  "L.0003", "19/10/2026", "CAD. 04/2027", "2028-03-01"])
    sheet.append([12, "123", "Lote con guion", 1, 2, "1L.0004", "1234-5678"])
    book.save(path)
    book.close()

    result = IgsaMonthlyReviewService().compare(path, {}, year=2026, month=2)
    rows = [row for row in result.lots if row.kind == "muestra" and row.product == "18921"]
    assert {row.lot: row.igsa for row in rows} == {"8200116": 39, "8200115": 17}
    assert next(row for row in result.products if row.kind == "muestra" and row.product == "18921").igsa == 56
    assert not any(issue.code in {"reparto", "lote_no_reconocido", "reparto_desconocido"}
                   and issue.location and issue.location.sheet == "muestras" and issue.location.row == 2
                   for issue in result.issues)
    assert {row.lot: row.igsa for row in result.lots if row.product == "121"} == {"0001": 1, "0002": 2}
    assert [row.lot for row in result.lots if row.product == "122"] == ["0003"]
    assert "1234-5678" in [row.lot for row in result.lots if row.product == "123"]
