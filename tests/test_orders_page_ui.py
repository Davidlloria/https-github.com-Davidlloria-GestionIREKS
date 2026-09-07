from __future__ import annotations

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidgetItem, QTabWidget

from app.models import PedidoIncidencia, PedidoIncidenciaImagen
from app.services.order_incident_service import OrderIncidentRow, ReceivedArticleOption
from app.services.order_query_service import ArticleOrderHistoryRow
from app.ui.widgets import orders_page as orders_page_module
from app.ui.widgets.orders_page import NewPedidoDialog, OrderIncidentDialog, OrdersPage, PedidoListRow


_APP: QApplication | None = None


def _application() -> QApplication:
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


class _ArticleHistoryQueryService:
    def __init__(self, rows: list[ArticleOrderHistoryRow]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []

    def list_article_order_history(
        self,
        almacen_id: str,
        articulo_id: str,
        **kwargs,
    ) -> list[ArticleOrderHistoryRow]:
        self.calls.append({"almacen_id": almacen_id, "articulo_id": articulo_id, **kwargs})
        return self.rows


def _history_submenu(menu):
    return next(action.menu() for action in menu.actions() if action.text() == "Últimos pedidos del artículo")


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


def test_pedido_quantity_edit_defers_reload_until_editor_commit_finishes(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()
    saved: list[tuple[str, float]] = []
    scheduled: list[tuple[int, object]] = []
    monkeypatch.setattr(
        page.order_service,
        "update_order_line_quantity",
        lambda item_id, quantity: saved.append((item_id, quantity)),
    )
    monkeypatch.setattr(
        orders_page_module.QTimer,
        "singleShot",
        lambda delay, callback: scheduled.append((delay, callback)),
    )
    page._loading_pedido_items_table = True
    page.pedido_items_table.setRowCount(1)
    id_item = QTableWidgetItem("5100")
    id_item.setData(Qt.ItemDataRole.UserRole, "line-1")
    quantity_item = QTableWidgetItem("3,5")
    page.pedido_items_table.setItem(0, 0, id_item)
    page.pedido_items_table.setItem(0, 2, quantity_item)
    page._loading_pedido_items_table = False

    page._on_pedido_item_cell_changed(quantity_item)

    assert saved == [("line-1", 3.5)]
    assert len(scheduled) == 1
    assert scheduled[0][0] == 0
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_new_and_edit_order_table_context_menu_shows_article_history(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(NewPedidoDialog, "_load_rows", lambda self: None)
    dialog = NewPedidoDialog(
        "alm-1",
        title="Editar pedido",
        history_reference_date=date(2026, 6, 10),
        history_exclude_pedido_id="pedido-actual",
    )
    history_service = _ArticleHistoryQueryService(
        [
            ArticleOrderHistoryRow("pedido-2", date(2026, 6, 9), "A-002", 4.0),
            ArticleOrderHistoryRow("pedido-1", date(2026, 6, 1), "", 2.5),
        ]
    )
    dialog.order_query_service = history_service
    dialog.table.setRowCount(1)
    ref_item = QTableWidgetItem("R1")
    ref_item.setData(Qt.ItemDataRole.UserRole, "art-1")
    dialog.table.setItem(0, 0, ref_item)
    captured: dict[str, object] = {}

    def capture_menu(menu, _pos):
        history_menu = _history_submenu(menu)
        captured["texts"] = [action.text() for action in history_menu.actions()]
        captured["enabled"] = [action.isEnabled() for action in history_menu.actions()]

    monkeypatch.setattr(
        orders_page_module,
        "_exec_context_menu",
        capture_menu,
    )

    dialog._show_article_history_context_menu(dialog.table.visualItemRect(ref_item).center())

    assert dialog.table.selectionModel().selectedRows()[0].row() == 0
    assert history_service.calls == [
        {
            "almacen_id": "alm-1",
            "articulo_id": "art-1",
            "reference_date": date(2026, 6, 10),
            "exclude_pedido_id": "pedido-actual",
            "limit": 5,
        }
    ]
    assert captured["texts"] == [
        "09/06/2026 · Pedido A-002 · 4,00 uds.",
        "01/06/2026 · Pedido Sin número · 2,50 uds.",
    ]
    assert captured["enabled"] == [False, False]
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()


def test_pedido_tab_context_menu_shows_empty_article_history(monkeypatch) -> None:
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()
    selected_order = PedidoListRow(
        pedido_id="pedido-actual",
        almacen_id="alm-1",
        almacen_nombre="Almacén",
        pedido_fecha=date(2026, 6, 10),
        pedido_numero="A-003",
        pedido_albaran_numero="",
        pedido_factura_numero="",
        pedido_ref="",
        pedido_estado="P",
        semana=24,
        total_kg=12.5,
    )
    monkeypatch.setattr(page, "_selected_row", lambda: selected_order)
    history_service = _ArticleHistoryQueryService([])
    page.order_query_service = history_service
    page.pedido_items_table.setRowCount(1)
    id_item = QTableWidgetItem("R1")
    id_item.setData(Qt.ItemDataRole.UserRole, "line-1")
    id_item.setData(orders_page_module.ARTICLE_ID_ROLE, "art-1")
    page.pedido_items_table.setItem(0, 0, id_item)
    captured: dict[str, object] = {}

    def capture_menu(menu, _pos):
        history_menu = _history_submenu(menu)
        captured["texts"] = [action.text() for action in history_menu.actions()]
        captured["enabled"] = [action.isEnabled() for action in history_menu.actions()]

    monkeypatch.setattr(
        orders_page_module,
        "_exec_context_menu",
        capture_menu,
    )

    page._show_pedido_items_context_menu(page.pedido_items_table.visualItemRect(id_item).center())

    assert page.pedido_items_table.selectionModel().selectedRows()[0].row() == 0
    assert history_service.calls == [
        {
            "almacen_id": "alm-1",
            "articulo_id": "art-1",
            "reference_date": date(2026, 6, 10),
            "exclude_pedido_id": "pedido-actual",
            "limit": 5,
        }
    ]
    assert captured["texts"] == ["Sin pedidos anteriores"]
    assert captured["enabled"] == [False]
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
        unidades_afectadas=1,
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
    assert dialog.units_affected.value() == 1
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


def test_excel_export_reports_primary_history_and_status_failures(monkeypatch) -> None:
    from types import SimpleNamespace

    for failing_stage in ("excel", "history", "status", "none"):
        calls = []
        warnings = []
        information = []

        def step(name, result=None):
            calls.append(name)
            if failing_stage == name:
                raise OSError("Destino no disponible")
            return result

        workbook = SimpleNamespace(save=lambda path: step("excel"))
        service = SimpleNamespace(
            build_order_workbook=lambda order_id: (workbook, "pedido"),
            save_order_excel_history=lambda *args: step("history", "historico/pedido.xlsx"),
            mark_order_exported=lambda order_id: step("status"),
        )
        page = SimpleNamespace(
            order_export_service=service,
            reload=lambda: step("reload"),
            _select_by_id=lambda order_id: step("select"),
        )
        monkeypatch.setattr(orders_page_module.QFileDialog, "getSaveFileName", lambda *args: ("pedido.xlsx", ""))
        monkeypatch.setattr(orders_page_module.QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
        monkeypatch.setattr(orders_page_module.QMessageBox, "information", lambda *args: information.append(args[-1]))
        OrdersPage._export_order_to_excel(page, "order-1")
        if failing_stage == "excel":
            assert calls == ["excel"]
            assert "No se pudo guardar el Excel" in warnings[0]
        elif failing_stage == "history":
            assert calls == ["excel", "history"]
            assert "El Excel se ha guardado" in warnings[0]
            assert "no se ha marcado como exportado" in warnings[0]
        elif failing_stage == "status":
            assert calls == ["excel", "history", "status"]
            assert "historico/pedido.xlsx" in warnings[0]
            assert "No se pudo actualizar el estado" in warnings[0]
        else:
            assert calls == ["excel", "history", "status", "reload", "select"]
            assert not warnings
            assert information


def test_history_selector_refreshes_sum_without_changing_entered_units(monkeypatch) -> None:
    from app.models import IngredienteIreks
    _application()
    calls = []
    article = IngredienteIreks(articulo_id="art-1", articulo_descripcion="Harina")

    def catalogs(self, almacen_id, preload_history, **kwargs):
        calls.append(kwargs)
        return [article], [], [], [], {"art-1": kwargs["history_limit"] * 3.0}, {}

    monkeypatch.setattr(orders_page_module.OrderQueryService, "order_dialog_catalogs", catalogs)
    for excluded_id in ("", "current"):
        dialog = NewPedidoDialog(
            "alm-1", initial_qty_by_articulo={"art-1": 7},
            history_exclude_pedido_id=excluded_id,
        )
        assert dialog.table.item(0, 5).text() == "3.00"
        dialog.history_limit_spin.setValue(2)
        assert dialog.table.item(0, 5).text() == "6.00"
        assert dialog.table.item(0, 3).text() == "7.00"
        assert calls[-1]["exclude_pedido_id"] == excluded_id
        dialog.fecha_edit.setDate(dialog.fecha_edit.date().addDays(-1))
        assert calls[-1]["history_limit"] == 2
        assert calls[-1]["reference_date"] == dialog.fecha_edit.date().toPython()
        dialog.close()
        dialog.deleteLater()
    QApplication.processEvents()
