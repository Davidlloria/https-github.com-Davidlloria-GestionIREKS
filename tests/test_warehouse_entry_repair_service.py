from __future__ import annotations

from datetime import date

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Albaran,
    AlbaranItem,
    AlmacenMovimiento,
    AlmacenStock,
    IngredienteIreks,
    Pedido,
)
from app.services.warehouse_entry_repair_service import WarehouseEntryRepairService


def _engine(tmp_path) -> Engine:  # noqa: ANN001
    database_engine = create_engine(f"sqlite:///{tmp_path / 'warehouse-repair.db'}")
    SQLModel.metadata.create_all(database_engine)
    return database_engine


def _article(article_id: str, full_code: str, short_code: str) -> IngredienteIreks:
    return IngredienteIreks(
        articulo_id=article_id,
        articulo_referencia=full_code,
        articulo_referencia_corta=short_code,
        articulo_descripcion=f"Articulo {short_code}",
    )


def test_repair_deletes_only_proven_orphan_albaran_duplicates(tmp_path) -> None:  # noqa: ANN001
    database_engine = _engine(tmp_path)
    with Session(database_engine) as session:
        session.add(_article("article-1", "120960E", "20960"))
        session.add(
            Pedido(
                pedido_id="valid-order", almacen_id="warehouse-1", pedido_numero="74"
            )
        )
        valid_albaran = Albaran(
            albaran_id="valid-note",
            pedido_id="valid-order",
            almacen_id="warehouse-1",
            albaran_numero="2026090003",
            albaran_fecha=date(2026, 1, 12),
        )
        orphan_albaran = Albaran(
            albaran_id="orphan-note",
            pedido_id="deleted-order",
            almacen_id="warehouse-1",
            albaran_numero="2026090003",
            albaran_fecha=date(2026, 1, 12),
        )
        session.add(valid_albaran)
        session.add(orphan_albaran)
        session.add(
            AlbaranItem(
                item_id="valid-item",
                pedido_id="valid-order",
                albaran_id="valid-note",
                albaran_numero="2026090003",
                albaran_fecha=date(2026, 1, 12),
                articulo_codigo="20960",
                articulo_id="article-1",
                articulo_cantidad=30,
                articulo_lote="LOT-1",
                articulo_caducidad=date(2026, 7, 24),
            )
        )
        session.add(
            AlbaranItem(
                item_id="orphan-item",
                pedido_id="deleted-order",
                albaran_id="orphan-note",
                albaran_numero="2026090003",
                albaran_fecha=date(2026, 1, 12),
                articulo_codigo="120960E",
                articulo_id="article-1",
                articulo_cantidad=30,
                articulo_lote="LOT-1",
                articulo_caducidad=date(2026, 7, 24),
            )
        )
        session.add(
            AlmacenMovimiento(
                almacen_id="warehouse-1",
                articulo_id="article-1",
                pedido_numero="74",
                pedido_albaran_numero="2026090003",
                cantidad=30,
                articulo_lote="LOT-1",
                articulo_caducidad=date(2026, 7, 24),
                fecha_pedido=date(2026, 1, 12),
                albaran_item_id="valid-item",
            )
        )
        session.add(
            AlmacenStock(
                almacen_id="warehouse-1", articulo_id="article-1", cantidad_total=999
            )
        )
        session.commit()

    service = WarehouseEntryRepairService(database_engine)
    result = service.repair()

    assert result.deleted_orphan_albaranes == 1
    assert result.deleted_orphan_items == 1
    assert result.unresolved_orphan_albaranes == 0
    assert not any(result.after.as_dict().values())
    assert result.integrity_check == "ok"
    with Session(database_engine) as session:
        assert session.get(Albaran, "orphan-note") is None
        assert session.get(AlbaranItem, "orphan-item") is None
        assert session.get(Albaran, "valid-note") is not None
        stock = session.get(AlmacenStock, ("warehouse-1", "article-1"))
        assert stock is not None
        assert stock.cantidad_total == 30


def test_repair_creates_synchronizes_and_deduplicates_entries(tmp_path) -> None:  # noqa: ANN001
    database_engine = _engine(tmp_path)
    with Session(database_engine) as session:
        session.add(_article("article-1", "120960E", "20960"))
        session.add(_article("article-2", "129302E", "29302"))
        session.add(
            Pedido(pedido_id="order-1", almacen_id="warehouse-1", pedido_numero="100")
        )
        session.add(
            Albaran(
                albaran_id="note-1",
                pedido_id="order-1",
                almacen_id="warehouse-1",
                albaran_numero="ALB-1",
                albaran_fecha=date(2026, 2, 1),
            )
        )
        for item_id, article_id, code, quantity in (
            ("item-1", "article-1", "20960", 4),
            ("item-2", "article-2", "29302", 6),
        ):
            session.add(
                AlbaranItem(
                    item_id=item_id,
                    pedido_id="order-1",
                    albaran_id="note-1",
                    albaran_numero="ALB-1",
                    albaran_fecha=date(2026, 2, 1),
                    articulo_codigo=code,
                    articulo_id=article_id,
                    articulo_cantidad=quantity,
                    articulo_lote="LOT",
                )
            )
        for quantity in (2, 4):
            session.add(
                AlmacenMovimiento(
                    almacen_id="wrong-warehouse",
                    articulo_id="article-1",
                    pedido_numero="wrong-order",
                    pedido_albaran_numero="wrong-note",
                    cantidad=quantity,
                    articulo_lote="wrong-lot",
                    fecha_pedido=date(2025, 1, 1),
                    albaran_item_id="item-1",
                )
            )
        session.commit()

    service = WarehouseEntryRepairService(database_engine)
    result = service.repair()

    assert result.created_entries == 1
    assert result.deleted_duplicate_entries == 1
    assert result.updated_entries == 1
    assert not any(result.after.as_dict().values())
    with Session(database_engine) as session:
        movements = list(
            session.exec(
                select(AlmacenMovimiento).order_by(AlmacenMovimiento.articulo_id)
            )
        )
        assert len(movements) == 2
        first = movements[0]
        assert first.almacen_id == "warehouse-1"
        assert first.pedido_numero == "100"
        assert first.pedido_albaran_numero == "ALB-1"
        assert first.cantidad == 4
        assert first.articulo_lote == "LOT"
        assert first.fecha_pedido == date(2026, 2, 1)

    second_result = service.repair()
    assert second_result.created_entries == 0
    assert second_result.deleted_duplicate_entries == 0
    assert second_result.updated_entries == 0
    assert not any(second_result.after.as_dict().values())
