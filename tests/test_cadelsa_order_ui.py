import os
from datetime import date
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDialog

from app.services.cadelsa_order_import_service import CadelsaLine, CadelsaResolvedLine, CadelsaPreview
from app.ui.widgets import orders_page as module
from app.ui.widgets.cadelsa_order_preview_dialog import CadelsaOrderPreviewDialog


APP = None


def application():
    global APP
    APP = QApplication.instance() or QApplication([])
    return APP


def make_page(monkeypatch):
    application()
    monkeypatch.setattr(module.OrdersPage, "reload", lambda self: None)
    page = module.OrdersPage()
    page.almacen_filter.addItem("Todos", "")
    page.almacen_filter.addItem("CADELSA LZA (Cliente directo)", "cad")
    page.almacen_filter.addItem("IGSA (Distribuidor)", "igsa")
    return page


def test_button_requires_exact_selected_client_and_rejects_stale_text(monkeypatch):
    page = make_page(monkeypatch)
    assert page.cadelsa_btn.text() == "Imp CADELSA"
    assert not page.cadelsa_btn.isEnabled()
    page.almacen_filter.setCurrentIndex(1)
    assert page.cadelsa_btn.isEnabled()
    page.almacen_filter.setEditText("IGSA")
    assert not page.cadelsa_btn.isEnabled()
    page.almacen_filter.setCurrentIndex(2)
    assert not page.cadelsa_btn.isEnabled()
    page.close()


def test_preview_displays_quantities_date_and_blocks_issues():
    application()
    row = CadelsaResolvedLine(CadelsaLine("505", "Producto 12,5K", 60, 12.5), "a", "I505", "Producto", "Envase distinto")
    dialog = CadelsaOrderPreviewDialog(CadelsaPreview("cad", "hash", (row,)))
    assert not dialog.save_button.isEnabled()
    assert dialog.table.item(0, 5).text() == "750"
    dialog.order_date.setDate(QDate(2026, 10, 1))
    assert dialog.order_date.date().toPython() == date(2026, 10, 1)
    dialog.close()


def test_cancel_does_not_save_and_confirm_uses_program_date(monkeypatch):
    page = make_page(monkeypatch)
    page.almacen_filter.setCurrentIndex(1)
    calls = []
    preview = object()
    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *a: ("test.pdf", ""))
    monkeypatch.setattr(module, "CadelsaOrderImportService", lambda: SimpleNamespace(
        preview=lambda path, client: preview,
        save=lambda value, day: calls.append((value, day)) or "new-id",
    ))
    outcome = [QDialog.DialogCode.Rejected]
    monkeypatch.setattr(module, "CadelsaOrderPreviewDialog", lambda *a: SimpleNamespace(
        exec=lambda: outcome[0], order_date=SimpleNamespace(date=lambda: QDate(2026, 10, 1)),
    ))
    monkeypatch.setattr(module.QMessageBox, "information", lambda *a: None)
    monkeypatch.setattr(page, "_select_by_id", lambda value: None)
    page._import_cadelsa_order()
    assert calls == []
    outcome[0] = QDialog.DialogCode.Accepted
    page._import_cadelsa_order()
    assert calls == [(preview, date(2026, 10, 1))]
    page.close()
