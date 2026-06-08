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
