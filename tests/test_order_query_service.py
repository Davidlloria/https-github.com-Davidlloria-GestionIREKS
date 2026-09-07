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


def test_list_article_order_history_orders_limits_aggregates_and_excludes_current_order(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        for day in range(1, 8):
            pedido_id = f"pedido-{day}"
            session.add(
                Pedido(
                    pedido_id=pedido_id,
                    almacen_id="alm-1",
                    pedido_fecha=date(2026, 6, day),
                    pedido_numero=f"A-{day:03d}",
                )
            )
            session.add(
                PedidoItem(
                    item_id=f"item-{day}",
                    pedido_id=pedido_id,
                    pedido_numero=f"A-{day:03d}",
                    pedido_item_fecha=date(2026, 6, day),
                    articulo_id=articulo_id,
                    articulo_cantidad=float(day),
                )
            )
        session.add(
            PedidoItem(
                item_id="item-7-extra",
                pedido_id="pedido-7",
                pedido_numero="A-007",
                pedido_item_fecha=date(2026, 6, 7),
                articulo_id=articulo_id,
                articulo_cantidad=0.5,
            )
        )
        for pedido_id, almacen_id, day, quantity in (
            ("pedido-actual", "alm-1", 8, 80.0),
            ("pedido-futuro", "alm-1", 9, 90.0),
            ("pedido-otro-almacen", "alm-2", 7, 70.0),
        ):
            session.add(
                Pedido(
                    pedido_id=pedido_id,
                    almacen_id=almacen_id,
                    pedido_fecha=date(2026, 6, day),
                    pedido_numero=pedido_id,
                )
            )
            session.add(
                PedidoItem(
                    item_id=f"item-{pedido_id}",
                    pedido_id=pedido_id,
                    pedido_numero=pedido_id,
                    pedido_item_fecha=date(2026, 6, day),
                    articulo_id=articulo_id,
                    articulo_cantidad=quantity,
                )
            )
        session.commit()

    history = OrderQueryService().list_article_order_history(
        "alm-1",
        articulo_id,
        reference_date=date(2026, 6, 8),
        exclude_pedido_id="pedido-actual",
        limit=5,
    )

    assert [row.pedido_id for row in history] == ["pedido-7", "pedido-6", "pedido-5", "pedido-4", "pedido-3"]
    assert [row.unidades for row in history] == [7.5, 6.0, 5.0, 4.0, 3.0]


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


def test_list_order_items_returns_received_quantity_by_article(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        session.add(
            Pedido(
                pedido_id="pedido-1",
                almacen_id="alm-1",
                pedido_fecha=date(2026, 6, 10),
                pedido_numero="A-001",
            )
        )
        session.add(
            PedidoItem(
                pedido_id="pedido-1",
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
                pedido_id="pedido-1",
                albaran_numero="ALB-1",
                albaran_fecha=date(2026, 6, 11),
            )
        )
        session.add(
            AlbaranItem(
                item_id="alb-item-1",
                pedido_id="pedido-1",
                albaran_id="alb-1",
                albaran_numero="ALB-1",
                albaran_fecha=date(2026, 6, 11),
                articulo_codigo="REF-1",
                articulo_id=articulo_id,
                articulo_cantidad=1.5,
            )
        )
        session.add(
            AlbaranItem(
                item_id="alb-item-2",
                pedido_id="pedido-1",
                albaran_id="alb-1",
                albaran_numero="ALB-1",
                albaran_fecha=date(2026, 6, 11),
                articulo_codigo="REF-1",
                articulo_id=articulo_id,
                articulo_cantidad=0.5,
            )
        )
        session.commit()

    service = OrderQueryService()
    rows, pending_article_ids, received_by_article = service.list_order_items("pedido-1")

    assert len(rows) == 1
    assert pending_article_ids == {articulo_id}
    assert received_by_article == {articulo_id: 2.0}



def test_list_order_items_uses_assigned_units_without_double_counting(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        articulo_id = _seed_catalog(session)
        session.add(Albaran(albaran_id="alb-1", almacen_id="alm-1", pedido_id="pedido-1",
                            albaran_numero="ALB-1", albaran_fecha=date(2026, 6, 1)))
        session.add(Pedido(pedido_id="pedido-1", almacen_id="alm-1", pedido_fecha=date(2026, 6, 1), pedido_numero="P-1"))
        session.add(PedidoItem(pedido_id="pedido-1", pedido_numero="P-1", pedido_item_fecha=date(2026, 6, 1), articulo_id=articulo_id, articulo_cantidad=10.0))
        session.add(Pedido(pedido_id="pedido-2", almacen_id="alm-1", pedido_fecha=date(2026, 6, 2), pedido_numero="P-2"))
        session.add(PedidoItem(pedido_id="pedido-2", pedido_numero="P-2", pedido_item_fecha=date(2026, 6, 2), articulo_id=articulo_id, articulo_cantidad=5.0))
        session.add(Albaran(albaran_id="alb-2", almacen_id="alm-1", pedido_id="pedido-2", albaran_numero="ALB-2", albaran_fecha=date(2026, 6, 3)))
        session.add(AlbaranItem(item_id="alb-item-2", pedido_id="pedido-2", albaran_id="alb-2", albaran_numero="ALB-2", albaran_fecha=date(2026, 6, 3), articulo_codigo="REF-1", articulo_id=articulo_id, articulo_cantidad=7.0))
        session.commit()

    service = OrderQueryService()
    rows, pending_article_ids, received_by_article = service.list_order_items("pedido-2")

    assert len(rows) == 1
    assert pending_article_ids == set()
    assert received_by_article == {articulo_id: 5.0}
    assert service.list_order_items("pedido-1")[2] == {articulo_id: 2.0}


def test_order_dialog_history_limit_sums_received_units(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        article_id = _seed_catalog(session)
        for order_id, day, warehouse, quantity in [
            ("old", 1, "alm-1", 2), ("recent", 2, "alm-1", 3),
            ("current", 3, "alm-1", 50), ("future", 4, "alm-1", 100),
            ("other", 2, "alm-2", 200),
        ]:
            session.add(Pedido(pedido_id=order_id, almacen_id=warehouse,
                               pedido_fecha=date(2026, 6, day), pedido_numero=order_id))
            session.add(AlbaranItem(item_id=order_id, pedido_id=order_id,
                                   articulo_id=article_id, articulo_cantidad=quantity))
        session.commit()
    service = OrderQueryService()
    for limit, expected in [(1, 3), (2, 5), (100, 5)]:
        result = service.order_dialog_catalogs(
            "alm-1", True, reference_date=date(2026, 6, 3),
            exclude_pedido_id="current", history_limit=limit,
        )
        assert result[4] == {article_id: expected}
