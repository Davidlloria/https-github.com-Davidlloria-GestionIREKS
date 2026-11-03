import os
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.models import AlmacenCatalogo, AlmacenMovimiento, Cliente, IngredienteIreks, TarifaPrecioIreks
from app.services.customer_forecast_service import CustomerForecastService, ForecastLot, ForecastProduct
from app.ui.widgets.customer_forecast_dialog import CustomerForecastDialog, ForecastArticleDialog
from app.ui.widgets.customers_page import CustomersPage


@pytest.mark.parametrize("customer_type,distributor_id,tariff,expected", [
    ("indirecto", "", "IGSA", [Decimal("12.345"), None, None]),
    ("", "", "IGSA", [Decimal("12.345"), None, None]),
    ("distribuidor", "other", "IGSA", [Decimal("12.345"), None, None]),
    ("directo", "", "IREKS", [Decimal("99"), Decimal("99"), None]),
    (" DIRECTO ", "other", "IREKS", [Decimal("99"), Decimal("99"), None]),
])
def test_catalog_uses_customer_type_exact_year_and_active_products(customer_type, distributor_id, tariff, expected):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Cliente(cliente_id="c", cliente_tipo=customer_type, distribuidor_id=distributor_id),
            IngredienteIreks(articulo_id="a", distribuidor_id="d", articulo_descripcion="A"),
            IngredienteIreks(articulo_id="b", distribuidor_id="d", articulo_descripcion="B"),
            IngredienteIreks(articulo_id="c", distribuidor_id="other", articulo_descripcion="C"),
            IngredienteIreks(articulo_id="e", distribuidor_id="d", articulo_status_activo=False),
            TarifaPrecioIreks(articulo_id="a", tarifa_ano=2026, precio_distribuidor=12.345, precio_fabricante=99),
            TarifaPrecioIreks(articulo_id="b", tarifa_ano=2026, precio_distribuidor=0, precio_fabricante=99),
            TarifaPrecioIreks(articulo_id="b", tarifa_ano=2025, precio_distribuidor=10),
            TarifaPrecioIreks(articulo_id="c", tarifa_ano=2026, precio_distribuidor=0, precio_fabricante=0),
        ])
        session.commit()
    service = CustomerForecastService(engine)
    name, products = service.catalog("c", 2026)
    assert name == tariff
    assert [p.price for p in products] == expected
    assert service.amount(1, Decimal("12.345")) == Decimal("12.35")
    assert service.amount(3, Decimal("12.345")) == Decimal("37.04")
    assert service.amount(2, None) is None
    assert all(p.price is None for p in service.catalog("c", 2027)[1])
    with pytest.raises(ValueError, match="cliente"):
        service.catalog("missing", 2026)
    with pytest.raises(ValueError):
        service.amount(0, Decimal("2"))
    with Session(engine) as session:
        assert len(session.exec(select(TarifaPrecioIreks)).all()) == 4


class FakeService(CustomerForecastService):
    def __init__(self):
        pass

    def catalog(self, customer_id, year):
        return "IGSA", [ForecastProduct("Producto", Decimal("12.345")), ForecastProduct("Sin precio", None)]

    def lots(self, article_id):
        return []


_APP = None


def application():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_dialog_quantities_dates_duplicates_missing_price_and_discard(monkeypatch):
    application()
    dialog = CustomerForecastDialog(SimpleNamespace(cliente_id="c", cliente_nombre_comercial="Cliente"), service=FakeService())
    assert dialog.distributor.text() == "Tarifa aplicada: IGSA"
    dialog._add_line(dialog._catalog[0])
    dialog._add_line(dialog._catalog[0])
    assert dialog.table.rowCount() == 2
    assert not dialog.year.isEnabled()
    dialog.table.cellWidget(0, 1).setValue(3)
    assert dialog.table.item(0, 3).text() == "37,04"
    assert "49,39" in dialog.total.text()
    assert dialog.table.item(0, 6).text() == "Fechas pendientes"
    dialog.table.cellWidget(0, 4).setDate(QDate(2026, 11, 10))
    dialog.table.cellWidget(0, 5).setDate(QDate(2026, 11, 9))
    assert dialog.table.item(0, 6).text() == "Caduca antes de la entrega"
    dialog.table.cellWidget(0, 5).setDate(QDate(2027, 1, 10))
    assert dialog.table.item(0, 6).text() == ""
    dialog._add_line(dialog._catalog[1])
    assert "Incompleto" in dialog.total.text()
    assert dialog.table.item(2, 3).text() == "Pendiente"
    assert dialog.table.editTriggers() == dialog.table.EditTrigger.NoEditTriggers
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    dialog.show()
    dialog.reject()
    assert dialog.isVisible()
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    dialog.reject()
    assert not dialog.isVisible()
    dialog.deleteLater()


def test_dialog_load_failure_disables_add():
    application()
    service = FakeService()
    def fail(*args):
        raise ValueError("Sin distribuidor")
    service.catalog = fail
    dialog = CustomerForecastDialog(SimpleNamespace(cliente_id="c", cliente_nombre_comercial="Cliente"), service=service)
    assert not dialog.add_button.isEnabled()
    assert "Sin distribuidor" in dialog.distributor.text()
    dialog.close()


def test_customer_button_opens_selected_customer(monkeypatch):
    application()
    monkeypatch.setattr(CustomersPage, "reload", lambda self: None)
    page = CustomersPage()
    assert page.forecast_btn.text() == "Previsión"
    assert page.forecast_btn.toolTip() == "Preparar previsión de suministro"
    assert not page.forecast_btn.isEnabled()
    customer = SimpleNamespace(cliente_id="c")
    monkeypatch.setattr(page, "_selected_row", lambda: customer)
    calls = []
    monkeypatch.setattr("app.ui.widgets.customers_page.CustomerForecastDialog", lambda c, p: SimpleNamespace(exec=lambda: calls.append(c)))
    page.forecast_btn.setEnabled(True)
    page.forecast_btn.click()
    assert calls == [customer]
    page.close()


def test_lots_net_stock_separates_warehouses_dates_and_products():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    expiry = date(2027, 1, 1)
    with Session(engine) as session:
        session.add(AlmacenCatalogo(almacen_id="w1", almacen_nombre="Principal"))
        for warehouse, article, lot, cad, quantity in [
            ("w1", "a", "L1", expiry, 10),
            ("w1", "a", "L1", expiry, -4),
            ("w2", "a", "L1", expiry, 2),
            ("w1", "a", "L1", date(2027, 2, 1), 3),
            ("w1", "a", "L2", None, 4),
            ("w1", "a", "ZERO", expiry, 2),
            ("w1", "a", "ZERO", expiry, -2),
            ("w1", "a", "NEG", expiry, -1),
            ("w1", "other", "OTHER", expiry, 100),
        ]:
            session.add(AlmacenMovimiento(almacen_id=warehouse, articulo_id=article,
                articulo_lote=lot, articulo_caducidad=cad, cantidad=quantity))
        session.commit()
    lots = CustomerForecastService(engine).lots("a")
    assert len(lots) == 4
    assert [(l.warehouse_id, l.lot, l.available) for l in lots] == [
        ("w1", "L1", Decimal("6")), ("w2", "L1", Decimal("2")),
        ("w1", "L1", Decimal("3")), ("w1", "L2", Decimal("4")),
    ]
    assert lots[0].warehouse_name == "Principal"
    assert lots[-1].expiry is None
    assert CustomerForecastService(engine).lots("missing") == []
    with Session(engine) as session:
        assert sum(m.cantidad for m in session.exec(select(AlmacenMovimiento))) == 114


def test_occurrence_search_and_lot_lines(monkeypatch):
    application()
    service = FakeService()
    service.catalog = lambda *args: ("IGSA", [
        ForecastProduct("ABC123 · Mezcla centéno", Decimal("10"), "a"),
        ForecastProduct("XYZ · Trigo", Decimal("20"), "b"),
    ])
    service.lots = lambda article: [
        ForecastLot("w", "Principal", "L1", date(2027, 1, 1), Decimal("6")),
        ForecastLot("w", "Principal", "L2", date(2027, 2, 1), Decimal("4")),
    ] if article == "a" else []
    dialog = CustomerForecastDialog(SimpleNamespace(cliente_id="c", cliente_nombre_comercial="Cliente"), service=service)
    picker = ForecastArticleDialog(dialog._catalog, service)
    picker.search.setText("CENTENO bc12")
    assert picker.products.count() == 1
    assert picker.lots.rowCount() == 2
    assert not picker.add_button.isEnabled()
    picker.lots.selectRow(0)
    picker.add_button.click()
    assert picker.result() == picker.DialogCode.Accepted
    dialog._add_line(*picker.selection)
    dialog.table.cellWidget(0, 1).setValue(6)
    assert dialog.table.cellWidget(0, 5).date() == QDate(2027, 1, 1)
    assert not dialog.table.cellWidget(0, 5).isEnabled()
    second = ForecastArticleDialog(dialog._catalog, service)
    second.search.setText("bc12")
    second.lots.selectRow(1)
    second.lots.cellDoubleClicked.emit(1, 0)
    dialog._add_line(*second.selection)
    dialog.table.cellWidget(1, 1).setValue(4)
    assert dialog.table.cellWidget(1, 5).date() == QDate(2027, 2, 1)
    assert "100,00" in dialog.total.text()
    assert "supera" not in dialog.table.item(0, 6).text()
    dialog._add_line(*picker.selection)
    assert "supera" in dialog.table.item(0, 6).text()
    assert "supera" in dialog.status.text()
    dialog.remove_button.click()
    assert "supera" not in dialog.table.item(0, 6).text()
    picker.search.setText("no existe")
    assert picker.products.count() == 0
    assert picker.lots.rowCount() == 0
    assert not picker.add_button.isEnabled()
    assert not picker.unconfirmed.isEnabled()
    picker.search.setText("TRIG")
    assert picker.lots.rowCount() == 0
    picker.unconfirmed.click()
    dialog._add_line(*picker.selection)
    assert dialog.table.cellWidget(2, 5).isEnabled()
    assert dialog.table.item(2, 7).text() == "Sin confirmar"
    picker.search.clear()
    assert picker.products.count() == 2
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    dialog.close()


def test_add_article_opens_picker_and_cancel_keeps_forecast(monkeypatch):
    application()
    from app.ui.widgets import customer_forecast_dialog as module
    dialog = CustomerForecastDialog(SimpleNamespace(cliente_id="c", cliente_nombre_comercial="Cliente"), service=FakeService())
    assert dialog.add_button.text() == "Añadir artículo"
    assert not hasattr(dialog, "search")
    class Picker:
        selection = None
        def __init__(self, products, service, parent):
            self.selection = (products[0], None)
        def exec(self):
            return CustomerForecastDialog.DialogCode.Rejected
    monkeypatch.setattr(module, "ForecastArticleDialog", Picker)
    dialog.add_button.click()
    assert dialog.table.rowCount() == 0
    monkeypatch.setattr(Picker, "exec", lambda self: CustomerForecastDialog.DialogCode.Accepted)
    dialog.add_button.click()
    assert dialog.table.rowCount() == 1
    assert dialog.table.rowHeight(0) >= dialog.table.cellWidget(0, 4).sizeHint().height()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    dialog.close()


def test_text_inputs_keyboard_paste_validation_and_no_warehouse(monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit, QSpinBox
    application()
    dialog = CustomerForecastDialog(SimpleNamespace(cliente_id="c", cliente_nombre_comercial="Cliente"), service=FakeService())
    assert isinstance(dialog.year, QLineEdit)
    dialog.year.selectAll()
    QTest.keyClicks(dialog.year, "2027")
    assert dialog.year.value() == 2027
    dialog.year.clear()
    assert not dialog.add_button.isEnabled()
    dialog.year.setText("2026")
    assert dialog.add_button.isEnabled()
    lot = ForecastLot("w", "Nombre oculto", "LOTE123", date(2027, 1, 1), Decimal("100"))
    dialog._add_line(dialog._catalog[0], lot)
    quantity = dialog.table.cellWidget(0, 1)
    assert isinstance(quantity, QLineEdit)
    assert not isinstance(dialog.year, QSpinBox)
    assert not isinstance(quantity, QSpinBox)
    assert dialog.table.item(0, 7).text() == "LOTE123"
    quantity.selectAll()
    QTest.keyClicks(quantity, "12")
    assert quantity.value() == 12
    assert "148,14" in dialog.total.text()
    QApplication.clipboard().setText("25")
    quantity.selectAll()
    quantity.paste()
    assert quantity.value() == 25
    for bad in ("", "0", "1000001", "abc", "1.000"):
        quantity.setText(bad)
        assert not dialog.excel_button.isEnabled()
        assert "pendiente" in dialog.total.text()
    quantity.setText("3")
    assert dialog.excel_button.isEnabled()
    picker = ForecastArticleDialog(dialog._catalog, FakeService())
    assert picker.lots.columnCount() == 3
    assert all("almac" not in picker.lots.horizontalHeaderItem(c).text().lower() for c in range(3))
    picker.close()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    dialog.close()


def test_export_excel_cancel_failure_and_current_values(monkeypatch):
    from app.ui.widgets import customer_forecast_dialog as module
    application()
    dialog = CustomerForecastDialog(SimpleNamespace(cliente_id="c", cliente_nombre_comercial="Cliente"), service=FakeService())
    assert not dialog.excel_button.isEnabled()
    dialog._add_line(dialog._catalog[0])
    dialog.table.cellWidget(0, 1).setText("3")
    dialog.table.cellWidget(0, 4).setDate(QDate(2027, 2, 1))
    calls = []
    monkeypatch.setattr(module, "export_forecast_excel", lambda *args: calls.append(args))
    monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    dialog.excel_button.click()
    assert calls == []
    monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *args: ("test_forecast", ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    dialog.excel_button.click()
    assert calls[0][0] == "test_forecast.xlsx"
    assert calls[0][4][0][2:7] == [3, Decimal("12.345"), Decimal("37.04"), date(2027, 2, 1), None]
    errors = []
    def fail(*args):
        raise PermissionError("Archivo abierto")
    monkeypatch.setattr(module, "export_forecast_excel", fail)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: errors.append(args))
    dialog.excel_button.click()
    assert "Archivo abierto" in errors[0][2]
    assert dialog.table.rowCount() == 1
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    dialog.close()


def test_export_workbook_numbers_dates_pending_and_literal_text():
    from pathlib import Path
    from uuid import uuid4
    from openpyxl import load_workbook
    from app.services.customer_forecast_export_service import export_forecast_excel
    folder = Path(".tmp") / f"forecast-export-{uuid4().hex}"
    folder.mkdir(parents=True)
    path = folder / "forecast.xlsx"
    try:
        export_forecast_excel(path, "Cliente", "IGSA", 2026, [
            ["=PRODUCTO", "00123", 3, Decimal("12.345"), Decimal("37.04"), date(2027, 1, 1), date(2027, 2, 1), ""],
            ["Otro", "Sin confirmar", 2, None, None, None, None, "Fechas pendientes"],
        ])
        wb = load_workbook(path)
        ws = wb.active
        assert ws["A4"].data_type == "s"
        assert ws["A4"].value == "=PRODUCTO"
        assert ws["B4"].value == "00123"
        assert ws["C4"].value == 3
        assert ws["D4"].value == 12.345
        assert ws["E4"].value == 37.04
        assert ws["F4"].value.date() == date(2027, 1, 1)
        assert ws["F5"].value == "Pendiente"
        assert "Sin tarifa" in ws["H5"].value
        assert ws["E5"].value is None
        assert ws["A6"].value == "Subtotal valorado (incompleto)"
        assert ws["E6"].value == 37.04
        assert ws.freeze_panes == "A4"
        assert all("almac" not in str(c.value).lower() for row in ws for c in row)
        wb.close()
    finally:
        if path.exists():
            path.unlink()
        folder.rmdir()
