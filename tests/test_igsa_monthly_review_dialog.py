import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QAbstractItemView, QApplication

from app.services.igsa_monthly_review_service import Balance, MonthlyReview, ReviewIssue, ReviewLine, SourceLocation
from app.ui.widgets.igsa_monthly_review_dialog import IgsaMonthlyReviewDialog


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_review_displays_read_only_balances_and_source_locations(tmp_path):
    app()
    workbook = tmp_path / "igsa.xlsx"
    workbook.touch()
    pdf = tmp_path / "ventas.pdf"
    pdf.touch()
    excel_loc = SourceLocation("igsa.xlsx", "ventas", 27)
    pdf_loc = SourceLocation("ventas.pdf", page=3, item=2)
    lines = [ReviewLine("igsa", "venta", "A", "A", "Pan A", Decimal(3), "0001", excel_loc)]
    results = MonthlyReview(
        2026, 2,
        products=[Balance("muestra", "B", None, None, Decimal(1), None, "sin_correspondencia", (pdf_loc,)),
                  Balance("venta", "A", None, Decimal(3), Decimal(3), Decimal(0), "correcto", (excel_loc, pdf_loc))],
        lots=[Balance("venta", "A", "0001", Decimal(3), Decimal(3), Decimal(0), "correcto", (excel_loc, pdf_loc))],
        issues=[ReviewIssue("pdf_ausente", "Falta PDF de muestra")], lines=lines,
    )
    calls = []
    service = SimpleNamespace(compare=lambda *a, **k: calls.append((a, k)) or results)
    dialog = IgsaMonthlyReviewDialog(service=service)
    dialog.paths["excel"].setText(str(workbook))
    dialog.paths["venta"].setText(str(pdf))
    dialog.year.setValue(2026)
    dialog.month.setCurrentIndex(1)
    dialog.compare_button.click()
    assert calls == [((workbook, {"venta": pdf}), {"year": 2026, "month": 2})]
    assert dialog.product_table.rowCount() == 2
    assert dialog.product_table.item(0, 0).text() == "Venta"
    assert dialog.product_table.item(0, 1).text() == "Pan A"
    assert dialog.product_table.item(1, 4).text() == "—"
    assert "fila 27" in dialog.product_table.item(0, 8).text()
    assert "página 3" in dialog.product_table.item(0, 8).text()
    assert dialog.lot_table.item(0, 4).text() == "0001"
    assert dialog.issue_table.item(0, 1).text() == "Falta PDF de muestra"
    assert dialog.product_table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    dialog.only_differences.setChecked(True)
    assert dialog.product_table.rowCount() == 1
    assert dialog.product_table.item(0, 0).text() == "Muestra"
    dialog.close()


def test_changing_inputs_and_failed_comparison_clear_old_results(tmp_path):
    app()
    calls = []
    def compare(*args, **kwargs):
        calls.append(args)
        if len(calls) > 1:
            raise ValueError("archivo inválido")
        return MonthlyReview(2026, 2, products=[Balance("venta", "A", None, Decimal(1), Decimal(1), Decimal(0), "correcto", ())])
    dialog = IgsaMonthlyReviewDialog(service=SimpleNamespace(compare=compare))
    dialog.paths["excel"].setText(str(tmp_path / "igsa.xlsx"))
    dialog.compare_button.click()
    assert dialog.product_table.rowCount() == 1
    dialog.month.setCurrentIndex((dialog.month.currentIndex() + 1) % 12)
    assert dialog.product_table.rowCount() == 0
    assert dialog.tabs.tabText(2) == "Incidencias"
    dialog.compare_button.click()
    assert "archivo inválido" in dialog.message.text()
    assert dialog.product_table.rowCount() == 0
    dialog.paths["excel"].clear()
    dialog.compare_button.click()
    assert "Selecciona el Excel" in dialog.message.text()
    assert len(calls) == 2
    dialog.close()


def test_igsa_tools_exposes_preview_without_changing_import(monkeypatch):
    app()
    from app.ui.widgets import igsa_monthly_review_dialog, sales_page
    opened = []
    class Preview:
        def __init__(self, parent):
            opened.append(parent)
        def exec(self):
            opened.append("exec")
    monkeypatch.setattr(sales_page.SalesToolsDialog, "_refresh_history", lambda self: None)
    monkeypatch.setattr(igsa_monthly_review_dialog, "IgsaMonthlyReviewDialog", Preview)
    dialog = sales_page.SalesToolsDialog(mode="igsa")
    dialog.review_monthly_btn.click()
    assert opened == [dialog, "exec"]
    assert dialog.import_btn.isEnabled()
    dialog.close()


def test_preview_compares_real_workbook_and_pdf_without_altering_them(tmp_path):
    app()
    from openpyxl import Workbook
    from reportlab.pdfgen import canvas
    from app.services.igsa_monthly_catalog_service import IgsaMonthlyCatalog
    from app.services.igsa_monthly_review_service import IgsaMonthlyReviewService

    workbook = tmp_path / "febrero 26.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "ventas"
    sheet.append(["Año", 2026])
    sheet.append(["Mes", "Febrero"])
    sheet.append([1, "REFERENCIA ERRÓNEA", "Pan", 1, 3, "L.0001"])
    book.create_sheet("muestras")
    book.create_sheet("promociones")
    book.save(workbook)
    book.close()
    pdf = tmp_path / "ventas.pdf"
    document = canvas.Canvas(str(pdf))
    document.drawString(30, 800, "Ref. pedido: X 28/02/26 VENTAS Nº Pedido: Fecha entrega:")
    document.drawString(30, 780, "123 Pan 3,00 3 1,00 0 1,00 1,00 0Lote:0001Cons.Pref:12/05/27Carga:")
    document.drawString(30, 760, "Datos transporte Bultos:Peso:Portes:3 1.000 Pagados")
    document.save()
    before = (workbook.read_bytes(), pdf.read_bytes())
    ref = SimpleNamespace(articulo_referencia_distribuidor="1", articulo_id="P1")
    product = SimpleNamespace(articulo_id="P1", articulo_referencia_corta="123",
                              articulo_referencia="123", articulo_descripcion="Pan")
    service = IgsaMonthlyReviewService(catalog_provider=lambda: IgsaMonthlyCatalog([ref], [product]))
    dialog = IgsaMonthlyReviewDialog(service=service)
    dialog.paths["excel"].setText(str(workbook))
    dialog.paths["venta"].setText(str(pdf))
    dialog.year.setValue(2026)
    dialog.month.setCurrentIndex(1)
    dialog.compare_button.click()
    assert dialog.product_table.rowCount() == 1
    assert dialog.product_table.item(0, 2).text() == "1"
    assert dialog.product_table.item(0, 3).text() == "123"
    assert dialog.product_table.item(0, 4).text() == "3"
    assert dialog.product_table.item(0, 5).text() == "3"
    assert dialog.product_table.item(0, 7).text() == "Correcto"
    assert dialog.lot_table.item(0, 4).text() == "0001"
    assert dialog.issue_table.rowCount() >= 2  # Optional PDFs remain explicitly missing.
    assert (workbook.read_bytes(), pdf.read_bytes()) == before
    dialog.close()
