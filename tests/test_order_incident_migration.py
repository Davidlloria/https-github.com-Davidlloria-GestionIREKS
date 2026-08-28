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
