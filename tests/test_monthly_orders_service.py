from __future__ import annotations

from datetime import date

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.models import AlmacenMovimiento, IngredienteIreks, Pedido, PedidoItem
from app.services.monthly_orders_service import MonthlyOrdersService


def _engine(tmp_path) -> Engine:  # noqa: ANN001
    database_engine = create_engine(f"sqlite:///{tmp_path / 'monthly-orders.db'}")
    SQLModel.metadata.create_all(database_engine)
    return database_engine


def test_monthly_views_use_received_entries_and_keep_order_details(tmp_path) -> None:  # noqa: ANN001
    database_engine = _engine(tmp_path)
    with Session(database_engine) as session:
        session.add(
            IngredienteIreks(
                articulo_id="article-1",
                articulo_referencia="120960E",
                articulo_referencia_corta="20960",
                articulo_descripcion="MUFFIN PLUS",
                articulo_envase_peso_total=25,
            )
        )
        session.add(
            Pedido(
                pedido_id="order-1",
                almacen_id="warehouse-1",
                pedido_numero="100",
                pedido_fecha=date(2026, 1, 5),
            )
        )
        session.add(
            PedidoItem(
                item_id="order-item-1",
                pedido_id="order-1",
                pedido_numero="100",
                pedido_item_fecha=date(2026, 1, 5),
                articulo_id="article-1",
                articulo_cantidad=99,
            )
        )
        for movement_id, quantity in ((1, 3), (2, 2)):
            session.add(
                AlmacenMovimiento(
                    id=movement_id,
                    almacen_id="warehouse-1",
                    articulo_id="article-1",
                    pedido_numero="100",
                    pedido_albaran_numero="ALB-1",
                    cantidad=quantity,
                    fecha_pedido=date(2026, 1, 12),
                )
            )
        session.add(
            AlmacenMovimiento(
                id=3,
                almacen_id="warehouse-1",
                articulo_id="article-1",
                pedido_numero="100",
                cantidad=-1,
                fecha_pedido=date(2026, 1, 15),
            )
        )
        session.add(
            AlmacenMovimiento(
                id=4,
                almacen_id="warehouse-2",
                articulo_id="article-1",
                pedido_numero="200",
                cantidad=7,
                fecha_pedido=date(2026, 1, 20),
            )
        )
        session.commit()

    service = MonthlyOrdersService()
    with Session(database_engine) as session:
        rows = service.product_monthly_rows(
            session,
            articulo_id="article-1",
            almacen_id="warehouse-1",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
        )
        annual = service.annual_product_matrix(
            session, year=2026, almacen_id="warehouse-1"
        )
        details = service.product_order_details(
            session, articulo_id="article-1", almacen_id="warehouse-1"
        )

    assert len(rows) == 1
    assert rows[0].quantity == 5
    assert rows[0].kg == 125
    assert rows[0].order_count == 1
    assert rows[0].last_order_date == date(2026, 1, 12)
    assert len(annual) == 1
    assert annual[0].monthly_quantities[0] == 5
    assert annual[0].total_quantity == 5
    assert annual[0].total_kg == 125
    assert len(details) == 1
    assert details[0].quantity == 99
