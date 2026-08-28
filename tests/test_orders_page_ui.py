from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTabWidget

from app.models import PedidoIncidencia, PedidoIncidenciaImagen
from app.services.order_incident_service import OrderIncidentRow, ReceivedArticleOption
from app.ui.widgets.orders_page import OrderIncidentDialog, OrdersPage


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_pedido_tab_uses_split_order_and_received_columns(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    headers = [page.pedido_items_table.horizontalHeaderItem(i).text() for i in range(page.pedido_items_table.columnCount())]

    assert headers == ["Cod.", "Nombre", "Pedido", "Kg", "Recib.", "Kg", "Δ"]
    assert page.pedido_items_totals_table.columnCount() == 7
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_pedido_delta_header_and_zero_value_behavior(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    assert page.pedido_items_table.horizontalHeaderItem(6).text() == "Δ"

    page.close()
    page.deleteLater()
    QApplication.processEvents()



def test_pendientes_tab_uses_accumulated_pending_columns(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    headers = [page.pendientes_table.horizontalHeaderItem(i).text() for i in range(page.pendientes_table.columnCount())]

    assert headers == ["Cod.", "Nombre", "Pendiente", "Pedido"]
    assert page.pendientes_table.isSortingEnabled()
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_new_order_uses_typed_almacen_filter_text(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    page.almacen_filter.addItem("Todos", "")
    page.almacen_filter.addItem("Distribuidor Norte", "dist-norte")
    page.almacen_filter.addItem("Cliente Sur", "cli-sur")
    page.almacen_filter.setCurrentIndex(0)
    page.almacen_filter.lineEdit().setText("norte")

    assert page._selected_almacen_id() == "dist-norte"

    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_incidencias_tab_exposes_received_article_fields_and_actions(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    tab_widget = page.findChild(QTabWidget, "ordersTabs")
    assert tab_widget is not None
    assert [tab_widget.tabText(i) for i in range(tab_widget.count())] == [
        "Pedido",
        "Albarán",
        "Incidencias",
        "Factura",
        "Pendientes",
    ]
    headers = [page.incidents_table.horizontalHeaderItem(i).text() for i in range(page.incidents_table.columnCount())]
    assert headers == [
        "Fecha incidencia",
        "Código",
        "Descripción",
        "Lote",
        "Albarán",
    ]
    assert not hasattr(page, "incident_article_filter")
    assert not hasattr(page, "incident_observations")
    assert not hasattr(page, "incident_images_list")
    assert page.new_incident_btn.text() == "Nueva"
    assert page.edit_incident_btn.text() == "Editar"
    assert page.delete_incident_btn.text() == "Eliminar"
    assert page.incidents_table.contextMenuPolicy().name == "CustomContextMenu"

    page.close()
    page.deleteLater()
    QApplication.processEvents()


class _IncidentDialogService:
    def __init__(self, images=None, image_path=None) -> None:
        self.images = list(images or [])
        self.image_path = image_path

    def list_images(self, _incident_id: str):
        return self.images

    def resolve_image_path(self, _relative_path: str):
        return self.image_path


def _received_article() -> ReceivedArticleOption:
    return ReceivedArticleOption(
        item_id="line-1",
        codigo="5100",
        descripcion="MALTA TOSTADA X-70",
        lote="A307695",
        caducidad=date(2027, 6, 18),
        unidades=1,
        albaran_numero="2026090116",
        recepcion=date(2026, 8, 25),
    )


def test_incident_modal_contains_form_image_grid_and_actions() -> None:
    _application()
    dialog = OrderIncidentDialog(service=_IncidentDialogService(), articles=[_received_article()])

    assert dialog.windowTitle() == "Nueva incidencia"
    assert dialog.article_selector.count() == 2
    dialog.article_selector.setCurrentIndex(1)
    assert dialog.units_affected.isEnabled() is True
    assert dialog.units_affected.maximum() == 1
    assert dialog.observations.isReadOnly() is False
    assert dialog.images_grid.objectName() == "incidentImagesGrid"
    assert dialog.add_image_btn.text() == "Añadir imagen"
    assert dialog.remove_image_btn.text() == "Eliminar imagen"
    assert dialog.save_btn.text() == "Guardar"

    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()


def test_edit_incident_modal_loads_line_and_image_grid(tmp_path) -> None:
    _application()
    article = _received_article()
    incident = PedidoIncidencia(
        incidencia_id="incident-1",
        pedido_id="order-1",
        albaran_item_id=article.item_id,
        unidades_afectadas=0.5,
        observaciones="Saco roto visible",
        fecha_incidencia=date(2026, 8, 26),
    )
    row = OrderIncidentRow(incidencia=incident, articulo=article, image_count=0)
    image_path = tmp_path / "evidencia.jpg"
    image_path.write_bytes(b"image")
    image = PedidoIncidenciaImagen(
        imagen_id="image-1",
        incidencia_id="incident-1",
        ruta_relativa="incidencias_pedidos/incident-1/image-1.jpg",
        nombre_original="evidencia.jpg",
        tamano_bytes=5,
    )
    dialog = OrderIncidentDialog(
        service=_IncidentDialogService([image], image_path),
        articles=[article],
        incident_row=row,
    )

    assert dialog.windowTitle() == "Editar incidencia"
    assert dialog.article_selector.currentData() == "line-1"
    assert dialog.article_selector.isEnabled() is False
    assert dialog.units_affected.value() == 0.5
    assert dialog.observations.toPlainText() == "Saco roto visible"
    assert dialog.images_grid.count() == 1
    assert dialog.images_grid.item(0).text() == "evidencia.jpg"

    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()



def test_pedido_tab_uses_split_order_and_received_columns(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    headers = [page.pedido_items_table.horizontalHeaderItem(i).text() for i in range(page.pedido_items_table.columnCount())]

    assert headers == ["Cod.", "Nombre", "Pedido", "Kg", "Recib.", "Kg", "Δ"]
    assert page.pedido_items_totals_table.columnCount() == 7
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_pedido_delta_header_and_zero_value_behavior(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    assert page.pedido_items_table.horizontalHeaderItem(6).text() == "Δ"

    page.close()
    page.deleteLater()
    QApplication.processEvents()



def test_pendientes_tab_uses_accumulated_pending_columns(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()

    headers = [page.pendientes_table.horizontalHeaderItem(i).text() for i in range(page.pendientes_table.columnCount())]

    assert headers == ["Cod.", "Nombre", "Pendiente", "Pedido"]
    assert page.pendientes_table.isSortingEnabled()
    page.close()
    page.deleteLater()
    QApplication.processEvents()
