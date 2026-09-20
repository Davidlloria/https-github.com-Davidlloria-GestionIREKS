from datetime import date
import json

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

import app.core.database as database
import app.services.order_incident_service as incident_module
import app.services.order_document_import_service as document_module
import app.services.order_query_service as query_module
import app.services.order_dashboard_service as dashboard_module
import app.services.order_service as order_module
from app.models import (
    Albaran, AlbaranItem, AlmacenMovimiento, AlmacenStock, IngredienteIreks, Pedido, PedidoItem,
    PedidoFaltante, PedidoIncidencia, PedidoPendiente, PedidoRecepcionRevision, PedidoRecepcionReparto,
)
from app.services.order_incident_service import OrderIncidentService
from app.services.order_shortage_service import OrderShortageService
from app.services.order_receipt_assignment_service import receipt_fingerprint, save_receipt_split
from app.services.order_query_service import OrderQueryService
from app.services.order_document_import_service import OrderDocumentImportService
from app.services.order_dashboard_service import OrderDashboardService
from app.services.warehouse_entry_repair_service import WarehouseEntryRepairService


@pytest.fixture
def context(tmp_path, monkeypatch):
    db = create_engine(f"sqlite:///{tmp_path / 'shortages.db'}")
    @event.listens_for(db, "connect")
    def enable_fks(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    SQLModel.metadata.create_all(db)
    for module in (database, incident_module, document_module, query_module, dashboard_module, order_module):
        monkeypatch.setattr(module, "engine", db)
    database._ensure_almacen_stock_sync()
    with Session(db) as session:
        session.add(Pedido(pedido_id="p", pedido_numero="2393", almacen_id="w", pedido_fecha=date(2026, 8, 24)))
        session.add(IngredienteIreks(articulo_id="lemon", articulo_referencia_corta="D1203041",
            articulo_descripcion="PASTA LIMON", articulo_envase_peso_total=1))
        session.commit()
        session.add(PedidoItem(pedido_id="p", articulo_id="lemon", articulo_cantidad=30))
        session.add(Albaran(albaran_id="a", pedido_id="p", almacen_id="w", albaran_numero="2026090117", albaran_fecha=date(2026, 8, 27)))
        for item_id, quantity, lot in (("first", 6, "60486722"), ("second", 24, "60690267")):
            session.add(AlbaranItem(item_id=item_id, pedido_id="p", albaran_id="a", albaran_numero="2026090117",
                articulo_id="lemon", articulo_codigo="D1203041", articulo_cantidad=quantity,
                articulo_lote=lot, albaran_fecha=date(2026, 8, 27)))
            session.add(AlmacenMovimiento(almacen_id="w", articulo_id="lemon", pedido_numero="2393",
                pedido_albaran_numero="2026090117", cantidad=quantity, articulo_lote=lot,
                albaran_item_id=item_id, fecha_pedido=date(2026, 8, 27)))
        session.commit()
    attachments = OrderIncidentService(data_dir=tmp_path / "data")
    service = OrderShortageService(db_engine=db)
    source = tmp_path / "warehouse.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF")
    return db, service, attachments, source


def create(context, received=18, attach=True):
    _, service, attachments, source = context
    key = service.create(pedido_id="p", item_id="second", received=received,
        observations="Almacen: tres cajas de seis en el segundo lote", incident_date=date(2026, 9, 9))
    if attach:
        attachments.add_attachment(key, source)
    return key


def assert_quantities(db, received, pending, stock):
    with Session(db) as session:
        _, stats, _ = OrderQueryService()._build_operational_assignment(session, "p")
        values = stats[("p", "lemon")]
        assert values["ordered"] == 30
        assert values["received"] == received
        assert values["ordered"] - values["received"] - values.get("cancelled", 0) == pending
        assert sum(m.cantidad for m in session.exec(select(AlmacenMovimiento))) == stock
        assert session.exec(select(AlmacenStock)).one().cantidad_total == stock
        assert session.get(AlbaranItem, "second").articulo_cantidad == 24


def test_register_confirm_claim_preserves_document_and_updates_pending_stock(context):
    db, service, attachments, source = context
    key = create(context)
    assert_quantities(db, 30, 0, 30)
    stored = attachments.list_images(key)[0]
    assert attachments.resolve_image_path(stored.ruta_relativa).read_bytes() == source.read_bytes()
    service.confirm(key)
    assert_quantities(db, 24, 6, 24)
    with Session(db) as session:
        assert session.exec(select(PedidoPendiente)).one().cantidad_pendiente == 6
        assert session.get(AlbaranItem, "first").cantidad_recibida_confirmada is None
        history = json.loads(session.get(PedidoFaltante, key).historial)
        assert "ajuste de stock -6" in history[-1]["detalle"]
    service.mark_claimed(key, "Reclamado a proveedor el 10/09")
    assert service.list_for_order("p")[key].estado == "reclamada"
    with pytest.raises(ValueError):
        service.confirm(key)
    with pytest.raises(ValueError):
        service.mark_claimed(key, "Duplicada")
    assert_quantities(db, 24, 6, 24)


def test_credit_closes_pending_without_inventing_stock(context):
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    service.resolve(key, "abono", "Abono A-123; canceladas seis unidades")
    assert_quantities(db, 24, 0, 24)
    with Session(db) as session:
        assert not list(session.exec(select(PedidoPendiente)))
    row = OrderDashboardService().load_snapshot(year=2026).recent_orders[0]
    assert row.pending_kg == 0
    assert row.status == "completado"
    with pytest.raises(ValueError, match="resuelta"):
        service.resolve(key, "error_recuento", "Otra solución")


def test_confirmed_shortage_is_only_followed_in_incidents(context):
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    assert OrderQueryService().list_pendientes_acumulados("p")[0] == []
    service.mark_claimed(key, "Reclamación al proveedor")
    assert OrderQueryService().list_pendientes_acumulados("p")[0] == []
    assert service.list_for_order("p")[key].cantidad_documentada == 24
    assert_quantities(db, 24, 6, 24)


@pytest.mark.parametrize("resolution", ["abono", "error_recuento"])
def test_pending_list_preserves_undelivered_units_of_same_article(context, resolution):
    db, service, _, _ = context
    with Session(db) as session:
        order_item = session.exec(select(PedidoItem)).one()
        order_item.articulo_cantidad = 34
        session.add(order_item)
        session.commit()
    key = create(context)
    # The initial count has not changed the documented receipt yet.
    rows, _ = OrderQueryService().list_pendientes_acumulados("p")
    assert rows[0][0].cantidad_pendiente == 4
    service.confirm(key)
    rows, _ = OrderQueryService().list_pendientes_acumulados("p")
    assert len(rows) == 1
    assert rows[0][0].cantidad_pendiente == 4
    assert rows[0][0].cantidad_recibida == 24
    service.resolve(key, resolution, "Justificante")
    rows, _ = OrderQueryService().list_pendientes_acumulados("p")
    assert rows[0][0].cantidad_pendiente == 4


def test_count_error_reverses_once_and_repair_preserves_adjustments(context):
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    service.resolve(key, "error_recuento", "Se encontró la cuarta caja")
    assert_quantities(db, 30, 0, 30)
    result = WarehouseEntryRepairService(db).repair()
    assert result.deleted_duplicate_entries == 0
    assert result.updated_entries == 0
    assert result.after.duplicate_entry_groups == 0
    assert_quantities(db, 30, 0, 30)


def test_pending_error_can_close_without_stock_change(context):
    db, service, _, _ = context
    key = create(context, attach=False)
    service.resolve(key, "error_recuento", "Recuento inicial equivocado")
    assert_quantities(db, 30, 0, 30)


def test_confirmation_requires_evidence_and_matching_stock_and_rolls_back(context):
    db, service, _, _ = context
    key = create(context, attach=False)
    with pytest.raises(ValueError, match="justificante"):
        service.confirm(key)
    context[2].add_attachment(key, context[3])
    with Session(db) as session:
        movement = session.exec(select(AlmacenMovimiento).where(AlmacenMovimiento.albaran_item_id == "second")).one()
        movement.cantidad = 23
        session.add(movement)
        session.commit()
    with pytest.raises(ValueError, match="stock"):
        service.confirm(key)
    with Session(db) as session:
        assert session.get(AlbaranItem, "second").cantidad_recibida_confirmada is None
        assert session.get(PedidoFaltante, key).estado == "pendiente"


def test_confirm_handles_already_reviewed_receipt(context):
    db, service, _, _ = context
    with Session(db) as session:
        item = session.get(AlbaranItem, "second")
        session.add(PedidoRecepcionRevision(albaran_item_id=item.item_id, estado="confirmado", huella=receipt_fingerprint(item)))
        session.add(PedidoRecepcionReparto(albaran_item_id=item.item_id, pedido_id="p", cantidad=24))
        session.commit()
    key = create(context)
    service.confirm(key)
    assert_quantities(db, 24, 6, 24)


@pytest.mark.parametrize("received", [-1, 24, 25, 18.5, float("nan"), float("inf")])
def test_invalid_count_is_rejected(context, received):
    with pytest.raises(ValueError):
        create(context, received=received)


def test_duplicate_and_delete_and_edit_guards(context):
    _, service, attachments, _ = context
    key = create(context)
    with pytest.raises(ValueError, match="ya tiene"):
        create(context)
    with pytest.raises(ValueError, match="historial"):
        attachments.delete_incident(key)
    with pytest.raises(ValueError, match="cantidades"):
        attachments.update_incident(key, unidades_afectadas=5, observaciones="Cambio", fecha_incidencia=date.today())
    service.confirm(key)
    with pytest.raises(ValueError, match="conservan"):
        attachments.delete_image(attachments.list_images(key)[0].imagen_id)
    with pytest.raises(ValueError, match="incidencias"):
        OrderDocumentImportService().delete_albaran_item("second")


def add_replacement(db):
    with Session(db) as session:
        session.add(Albaran(albaran_id="replacement-note", pedido_id="p", almacen_id="w", albaran_numero="REPL", albaran_fecha=date(2026, 9, 12)))
        session.add(AlbaranItem(item_id="replacement", pedido_id="p", albaran_id="replacement-note", albaran_numero="REPL",
            articulo_id="lemon", articulo_codigo="D1203041", articulo_cantidad=6, articulo_lote="new",
            albaran_fecha=date(2026, 9, 12)))
        session.add(AlmacenMovimiento(almacen_id="w", articulo_id="lemon", pedido_numero="2393",
            pedido_albaran_numero="REPL", cantidad=6, articulo_lote="new", albaran_item_id="replacement",
            fecha_pedido=date(2026, 9, 12)))
        session.commit()


def test_replacement_links_existing_receipt_without_double_stock(context):
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    with pytest.raises(ValueError, match="Selecciona"):
        service.resolve(key, "reposicion", "Reposición", "missing")
    add_replacement(db)
    service.resolve(key, "reposicion", "Albarán REPL", "replacement")
    assert_quantities(db, 30, 0, 30)
    with pytest.raises(ValueError, match="vinculada"):
        OrderDocumentImportService().delete_albaran_item("replacement")
    with Session(db) as session, pytest.raises(ValueError, match="vinculadas"):
        item = session.get(AlbaranItem, "replacement")
        save_receipt_split(session, item, {}, 6, fingerprint=receipt_fingerprint(item), version=0)


def test_shared_replacement_resolves_each_orders_shortage(context):
    from app.services.order_receipt_assignment_service import track_receipt, sync_receipt_pending
    db, service, attachments, source = context
    first = create(context)
    service.confirm(first)
    with Session(db) as session:
        session.add(Pedido(pedido_id="q", pedido_numero="Q", almacen_id="w", pedido_fecha=date(2026, 8, 24)))
        session.commit()
        session.add(PedidoItem(pedido_id="q", articulo_id="lemon", articulo_cantidad=6))
        session.add(Albaran(albaran_id="qa", pedido_id="q", almacen_id="w", albaran_numero="QA", albaran_fecha=date(2026, 8, 27)))
        session.add(AlbaranItem(item_id="qi", pedido_id="q", albaran_id="qa", albaran_numero="QA",
            articulo_id="lemon", articulo_cantidad=6, articulo_lote="q", albaran_fecha=date(2026, 8, 27)))
        session.add(AlmacenMovimiento(almacen_id="w", articulo_id="lemon", pedido_numero="Q",
            pedido_albaran_numero="QA", cantidad=6, articulo_lote="q", albaran_item_id="qi", fecha_pedido=date(2026, 8, 27)))
        session.commit()
    second = service.create(pedido_id="q", item_id="qi", received=0,
        observations="Recuento", incident_date=date(2026, 9, 9))
    attachments.add_attachment(second, source)
    service.confirm(second)
    with Session(db) as session:
        session.add(Albaran(albaran_id="ra", pedido_id="p", almacen_id="w", albaran_numero="RA", albaran_fecha=date(2026, 9, 12)))
        item = AlbaranItem(item_id="ri", pedido_id="p", albaran_id="ra", albaran_numero="RA",
            articulo_id="lemon", articulo_cantidad=12.0, albaran_fecha=date(2026, 9, 12))
        session.add(item)
        session.add(AlmacenMovimiento(almacen_id="w", articulo_id="lemon", cantidad=12,
            albaran_item_id="ri", fecha_pedido=date(2026, 9, 12)))
        session.flush()
        track_receipt(session, item)
        save_receipt_split(session, item, {"p": 6, "q": 6}, 0, fingerprint=receipt_fingerprint(item), version=0)
        sync_receipt_pending(session, "p")
        session.commit()
        stock_before = sum(m.cantidad for m in session.exec(select(AlmacenMovimiento)))
    service.resolve(first, "reposicion", "Reposición P", "ri")
    service.resolve(second, "reposicion", "Reposición Q", "ri")
    for pid, key in (("p", first), ("q", second)):
        shortage = service.list_for_order(pid)[key]
        assert shortage.estado == "resuelta" and shortage.reposicion_item_id == "ri"
    with Session(db) as session:
        assert sum(m.cantidad for m in session.exec(select(AlmacenMovimiento))) == stock_before
        assert not list(session.exec(select(PedidoPendiente)))
    with pytest.raises(ValueError, match="resuelta"):
        service.resolve(second, "reposicion", "Duplicada", "ri")


def test_replacement_units_cannot_resolve_two_shortages_in_same_order(context):
    _, service, attachments, source = context
    first = create(context)
    service.confirm(first)
    second = service.create(pedido_id="p", item_id="first", received=0,
        observations="Falta el otro lote", incident_date=date(2026, 9, 9))
    attachments.add_attachment(second, source)
    service.confirm(second)
    add_replacement(context[0])
    service.resolve(first, "reposicion", "Reposición", "replacement")
    with pytest.raises(ValueError, match="suficientes unidades"):
        service.resolve(second, "reposicion", "Mismas unidades", "replacement")
    assert service.list_for_order("p")[second].estado == "confirmado"


def test_credit_rejected_if_replacement_already_received(context):
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    add_replacement(db)
    with pytest.raises(ValueError, match="ya no tiene"):
        service.resolve(key, "abono", "A-2")
    with pytest.raises(ValueError):
        service.resolve(key, "error_recuento", "Error")
    assert_quantities(db, 30, 0, 30)


def test_pending_count_edit_invalidates_stale_confirmation(context):
    db, service, _, _ = context
    key = create(context)
    service.update_count(key, 12, "Se verificaron dos cajas, no tres")
    with pytest.raises(ValueError, match="ha cambiado"):
        service.confirm(key, expected_received=18)
    assert_quantities(db, 30, 0, 30)
    service.confirm(key, expected_received=12)
    assert_quantities(db, 18, 12, 18)
    with pytest.raises(ValueError, match="antes de confirmar"):
        service.update_count(key, 18, "Cambio tardío")


def test_shortage_does_not_reassign_other_orders_split(context):
    db, service, _, _ = context
    with Session(db) as session:
        session.add(Pedido(pedido_id="other", almacen_id="w", pedido_numero="2392", pedido_fecha=date(2026, 8, 23)))
        session.commit()
        session.add(PedidoItem(pedido_id="other", articulo_id="lemon", articulo_cantidad=6))
        session.add(Albaran(albaran_id="other-note", pedido_id="other", almacen_id="w"))
        item = session.get(AlbaranItem, "second")
        session.add(PedidoRecepcionRevision(albaran_item_id=item.item_id, estado="confirmado", huella=receipt_fingerprint(item)))
        session.add(PedidoRecepcionReparto(albaran_item_id=item.item_id, pedido_id="p", cantidad=18))
        session.add(PedidoRecepcionReparto(albaran_item_id=item.item_id, pedido_id="other", cantidad=6))
        session.commit()
    key = create(context)
    service.confirm(key)
    with Session(db) as session:
        splits = {r.pedido_id: r.cantidad for r in session.exec(select(PedidoRecepcionReparto).where(PedidoRecepcionReparto.albaran_item_id == "second"))}
        assert splits == {"p": 12, "other": 6}


def test_unreviewed_assignment_blocks_confirmation(context):
    db, service, _, _ = context
    with Session(db) as session:
        item = session.get(AlbaranItem, "second")
        session.add(PedidoRecepcionRevision(albaran_item_id=item.item_id, huella=receipt_fingerprint(item)))
        session.commit()
    key = create(context)
    with pytest.raises(ValueError, match="asigna"):
        service.confirm(key)
    with Session(db) as session:
        assert session.get(AlbaranItem, "second").cantidad_recibida_confirmada is None


def test_reimport_cannot_overwrite_shortage_and_unchanged_document_is_safe(context):
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    rows = [dict(albaran_numero="2026090117", albaran_fecha="27/08/2026", articulo_codigo="D1203041",
        articulo_cantidad=qty, articulo_lote=lot) for qty, lot in ((6, "60486722"), (24, "60690267"))]
    documents = OrderDocumentImportService()
    with Session(db) as session:
        documents._reimport_albaran(session, "p", "a", rows)
    assert_quantities(db, 24, 6, 24)
    rows[1]["articulo_cantidad"] = 18
    with Session(db) as session, pytest.raises(ValueError, match="faltante"):
        documents._reimport_albaran(session, "p", "a", rows)
    assert_quantities(db, 24, 6, 24)


def test_monthly_received_totals_include_shortage_correction(context):
    from app.services.monthly_orders_service import MonthlyOrdersService
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    with Session(db) as session:
        movements = MonthlyOrdersService()._load_received_entries(session, articulo_id="lemon", almacen_id="w")
        assert sum(m.cantidad for m in movements) == 24


def test_order_quantity_and_date_keep_shortage_history_consistent(context):
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    orders = order_module.OrderService()
    with Session(db) as session:
        line = session.exec(select(PedidoItem)).one()
    for change in (lambda: orders.update_order_line_quantity(line.item_id, 24),
            lambda: orders.delete_order_line(line.item_id),
            lambda: orders.update_order_header("p", date(2026, 9, 30), "2393")):
        with pytest.raises(ValueError, match="conserva"):
            change()
    assert_quantities(db, 24, 6, 24)


def test_open_shortage_is_visible_in_dashboard_even_before_confirmation(context):
    create(context)
    row = OrderDashboardService().load_snapshot(year=2026).recent_orders[0]
    assert row.status == "incidencia"
    assert row.received_kg == 30


def test_failure_after_adjustment_rolls_back_receipt_stock_and_history(context, monkeypatch):
    import app.services.order_shortage_service as shortage_module
    db, service, _, _ = context
    key = create(context)
    def fail(*args):
        raise RuntimeError("Fallo al recalcular pendientes")
    monkeypatch.setattr(shortage_module, "sync_receipt_pending", fail)
    with pytest.raises(RuntimeError):
        service.confirm(key)
    assert_quantities(db, 30, 0, 30)
    with Session(db) as session:
        assert session.get(PedidoFaltante, key).estado == "pendiente"
        assert len(json.loads(session.get(PedidoFaltante, key).historial)) == 1
        assert not list(session.exec(select(PedidoRecepcionRevision)))


def test_full_line_shortage_can_confirm_zero_received(context):
    db, service, _, _ = context
    key = create(context, received=0)
    service.confirm(key)
    assert_quantities(db, 6, 24, 6)


def test_orders_ui_shows_original_lots_actual_receipts_and_open_shortage(context, monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QTabWidget
    from app.ui.widgets.orders_page import OrdersPage
    db, service, _, _ = context
    key = create(context)
    service.confirm(key)
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(OrdersPage, "reload", lambda self: None)
    page = OrdersPage()
    page.order_shortage_service = service
    page._reload_albaran_items_table("p", "a")
    page._reload_incidents("p", key)
    index = next(r for r in range(page.albaran_items_table.rowCount())
        if page.albaran_items_table.item(r, 0).data(Qt.ItemDataRole.UserRole) == "second")
    assert page.albaran_items_table.item(index, 3).text() == "24,00"
    assert page.albaran_items_table.item(index, 5).text() == "60690267"
    assert page.albaran_items_table.item(index, 6).text() == "18,00"
    assert page.edit_incident_btn.text() == "Seguimiento"
    assert not page.delete_incident_btn.isEnabled()
    assert page.findChild(QTabWidget, "ordersTabs").tabText(2) == "Incidencias (1)"
    page.close()
    page.deleteLater()
    app.processEvents()
