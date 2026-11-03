import os
from decimal import Decimal
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.models import Cliente, IngredienteIreks, TarifaPrecioIreks
from app.services.customer_forecast_service import CustomerForecastService, ForecastProduct
from app.ui.widgets.customer_forecast_dialog import CustomerForecastDialog
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


_APP = None


def application():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_dialog_quantities_dates_duplicates_missing_price_and_discard(monkeypatch):
    application()
    dialog = CustomerForecastDialog(SimpleNamespace(cliente_id="c", cliente_nombre_comercial="Cliente"), service=FakeService())
    assert dialog.distributor.text() == "Tarifa aplicada: IGSA"
    dialog.add_button.click()
    dialog.add_button.click()
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
    dialog.products.setCurrentIndex(1)
    dialog.add_button.click()
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
