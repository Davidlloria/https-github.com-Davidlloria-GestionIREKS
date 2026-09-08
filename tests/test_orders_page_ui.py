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


def test_factura_items_load_with_and_without_price_discrepancy(monkeypatch) -> None:
    from types import SimpleNamespace

    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()
    rows = [
        (SimpleNamespace(item_id=item_id, articulo_codigo=item_id,
                         articulo_cantidad=2, articulo_kilos=10,
                         precio_unitario=5, total_linea=50), None)
        for item_id in ("different", "equal", "unknown")
    ]
    monkeypatch.setattr(
        page.order_document_import_service, "list_factura_items",
        lambda pedido_id, factura_id: (rows, {"different": True, "equal": False}),
    )
    try:
        page._reload_factura_items_table("order", "invoice")
        assert page.factura_items_table.rowCount() == 3
        for row in range(3):
            item_id = page.factura_items_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            price = page.factura_items_table.item(row, 4)
            assert price.text() == "5,00"
            assert (price.foreground().color().name() == "#c62828") == (item_id == "different")
    finally:
        page.close()
        page.deleteLater()
        QApplication.processEvents()


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


def test_warehouse_filter_defaults_to_igsa_and_preserves_selection(monkeypatch) -> None:
    from app.services.order_query_service import WarehouseFilterOption
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()
    options = [WarehouseFilterOption("Todos", ""), WarehouseFilterOption("Otro", "other"),
               WarehouseFilterOption("IGSA", "igsa")]
    monkeypatch.setattr(page.order_query_service, "warehouse_filter_options", lambda: options)
    page._load_almacen_filter()
    assert page.almacen_filter.currentData() == "igsa"
    for selected in ("other", "", "igsa"):
        page.almacen_filter.setCurrentIndex(page.almacen_filter.findData(selected))
        page._load_almacen_filter()
        assert page.almacen_filter.currentData() == selected
    page.almacen_filter.clear()
    options.pop()
    page._load_almacen_filter()
    assert page.almacen_filter.currentData() == ""
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_receipt_dialog_defers_without_writes_and_confirms_explicit_split():
    from app.services.order_receipt_assignment_service import ReceiptCandidate, ReceiptReview
    from app.ui.widgets.receipt_assignment_dialog import ReceiptAssignmentDialog
    _application()

    class Service:
        def __init__(self):
            self.saved = []
        def list_reviews(self, *args, **kwargs):
            if self.saved:
                return []
            return [ReceiptReview("receipt", "2026090119", "PASTA BAYA DE SAUCO", 6, True, "hash", 0,
                [ReceiptCandidate("old", "1482", date(2026, 5, 25), 1),
                 ReceiptCandidate("target", "2393", date(2026, 8, 24), 6)], {}, 0, [])]
        def confirm(self, review, allocations, excess):
            self.saved.append((review.item_id, allocations, excess))

    service = Service()
    dialog = ReceiptAssignmentDialog(service)
    assert not dialog.confirm.isEnabled()
    assert dialog.table.cellWidget(0, 3).value() == 0
    assert dialog.table.cellWidget(1, 3).value() == 0
    dialog.later.click()
    assert not service.saved
    dialog.deleteLater()
    dialog = ReceiptAssignmentDialog(service)
    dialog.table.cellWidget(1, 3).setValue(6)
    assert dialog.confirm.isEnabled()
    dialog.confirm.click()
    assert service.saved == [("receipt", {"old": 0, "target": 6}, 0)]
    assert dialog.selector.count() == 0
    dialog.close()
    dialog.deleteLater()
    QApplication.processEvents()



def test_albaran_import_opens_pending_receipt_confirmation(monkeypatch):
    from types import SimpleNamespace
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()
    monkeypatch.setattr(page, "_selected_row", lambda: SimpleNamespace(pedido_id="source"))
    monkeypatch.setattr(orders_page_module.QFileDialog, "getOpenFileName", lambda *args: ("delivery.csv", ""))
    monkeypatch.setattr(page.orders_documents_import_ui_service, "run_import_document_flow", lambda *args, **kwargs:
                        SimpleNamespace(ok=True, title="Albaran", message="Imported"))
    monkeypatch.setattr(page.receipt_assignment_service, "pending_count", lambda **kwargs: 1)
    opened = []
    monkeypatch.setattr(page, "_review_receipts", lambda pedido_id: opened.append(pedido_id))
    monkeypatch.setattr(orders_page_module.QMessageBox, "information", lambda *args: None)
    page._import_document_for_selected_order(dialog_title="Import", warning_prefix="albaran",
        preview_loader=lambda *args: None, importer=lambda *args: None, confirm_preview=lambda *args: True)
    assert opened == ["source"]
    page.close()
    page.deleteLater()
    QApplication.processEvents()



def _orders_context_page(monkeypatch):
    _application()
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    monkeypatch.setattr(OrdersPage, "_show_selected_details", lambda self: None)
    page = OrdersPage()
    page.rows = [PedidoListRow(pid, "igsa", "IGSA", date(2026, 9, 7), number, "", "", "", state, 37, 100)
                 for pid, number, state in [("pending", "2447", "E"), ("clear", "2393", "P")]]
    page._receipt_counts = {"pending": 3, "clear": 0}
    page._render_table()
    page.table.sortItems(1, Qt.SortOrder.AscendingOrder)
    return page


def test_order_status_marks_receipts_and_refreshes_after_resolution(monkeypatch):
    reload_page = OrdersPage.reload
    page = _orders_context_page(monkeypatch)
    assert not hasattr(page, "receipts_btn")
    assert page.table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    page._select_by_id("pending")
    row = page.table.currentRow()
    assert page.table.item(row, 5).text() == "A (3)"
    assert "Clic derecho" in page.table.item(row, 5).toolTip()
    page._select_by_id("clear")
    assert page.table.item(page.table.currentRow(), 5).text() == ""
    assert [r.pedido_estado for r in page.rows] == ["E", "P"]
    monkeypatch.setattr(page.order_query_service, "list_raw_orders", lambda: [])
    monkeypatch.setattr(page.order_query_service, "list_order_rows", lambda **kwargs: page.rows[:])
    monkeypatch.setattr(page, "_load_almacen_filter", lambda: None)
    monkeypatch.setattr(page, "_load_period_filters", lambda rows: None)
    monkeypatch.setattr(page.receipt_assignment_service, "pending_count", lambda **kwargs: 0)
    reload_page(page)
    assert all(page.table.item(row, 5).text() == "" for row in range(page.table.rowCount()))
    page.close()
    page.deleteLater()
    QApplication.processEvents()


def test_order_context_menu_mirrors_ribbon_and_uses_clicked_sorted_row(monkeypatch):
    page = _orders_context_page(monkeypatch)
    buttons = (page.new_btn, page.edit_btn, page.del_btn, page.export_btn,
               page.send_mail_btn, page.print_btn, page.help_btn)
    clicked = []
    for button in buttons:
        button.clicked.disconnect()
        button.clicked.connect(lambda checked=False, name=button.text(): clicked.append((name, page._selected_id())))
    page.export_btn.setEnabled(False)
    monkeypatch.setattr(page.receipt_assignment_service, "pending_count", lambda *, pedido_id: 3 if pedido_id == "pending" else 0)
    opened = []
    monkeypatch.setattr(page, "_review_receipts", lambda pid: opened.append(pid))
    page._select_by_id("pending")
    pending_cell = page.table.item(page.table.currentRow(), 0)
    pending_pos = page.table.visualItemRect(pending_cell).center()
    labels = [b.text() for b in buttons] + ["Asignar recepciones"]
    for chosen_label in labels:
        page._select_by_id("clear")
        def capture(menu, pos):
            actions = [a for a in menu.actions() if not a.isSeparator()]
            assert [a.text() for a in actions] == labels
            assert [a.isEnabled() for a in actions[:-1]] == [b.isEnabled() for b in buttons]
            assert actions[-1].isEnabled()
            assert page._selected_id() == "pending"
            return next(a for a in actions if a.text() == chosen_label)
        monkeypatch.setattr(orders_page_module, "_exec_context_menu", capture)
        page._show_orders_context_menu(pending_pos)
    assert clicked == [(b.text(), "pending") for b in buttons if b.isEnabled()]
    assert opened == ["pending"]
    page._select_by_id("clear")
    clear_pos = page.table.visualItemRect(page.table.item(page.table.currentRow(), 0)).center()
    page._select_by_id("pending")
    def disabled(menu, pos):
        action = menu.actions()[-1]
        assert action.text() == "Asignar recepciones" and not action.isEnabled()
        assert page._selected_id() == "clear"
        return action
    monkeypatch.setattr(orders_page_module, "_exec_context_menu", disabled)
    page._show_orders_context_menu(clear_pos)
    assert opened == ["pending"]
    from PySide6.QtCore import QPoint
    monkeypatch.setattr(orders_page_module, "_exec_context_menu", lambda *args: (_ for _ in ()).throw(AssertionError("Empty area")))
    page._show_orders_context_menu(QPoint(-1, -1))
    page.close()
    page.deleteLater()
    QApplication.processEvents()



def test_receipt_integer_editors_fit_styled_rows_and_arrow_clicks_work():
    from pathlib import Path
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QSpinBox, QStyle, QStyleOptionSpinBox
    from app.services.order_receipt_assignment_service import ReceiptCandidate, ReceiptReview
    from app.ui.widgets.receipt_assignment_dialog import ReceiptAssignmentDialog
    app = _application()
    previous_style = app.styleSheet()
    dialog = None

    class Service:
        def list_reviews(self, *args, **kwargs):
            return [ReceiptReview("r", "2026090119", "FRUTAS DEL BOSQUE", 2, True, "hash", 0,
                [ReceiptCandidate("a", "2057", date(2026, 7, 20), 1),
                 ReceiptCandidate("b", "2199", date(2026, 8, 3), 4)], {}, 0, [])]

    try:
        app.setStyleSheet((Path(__file__).resolve().parents[1] / "assets/styles.qss").read_text(encoding="utf-8"))
        dialog = ReceiptAssignmentDialog(Service())
        dialog.show()
        QApplication.processEvents()
        for row in range(2):
            editor = dialog.table.cellWidget(row, 3)
            assert isinstance(editor, QSpinBox)
            assert editor.text() == "0" and editor.singleStep() == 1
            cell = dialog.table.visualRect(dialog.table.model().index(row, 3))
            assert cell.contains(editor.geometry())
            option = QStyleOptionSpinBox()
            editor.initStyleOption(option)
            up = editor.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option, QStyle.SubControl.SC_SpinBoxUp, editor)
            down = editor.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option, QStyle.SubControl.SC_SpinBoxDown, editor)
            assert not up.intersects(down)
            QTest.mouseClick(editor, Qt.MouseButton.LeftButton, pos=up.center())
            assert editor.value() == 1
            QTest.mouseClick(editor, Qt.MouseButton.LeftButton, pos=down.center())
            assert editor.value() == 0
            for _ in range(3):
                QTest.mouseClick(editor, Qt.MouseButton.LeftButton, pos=up.center())
            assert editor.value() == (1 if row == 0 else 2)
            editor.setValue(0)
        assert isinstance(dialog.excess, QSpinBox) and dialog.excess.maximum() == 2
        dialog.table.cellWidget(0, 3).setValue(1)
        dialog.excess.setValue(1)
        assert dialog.confirm.isEnabled()
        assert dialog._allocations() == {"a": 1, "b": 0}
    finally:
        if dialog:
            dialog.close()
            dialog.deleteLater()
        app.setStyleSheet(previous_style)
        QApplication.processEvents()
