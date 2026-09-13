from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

import app.core.database as database


def test_migration_adds_affected_units_to_existing_incidents_table(tmp_path: Path, monkeypatch) -> None:
    test_engine = create_engine(f"sqlite:///{tmp_path / 'legacy-incidents.db'}")
    with test_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE pedidos_incidencias (
                incidencia_id TEXT PRIMARY KEY,
                pedido_id TEXT NOT NULL,
                albaran_item_id TEXT NOT NULL,
                observaciones TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO pedidos_incidencias (incidencia_id, pedido_id, albaran_item_id) VALUES ('i-1', 'p-1', 'a-1')"
        )
    monkeypatch.setattr(database, "engine", test_engine)

    database._migrate_pedidos_incidencias_columns()

    with test_engine.connect() as connection:
        columns = {
            str(row[1]): str(row[2])
            for row in connection.exec_driver_sql("PRAGMA table_info(pedidos_incidencias)").fetchall()
        }
        row = connection.exec_driver_sql(
            "SELECT unidades_afectadas FROM pedidos_incidencias WHERE incidencia_id='i-1'"
        ).fetchone()
    assert columns["unidades_afectadas"] == "INTEGER"
    assert row == (0,)


def test_migration_normalizes_previous_fractional_affected_units(tmp_path: Path, monkeypatch) -> None:
    test_engine = create_engine(f"sqlite:///{tmp_path / 'fractional-incidents.db'}")
    with test_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE pedidos_incidencias (
                incidencia_id TEXT PRIMARY KEY,
                unidades_afectadas REAL NOT NULL DEFAULT 0
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO pedidos_incidencias (incidencia_id, unidades_afectadas) VALUES ('i-1', 0.01), ('i-2', 2.6)"
        )
    monkeypatch.setattr(database, "engine", test_engine)

    database._migrate_pedidos_incidencias_columns()

    with test_engine.connect() as connection:
        rows = connection.exec_driver_sql(
            "SELECT incidencia_id, unidades_afectadas FROM pedidos_incidencias ORDER BY incidencia_id"
        ).fetchall()
    assert rows == [("i-1", 1.0), ("i-2", 3.0)]


def test_shortage_schema_upgrade_preserves_original_quantities(tmp_path, monkeypatch):
    from app.models import PedidoFaltante, PedidoFaltanteMovimiento
    test_engine = create_engine(f"sqlite:///{tmp_path / 'legacy-delivery.db'}")
    with test_engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE albaranes_items (item_id TEXT PRIMARY KEY, articulo_id TEXT, articulo_codigo TEXT, articulo_cantidad REAL)")
        connection.exec_driver_sql("INSERT INTO albaranes_items VALUES ('line', 'product', 'D1203041', 24)")
        connection.exec_driver_sql("CREATE TABLE productos_ireks (articulo_id TEXT, articulo_referencia TEXT, articulo_referencia_corta TEXT)")
    monkeypatch.setattr(database, "engine", test_engine)
    database._migrate_albaranes_items_schema()
    database._migrate_albaranes_items_schema()
    PedidoFaltante.__table__.create(test_engine)
    PedidoFaltanteMovimiento.__table__.create(test_engine)
    with test_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT articulo_cantidad, cantidad_recibida_confirmada FROM albaranes_items").one() == (24, None)
