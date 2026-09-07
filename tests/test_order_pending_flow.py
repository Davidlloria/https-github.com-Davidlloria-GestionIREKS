from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

import app.services.order_document_import_service as order_document_import_service_module
import app.services.order_query_service as order_query_service_module
from app.models import Albaran, AlbaranItem, Fabricante, Familia, IngredienteIreks, Pedido, PedidoItem, PedidoPendiente, Subfamilia
from app.services.order_document_import_service import OrderDocumentImportService
from app.services.order_query_service import OrderQueryService


@pytest.fixture()
def isolated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'pending.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(order_document_import_service_module, "engine", engine)
    monkeypatch.setattr(order_query_service_module, "engine", engine)
    return engine


def _seed_catalog(session: Session) -> str:
    fabricante_id = "fab-1"
    familia_id = "fam-1"
    subfamilia_id = "sub-1"
    articulo_id = "art-1"

    session.add(Fabricante(fabricante_id=fabricante_id, fabricante_codigo=1, fabricante_nombre="Fabricante"))
    session.add(
        Familia(
            articulo_familia_id=familia_id,
            fabricante_id=fabricante_id,
            articulo_familia_nombre="Familia",
            articulo_familia_codigo="FAM",
        )
    )
    session.add(
        Subfamilia(
            articulo_familia_id=familia_id,
            articulo_subfamilia_id=subfamilia_id,
            articulo_subfamilia_nombre="Subfamilia",
            articulo_subfamilia_codigo="SUB",
        )
    )
    session.add(
        IngredienteIreks(
            almacen_id="alm-1",
            fabricante_id=fabricante_id,
            articulo_id=articulo_id,
            articulo_referencia="REF-1",
            articulo_referencia_corta="R1",
            articulo_descripcion="Articulo 1",
            articulo_envase_peso_total=10.0,
            articulo_familia_id=familia_id,
            articulo_subfamilia_id=subfamilia_id,
            articulo_status_en_lista=True,
        )
    )
    session.commit()
    return articulo_id


def _seed_order(session: Session, pedido_id: str, pedido_fecha: date, pedido_numero: str, articulo_id: str, cantidad: float) -> None:
    session.add(
        Pedido(
            pedido_id=pedido_id,
            almacen_id="alm-1",
            pedido_fecha=pedido_fecha,
            pedido_numero=pedido_numero,
        )
    )
    session.add(
        PedidoItem(
            pedido_id=pedido_id,
            pedido_numero=pedido_numero,
            pedido_item_fecha=pedido_fecha,
            articulo_id=articulo_id,
            articulo_cantidad=cantidad,
        )
    )


def _seed_albaran(
    session: Session,
    *,
    pedido_id: str,
    albaran_id: str,
    albaran_numero: str,
    albaran_fecha: date,
    articulo_id: str,
    articulo_codigo: str,
    cantidad: float,
) -> None:
    session.add(
        Albaran(
            albaran_id=albaran_id,
            almacen_id="alm-1",
            pedido_id=pedido_id,
            albaran_numero=albaran_numero,
            albaran_fecha=albaran_fecha,
        )
    )
    session.add(
        AlbaranItem(
            item_id=f"item-{albaran_id}",
            pedido_id=pedido_id,
            albaran_id=albaran_id,
            albaran_numero=albaran_numero,
            albaran_fecha=albaran_fecha,
            articulo_codigo=articulo_codigo,
            articulo_id=articulo_id,
            articulo_cantidad=cantidad,
        )
    )


def test_pending_rows_are_not_created_until_an_albaran_exists(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        _seed_order(session, "pedido-1", date(2026, 6, 1), "P-1", articulo_id, 10.0)
        _seed_order(session, "pedido-2", date(2026, 6, 2), "P-2", articulo_id, 5.0)
        session.commit()

        OrderDocumentImportService().rebuild_order_pendientes(session, "pedido-2", "albaran-missing")

    with Session(isolated_engine) as session:
        rows = list(session.exec(select(PedidoPendiente)))
        assert rows == []


def test_pending_rows_carry_forward_to_next_order_but_not_current_one(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        _seed_order(session, "pedido-1", date(2026, 6, 1), "P-1", articulo_id, 10.0)
        _seed_order(session, "pedido-2", date(2026, 6, 2), "P-2", articulo_id, 5.0)
        _seed_albaran(
            session,
            pedido_id="pedido-1",
            albaran_id="alb-1",
            albaran_numero="A-1",
            albaran_fecha=date(2026, 6, 2),
            articulo_id=articulo_id,
            articulo_codigo="REF-1",
            cantidad=7.0,
        )
        session.commit()

        OrderDocumentImportService().rebuild_order_pendientes(session, "pedido-1", "alb-1")

    with Session(isolated_engine) as session:
        stored_rows = list(session.exec(select(PedidoPendiente).order_by(PedidoPendiente.pedido_id, PedidoPendiente.estado)))
        assert len(stored_rows) == 1
        assert stored_rows[0].pedido_id == "pedido-1"
        assert stored_rows[0].cantidad_pendiente == 3.0
        assert stored_rows[0].estado == "pendiente"

    service = OrderQueryService()
    _rows, _fabricantes, _familias, _subfamilias, _prev_qty, pending_qty_by_articulo = service.order_dialog_catalogs(
        "alm-1",
        True,
        reference_date=date(2026, 6, 2),
        exclude_pedido_id="pedido-2",
    )

    assert pending_qty_by_articulo == {articulo_id: 3.0}


def test_pending_rows_ignore_same_day_orders_in_dialog(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        _seed_order(session, "pedido-1", date(2026, 6, 1), "P-1", articulo_id, 10.0)
        _seed_albaran(
            session,
            pedido_id="pedido-1",
            albaran_id="alb-1",
            albaran_numero="A-1",
            albaran_fecha=date(2026, 6, 2),
            articulo_id=articulo_id,
            articulo_codigo="REF-1",
            cantidad=7.0,
        )
        session.commit()

        OrderDocumentImportService().rebuild_order_pendientes(session, "pedido-1", "alb-1")

    service = OrderQueryService()
    _rows, _fabricantes, _familias, _subfamilias, _prev_qty, pending_qty_by_articulo = service.order_dialog_catalogs(
        "alm-1",
        True,
        reference_date=date(2026, 6, 1),
        exclude_pedido_id="pedido-x",
    )

    assert pending_qty_by_articulo == {}



def test_list_pendientes_acumulados_uses_selected_order_almacen_context(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        _seed_order(session, "pedido-1", date(2026, 6, 1), "P-1", articulo_id, 10.0)
        _seed_order(session, "pedido-2", date(2026, 6, 2), "P-2", articulo_id, 5.0)
        _seed_albaran(
            session,
            pedido_id="pedido-2",
            albaran_id="alb-2",
            albaran_numero="A-2",
            albaran_fecha=date(2026, 6, 3),
            articulo_id=articulo_id,
            articulo_codigo="REF-1",
            cantidad=7.0,
        )
        session.add(Albaran(
            albaran_id="alb-1", pedido_id="pedido-1", almacen_id="alm-1",
            albaran_numero="A-1", albaran_fecha=date(2026, 6, 1),
        ))
        session.commit()

        OrderDocumentImportService().rebuild_order_pendientes(session, "pedido-2", "alb-2")

    service = OrderQueryService()
    rows, articles = service.list_pendientes_acumulados("pedido-2")

    assert len(rows) == 1
    resumen = [(pedido.pedido_numero, pendiente.cantidad_pendiente) for pendiente, pedido in rows]
    assert resumen == [("P-1", 8.0)]
    assert len(articles) == 1
    assert articles[0].articulo_id == articulo_id


@pytest.mark.parametrize("received", [None, 0.0, 4.0, 10.0])
def test_pending_tab_only_includes_orders_with_imported_delivery(isolated_engine, received) -> None:
    with Session(isolated_engine) as session:
        article_id = _seed_catalog(session)
        _seed_order(session, "delivered", date(2026, 6, 1), "P-1", article_id, 10.0)
        _seed_order(session, "new", date(2026, 6, 2), "P-2", article_id, 5.0)
        if received is not None:
            _seed_albaran(
                session, pedido_id="delivered", albaran_id="alb-1",
                albaran_numero="A-1", albaran_fecha=date(2026, 6, 1),
                articulo_id=article_id, articulo_codigo="REF-1", cantidad=received,
            )
        session.commit()

    for selected_id in ("new", "delivered"):
        rows, articles = OrderQueryService().list_pendientes_acumulados(selected_id)
        expected = [] if received is None or received == 10 else [("delivered", 10 - received)]
        assert [(row.pedido_id, row.cantidad_pendiente) for row, _ in rows] == expected
        assert [article.articulo_id for article in articles] == ([article_id] if expected else [])


def test_explicit_receipt_closes_target_without_consuming_older_pending(isolated_engine) -> None:
    from app.models import PedidoRecepcionAsignacion
    from app.services.order_receipt_assignment_service import assign_order_receipt

    with Session(isolated_engine) as session:
        article_id = _seed_catalog(session)
        _seed_order(session, "old", date(2026, 5, 25), "1482", article_id, 1)
        _seed_order(session, "target", date(2026, 8, 24), "2393", article_id, 6)
        _seed_order(session, "source", date(2026, 8, 31), "2447", article_id, 0)
        for order_id in ("old", "target"):
            session.add(Albaran(albaran_id=order_id, pedido_id=order_id, almacen_id="alm-1"))
        _seed_albaran(session, pedido_id="source", albaran_id="delivery", albaran_numero="2026090119",
                      albaran_fecha=date(2026, 9, 1), articulo_id=article_id, articulo_codigo="REF-1", cantidad=6)
        session.commit()
        assert OrderQueryService().list_order_items("target")[2] == {}
        assign_order_receipt(session, "item-delivery", "target")
        assign_order_receipt(session, "item-delivery", "target")  # Idempotent.
        session.commit()

    service = OrderQueryService()
    assert service.list_order_items("target")[1:] == (set(), {article_id: 6.0})
    assert service.list_order_items("source")[2] == {}
    rows, _ = service.list_pendientes_acumulados("target")
    assert [(row.pedido_id, row.cantidad_pendiente) for row, _ in rows] == [("old", 1.0)]
    with Session(isolated_engine) as session:
        item = session.get(AlbaranItem, "item-delivery")
        assert (item.pedido_id, item.albaran_numero, item.articulo_cantidad) == ("source", "2026090119", 6)
        assert len(list(session.exec(select(PedidoRecepcionAsignacion)))) == 1
        for target_id in ("missing", "old"):
            with pytest.raises(ValueError):
                assign_order_receipt(session, "item-delivery", target_id)
        target = session.get(Pedido, "target")
        target.almacen_id = "other"
        session.flush()
        with pytest.raises(ValueError, match="same warehouse"):
            assign_order_receipt(session, "item-delivery", "target")
        session.rollback()


@pytest.fixture()
def receipt_engine(isolated_engine, monkeypatch):
    import app.services.order_receipt_assignment_service as module
    monkeypatch.setattr(module, "engine", isolated_engine)
    return isolated_engine


def _receipt_scenario(engine, quantities=(6, 1)):
    from app.services.order_receipt_assignment_service import track_receipt
    with Session(engine) as session:
        article_id = _seed_catalog(session)
        for index, quantity in enumerate(quantities):
            _seed_order(session, f"p{index}", date(2026, 8, index + 1), f"P{index}", article_id, quantity)
            session.add(Albaran(albaran_id=f"header{index}", pedido_id=f"p{index}", almacen_id="alm-1"))
        _seed_albaran(session, pedido_id="p0", albaran_id="new-delivery", albaran_numero="NEW",
                      albaran_fecha=date(2026, 9, 1), articulo_id=article_id, articulo_codigo="REF-1", cantidad=6)
        session.flush()
        track_receipt(session, session.get(AlbaranItem, "item-new-delivery"))
        session.commit()
    return article_id


def test_ambiguous_receipt_is_deferred_then_split_and_can_be_corrected(receipt_engine):
    from app.services.order_receipt_assignment_service import ReceiptAssignmentService, automate_receipts
    article = _receipt_scenario(receipt_engine)
    service = ReceiptAssignmentService()
    with Session(receipt_engine) as session:
        automate_receipts(session, "p0")
        session.commit()
    assert service.pending_count("alm-1") == 1
    assert service.pending_count("other") == 0
    assert OrderQueryService().list_order_items("p0")[2] == {}
    review = service.list_reviews()[0]
    assert review.allocations == {} and len(review.candidates) == 2
    with pytest.raises(ValueError):
        service.confirm(review, {"p0": 6, "p1": 1}, 0)
    with pytest.raises(ValueError):
        service.confirm(review, {"p1": 6}, 0)
    with pytest.raises(ValueError):
        service.confirm(review, {"p0": float("nan")}, 0)
    service.confirm(review, {"p0": 5, "p1": 1}, 0)
    assert service.pending_count() == 0
    assert OrderQueryService().list_order_items("p0")[2] == {article: 5}
    assert OrderQueryService().list_order_items("p1")[2] == {article: 1}
    with pytest.raises(ValueError, match="cambiado"):
        service.confirm(review, {"p0": 6}, 0)
    updated = service.list_reviews(pending_only=False)[0]
    service.confirm(updated, {"p0": 6}, 0)
    assert OrderQueryService().list_order_items("p0")[2] == {article: 6}
    assert OrderQueryService().list_order_items("p1")[2] == {}
    assert len(service.list_reviews(pending_only=False)[0].history) == 2


def test_unique_receipt_is_automatic_but_excess_requires_confirmation(receipt_engine):
    from app.services.order_receipt_assignment_service import ReceiptAssignmentService, automate_receipts
    article = _receipt_scenario(receipt_engine, (6,))
    with Session(receipt_engine) as session:
        automate_receipts(session, "p0")
        session.commit()
    service = ReceiptAssignmentService()
    assert service.pending_count() == 0
    assert OrderQueryService().list_order_items("p0")[2] == {article: 6}
    previous = service.list_reviews(pending_only=False)[0]
    with Session(receipt_engine) as session:
        item = session.get(AlbaranItem, "item-new-delivery")
        item.articulo_cantidad = 8
        session.add(item)
        session.commit()
        automate_receipts(session, "p0")
        session.commit()
    assert service.pending_count() == 1
    assert OrderQueryService().list_order_items("p0")[2] == {}
    with pytest.raises(ValueError, match="cambiado"):
        service.confirm(previous, {"p0": 6}, 0)
    revised = service.list_reviews()[0]
    assert revised.allocations == {}
    service.confirm(revised, {"p0": 6}, 2)
    assert service.list_reviews(pending_only=False)[0].excess == 2
    assert OrderQueryService().list_order_items("p0")[2] == {article: 6}


def test_duplicate_import_preserves_confirmed_split(receipt_engine):
    from app.services.order_receipt_assignment_service import ReceiptAssignmentService
    with Session(receipt_engine) as session:
        article = _seed_catalog(session)
        _seed_order(session, "p0", date(2026, 8, 1), "P0", article, 6)
        _seed_order(session, "p1", date(2026, 8, 2), "P1", article, 1)
        session.add(Albaran(albaran_id="old", pedido_id="p1", almacen_id="alm-1"))
        session.commit()
    payload = {"albaran_numero": "NEW", "albaran_fecha": "2026-09-01",
               "articulo_codigo": "REF-1", "articulo_cantidad": "6"}
    importer = OrderDocumentImportService()
    result = importer.import_albaran("p0", payload, [payload])
    assert result.imported == 1 and not result.errors
    service = ReceiptAssignmentService()
    review = service.list_reviews()[0]
    service.confirm(review, {"p0": 5, "p1": 1}, 0)
    result = importer.import_albaran("p0", payload, [payload])
    assert result.already_imported
    reviews = service.list_reviews(pending_only=False)
    assert len(reviews) == 1 and reviews[0].allocations == {"p0": 5, "p1": 1}



def test_reimport_quantity_change_only_reopens_affected_receipt(receipt_engine):
    from app.services.order_receipt_assignment_service import ReceiptAssignmentService
    with Session(receipt_engine) as session:
        article = _seed_catalog(session)
        _seed_order(session, "p0", date(2026, 8, 1), "P0", article, 6)
        session.commit()
    payload = {"albaran_numero": "NEW", "albaran_fecha": "2026-09-01",
               "articulo_codigo": "REF-1", "articulo_cantidad": "6"}
    importer = OrderDocumentImportService()
    assert importer.import_albaran("p0", payload, [payload]).imported == 1
    service = ReceiptAssignmentService()
    before = service.list_reviews(pending_only=False)[0]
    assert before.allocations == {"p0": 6}
    changed = {**payload, "articulo_cantidad": "5"}
    assert importer.import_albaran("p0", changed, [changed]).already_imported
    review = service.list_reviews()[0]
    assert review.item_id == before.item_id
    assert review.cantidad == 5 and review.allocations == {}
    assert OrderQueryService().list_order_items("p0")[2] == {}
    service.confirm(review, {"p0": 5}, 0)
    assert OrderQueryService().list_order_items("p0")[2] == {article: 5}
    rows, _ = OrderQueryService().list_pendientes("p0")
    assert len(rows) == 1 and rows[0].cantidad_pendiente == 1



def test_two_receipts_cannot_consume_the_same_pending_units(receipt_engine):
    from app.services.order_receipt_assignment_service import ReceiptAssignmentService, track_receipt
    article = _receipt_scenario(receipt_engine, (6,))
    with Session(receipt_engine) as session:
        _seed_albaran(session, pedido_id="p0", albaran_id="second", albaran_numero="SECOND",
                      albaran_fecha=date(2026, 9, 1), articulo_id=article, articulo_codigo="REF-1", cantidad=6)
        session.flush()
        track_receipt(session, session.get(AlbaranItem, "item-second"))
        session.commit()
    service = ReceiptAssignmentService()
    first, second = service.list_reviews()
    service.confirm(first, {"p0": 6}, 0)
    with pytest.raises(ValueError, match="pendiente disponible"):
        service.confirm(second, {"p0": 6}, 0)
    assert service.pending_count() == 1
    assert OrderQueryService().list_order_items("p0")[2] == {article: 6}


def test_reimport_changed_article_invalidates_assignment_and_preserves_other_lines(receipt_engine):
    from app.services.order_receipt_assignment_service import ReceiptAssignmentService
    from app.models import AlmacenMovimiento
    with Session(receipt_engine) as session:
        article = _seed_catalog(session)
        session.add(IngredienteIreks(articulo_id="art-2", articulo_referencia="REF-2", articulo_descripcion="Otro"))
        session.add(IngredienteIreks(articulo_id="art-3", articulo_referencia="REF-3", articulo_descripcion="Nuevo"))
        _seed_order(session, "p0", date(2026, 8, 1), "P0", article, 6)
        session.add(PedidoItem(pedido_id="p0", articulo_id="art-2", articulo_cantidad=2))
        session.commit()
    first = {"albaran_numero": "NEW", "albaran_fecha": "2026-09-01", "articulo_codigo": "REF-1", "articulo_cantidad": "6"}
    second = {**first, "articulo_codigo": "REF-2", "articulo_cantidad": "2"}
    importer = OrderDocumentImportService()
    assert importer.import_albaran("p0", first, [first, second]).imported == 2
    service = ReceiptAssignmentService()
    before = {r.articulo: r for r in service.list_reviews(pending_only=False)}
    changed = {**first, "articulo_codigo": "REF-3"}
    assert importer.import_albaran("p0", first, [second, changed]).already_imported
    reviews = service.list_reviews()
    assert len(reviews) == 1 and reviews[0].articulo == "Nuevo"
    unchanged = next(r for r in service.list_reviews(pending_only=False) if r.articulo == "Otro")
    assert unchanged.item_id == before["Otro"].item_id
    assert unchanged.allocations == {"p0": 2} and unchanged.version == before["Otro"].version
    with Session(receipt_engine) as session:
        movement = session.exec(select(AlmacenMovimiento).where(AlmacenMovimiento.albaran_item_id == reviews[0].item_id)).one()
        assert movement.articulo_id == "art-3" and movement.cantidad == 6



def test_reimport_resolved_article_creates_missing_stock_movement(receipt_engine):
    from app.models import AlmacenMovimiento
    with Session(receipt_engine) as session:
        article = _seed_catalog(session)
        _seed_order(session, "p0", date(2026, 8, 1), "P0", article, 6)
        session.commit()
    payload = {"albaran_numero": "NEW", "albaran_fecha": "2026-09-01", "articulo_codigo": "UNKNOWN", "articulo_cantidad": "6"}
    importer = OrderDocumentImportService()
    assert importer.import_albaran("p0", payload, [payload]).imported == 1
    with Session(receipt_engine) as session:
        assert not list(session.exec(select(AlmacenMovimiento)))
        session.add(IngredienteIreks(articulo_id="resolved", articulo_referencia="UNKNOWN", articulo_descripcion="Resolved"))
        session.commit()
    assert importer.import_albaran("p0", payload, [payload]).already_imported
    with Session(receipt_engine) as session:
        movement = session.exec(select(AlmacenMovimiento)).one()
        assert movement.articulo_id == "resolved" and movement.cantidad == 6



def test_historical_surplus_never_funds_future_or_undocumented_orders(receipt_engine):
    from app.services.order_receipt_assignment_service import reconcile_historical_receipts, ReceiptAssignmentService
    with Session(receipt_engine) as session:
        article = _seed_catalog(session)
        _seed_order(session, "source", date(2026, 1, 19), "141", article, 98)
        _seed_order(session, "future", date(2026, 8, 31), "2447", article, 100)
        _seed_order(session, "new", date(2026, 9, 7), "", article, 100)
        _seed_order(session, "undocumented", date(2026, 1, 1), "early", article, 100)
        session.add(Albaran(albaran_id="future-doc", pedido_id="future", almacen_id="alm-1",
                            albaran_fecha=date(2026, 9, 1)))
        _seed_albaran(session, pedido_id="source", albaran_id="old-doc", albaran_numero="2026090005",
                      albaran_fecha=date(2026, 1, 19), articulo_id=article, articulo_codigo="REF-1", cantidad=198)
        session.commit()
        assert reconcile_historical_receipts(session, "source") == 1
        session.commit()
        assert reconcile_historical_receipts(session, "source") == 0
        session.commit()
    query = OrderQueryService()
    assert query.list_order_items("source")[2] == {article: 98}
    for pid in ("future", "new", "undocumented"):
        assert query.list_order_items(pid)[2] == {}
    service = ReceiptAssignmentService()
    review = service.list_reviews()[0]
    assert review.allocations == {"source": 98}
    assert {r.pedido_id for r in review.candidates} == {"source"}
    service.confirm(review, {"source": 98}, 100)
    assert service.pending_count() == 0
    assert query.list_order_items("future")[2] == {}


def test_historical_ambiguity_preserves_documented_units_until_confirmation(receipt_engine):
    from app.services.order_receipt_assignment_service import reconcile_historical_receipts, ReceiptAssignmentService
    with Session(receipt_engine) as session:
        article = _seed_catalog(session)
        for pid, day, qty in [("older", 1, 5), ("old", 2, 5), ("source", 3, 4)]:
            _seed_order(session, pid, date(2026, 6, day), pid, article, qty)
            session.add(Albaran(albaran_id=pid, pedido_id=pid, almacen_id="alm-1", albaran_fecha=date(2026, 6, day)))
        _seed_albaran(session, pedido_id="source", albaran_id="delivery", albaran_numero="D1",
                      albaran_fecha=date(2026, 6, 4), articulo_id=article, articulo_codigo="REF-1", cantidad=7)
        session.commit()
        assert reconcile_historical_receipts(session, "source") == 1
        session.commit()
    query = OrderQueryService()
    assert query.list_order_items("source")[2] == {article: 4}
    assert query.list_order_items("older")[2] == {}
    assert query.list_order_items("old")[2] == {}
    service = ReceiptAssignmentService()
    assert service.pending_count() == 1
    review = service.list_reviews()[0]
    assert review.allocations == {"source": 4}
    service.confirm(review, {"source": 4, "old": 3}, 0)
    assert query.list_order_items("source")[2] == {article: 4}
    assert query.list_order_items("old")[2] == {article: 3}
    assert query.list_order_items("older")[2] == {}
