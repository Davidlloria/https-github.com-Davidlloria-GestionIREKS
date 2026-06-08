from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

import app.services.order_query_service as order_query_service_module
from app.models import Albaran, AlbaranItem, Fabricante, Familia, IngredienteIreks, Pedido, PedidoItem, Subfamilia
from app.services.order_query_service import OrderQueryService


@pytest.fixture()
def isolated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'orders.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
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
            articulo_envase_peso_total=12.5,
            articulo_familia_id=familia_id,
            articulo_subfamilia_id=subfamilia_id,
            articulo_status_en_lista=True,
        )
    )
    session.commit()
    return articulo_id


def test_order_dialog_catalogs_uses_previous_order_and_excludes_current_order(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        session.add(
            Pedido(
                pedido_id="pedido-prev",
                almacen_id="alm-1",
                pedido_fecha=date(2026, 6, 10),
                pedido_numero="A-001",
            )
        )
        session.add(
            PedidoItem(
                pedido_id="pedido-prev",
                pedido_numero="A-001",
                pedido_item_fecha=date(2026, 6, 10),
                articulo_id=articulo_id,
                articulo_cantidad=4.0,
            )
        )
        session.add(
            Albaran(
                albaran_id="alb-1",
                almacen_id="alm-1",
                pedido_id="pedido-prev",
                albaran_numero="ALB-1",
                albaran_fecha=date(2026, 6, 10),
            )
        )
        session.add(
            AlbaranItem(
                item_id="alb-item-1",
                pedido_id="pedido-prev",
                albaran_id="alb-1",
                albaran_numero="ALB-1",
                albaran_fecha=date(2026, 6, 10),
                articulo_codigo="REF-1",
                articulo_id=articulo_id,
                articulo_cantidad=2.5,
            )
        )
        session.add(
            Pedido(
                pedido_id="pedido-actual",
                almacen_id="alm-1",
                pedido_fecha=date(2026, 6, 10),
                pedido_numero="A-002",
            )
        )
        session.add(
            PedidoItem(
                pedido_id="pedido-actual",
                pedido_numero="A-002",
                pedido_item_fecha=date(2026, 6, 10),
                articulo_id=articulo_id,
                articulo_cantidad=7.0,
            )
        )
        session.commit()

    service = OrderQueryService()
    _rows, _fabricantes, _familias, _subfamilias, prev_qty_by_articulo, _pending_qty_by_articulo = service.order_dialog_catalogs(
        "alm-1",
        True,
        reference_date=date(2026, 6, 10),
        exclude_pedido_id="pedido-actual",
    )

    assert prev_qty_by_articulo == {articulo_id: 2.5}


def test_order_dialog_catalogs_can_disable_history(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        session.add(
            Pedido(
                pedido_id="pedido-prev",
                almacen_id="alm-1",
                pedido_fecha=date(2026, 6, 9),
                pedido_numero="A-001",
            )
        )
        session.add(
            PedidoItem(
                pedido_id="pedido-prev",
                pedido_numero="A-001",
                pedido_item_fecha=date(2026, 6, 9),
                articulo_id=articulo_id,
                articulo_cantidad=4.0,
            )
        )
        session.commit()

    service = OrderQueryService()
    _rows, _fabricantes, _familias, _subfamilias, prev_qty_by_articulo, _pending_qty_by_articulo = service.order_dialog_catalogs(
        "alm-1",
        False,
        reference_date=date(2026, 6, 10),
    )

    assert prev_qty_by_articulo == {}
