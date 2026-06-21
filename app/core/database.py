from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path
import os
import shutil
import sqlite3
from typing import Any
from uuid import uuid4
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import DATA_DIR, DB_PATH, DB_URL, LEGACY_DB_PATH

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXTERNAL_DATA_DIR = bool(os.environ.get("GESTION_IREKS_DATA_DIR"))


def _bootstrap_database_file() -> None:
    if EXTERNAL_DATA_DIR:
        if not DB_PATH.exists():
            raise RuntimeError(
                "No existe la base de datos externa para el ejecutable.\n"
                "Crea GestionIREKSReactDesktop/data/gestion_ireks.db o vuelve a ejecutar el build."
            )
        if DB_PATH.stat().st_size == 0:
            raise RuntimeError(
                "La base de datos externa para el ejecutable esta vacia.\n"
                "Crea GestionIREKSReactDesktop/data/gestion_ireks.db con la base de datos real."
            )
        return
    if DB_PATH.exists() or not LEGACY_DB_PATH.exists():
        return
    shutil.copy2(LEGACY_DB_PATH, DB_PATH)
    for suffix in ("-wal", "-shm"):
        legacy_sidecar = LEGACY_DB_PATH.with_name(f"{LEGACY_DB_PATH.name}{suffix}")
        new_sidecar = DB_PATH.with_name(f"{DB_PATH.name}{suffix}")
        if legacy_sidecar.exists() and not new_sidecar.exists():
            shutil.copy2(legacy_sidecar, new_sidecar)


_bootstrap_database_file()
engine = create_engine(DB_URL, echo=False, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


CLIENTE_COLUMNS = [
    "cliente_id",
    "cliente_codigo",
    "cliente_nombre_comercial",
    "cliente_nombre_fiscal",
    "cliente_nombre_interno",
    "cliente_abreviatura",
    "cliente_cif",
    "cliente_telefono",
    "cliente_email",
    "cliente_direccion",
    "cliente_direccion_cp",
    "cliente_direccion_localidad_id",
    "cliente_direccion_municipio_id",
    "cliente_direccion_provincia_id",
    "cliente_direccion_isla_id",
    "cliente_tipo",
    "cliente_actividad",
    "cliente_prospeccion",
    "distribuidor_id",
    "activo",
]


def _migrate_ingredient_columns() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "ingredientes_ireks" in tables and "productos_ireks" not in tables:
            conn.exec_driver_sql("ALTER TABLE ingredientes_ireks RENAME TO productos_ireks")
            tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        for table in ("productos_ireks", "ingredientes_ireks", "ingredientes_std"):
            if table not in tables:
                continue
            columns = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()]
            if "descripcion" in columns and "nombre" not in columns:
                conn.exec_driver_sql(f"ALTER TABLE {table} RENAME COLUMN descripcion TO nombre")


def _migrate_almacen_table() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        if "almacen" in tables:
            almacen_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(almacen)").fetchall()]
            is_old_catalog = "almacen_id" in almacen_cols and "almacen_nombre" in almacen_cols and "articulo_id" not in almacen_cols
            if is_old_catalog and "almacenes_catalogo" not in tables:
                conn.exec_driver_sql("ALTER TABLE almacen RENAME TO almacenes_catalogo")
                tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        # Migracion de nombre: tabla de movimientos legacy `almacen` -> `almacen_movimientos`
        if "almacen_movimientos" not in tables and "almacen" in tables:
            conn.exec_driver_sql("ALTER TABLE almacen RENAME TO almacen_movimientos")
            tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        if "almacen_movimientos" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE almacen_movimientos (
                    id INTEGER PRIMARY KEY,
                    almacen_id TEXT NOT NULL DEFAULT '',
                    articulo_id TEXT NOT NULL DEFAULT '',
                    pedido_numero TEXT NOT NULL DEFAULT '',
                    pedido_albaran_numero TEXT NOT NULL DEFAULT '',
                    cantidad REAL NOT NULL DEFAULT 0,
                    articulo_lote TEXT NOT NULL DEFAULT '',
                    articulo_caducidad DATE,
                    fecha_pedido DATE NOT NULL DEFAULT (DATE('now')),
                    albaran_item_id TEXT NOT NULL DEFAULT ''
                )
                """
            )
            tables.add("almacen_movimientos")
        else:
            columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(almacen_movimientos)").fetchall()]
            expected = {
                "id",
                "almacen_id",
                "articulo_id",
                "pedido_numero",
                "pedido_albaran_numero",
                "cantidad",
                "articulo_lote",
                "articulo_caducidad",
                "fecha_pedido",
                "albaran_item_id",
            }
            if not (expected.issubset(set(columns)) and len(columns) == len(expected)):
                rows = conn.exec_driver_sql("SELECT * FROM almacen_movimientos").fetchall()
                idx = {name: pos for pos, name in enumerate(columns)}

                def _get(row: Sequence[Any], key: str) -> str:
                    pos = idx.get(key)
                    if pos is None:
                        return ""
                    value = row[pos]
                    return "" if value is None else str(value).strip()

                converted: list[tuple] = []
                for row in rows:
                    almacen_id = _get(row, "almacen_id")
                    articulo_id = _get(row, "articulo_id")
                    if not almacen_id or not articulo_id:
                        continue
                    fecha_pedido = _get(row, "fecha_pedido") or _get(row, "pedido_item_fecha") or date.today().isoformat()
                    cantidad_raw = _get(row, "cantidad") or _get(row, "articulo_envase_cantidad") or "0"
                    pedido_numero = _get(row, "pedido_numero")
                    pedido_albaran_numero = _get(row, "pedido_albaran_numero")
                    articulo_lote = _get(row, "articulo_lote")
                    articulo_caducidad_raw = _get(row, "articulo_caducidad")
                    articulo_caducidad = articulo_caducidad_raw or None
                    albaran_item_id = _get(row, "albaran_item_id")
                    try:
                        cantidad = float(cantidad_raw.replace(",", "."))
                    except Exception:
                        cantidad = 0.0
                    converted.append(
                        (
                            almacen_id,
                            articulo_id,
                            pedido_numero,
                            pedido_albaran_numero,
                            cantidad,
                            articulo_lote,
                            articulo_caducidad,
                            fecha_pedido,
                            albaran_item_id,
                        )
                    )

                conn.exec_driver_sql("ALTER TABLE almacen_movimientos RENAME TO almacen_movimientos_old_schema")
                conn.exec_driver_sql(
                    """
                    CREATE TABLE almacen_movimientos (
                        id INTEGER PRIMARY KEY,
                        almacen_id TEXT NOT NULL DEFAULT '',
                        articulo_id TEXT NOT NULL DEFAULT '',
                        pedido_numero TEXT NOT NULL DEFAULT '',
                        pedido_albaran_numero TEXT NOT NULL DEFAULT '',
                        cantidad REAL NOT NULL DEFAULT 0,
                        articulo_lote TEXT NOT NULL DEFAULT '',
                        articulo_caducidad DATE,
                        fecha_pedido DATE NOT NULL DEFAULT (DATE('now')),
                        albaran_item_id TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                for (
                    almacen_id,
                    articulo_id,
                    pedido_numero,
                    pedido_albaran_numero,
                    cantidad,
                    articulo_lote,
                    articulo_caducidad,
                    fecha_pedido,
                    albaran_item_id,
                ) in converted:
                    conn.exec_driver_sql(
                        """
                        INSERT INTO almacen_movimientos (
                            almacen_id, articulo_id, pedido_numero, pedido_albaran_numero,
                            cantidad, articulo_lote, articulo_caducidad, fecha_pedido, albaran_item_id
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            almacen_id,
                            articulo_id,
                            pedido_numero,
                            pedido_albaran_numero,
                            cantidad,
                            articulo_lote,
                            articulo_caducidad,
                            fecha_pedido,
                            albaran_item_id,
                        ),
                    )
                conn.exec_driver_sql("DROP TABLE almacen_movimientos_old_schema")

        if "almacen_stock" not in tables:
            conn.exec_driver_sql(
                """
                CREATE TABLE almacen_stock (
                    almacen_id TEXT NOT NULL,
                    articulo_id TEXT NOT NULL,
                    cantidad_total REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (almacen_id, articulo_id)
                )
                """
            )


def _migrate_productos_ireks_schema() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "productos_ireks" not in tables:
            return
        info = conn.exec_driver_sql("PRAGMA table_info(productos_ireks)").fetchall()
        columns = [row[1] for row in info]
        expected = {
            "id",
            "almacen_id",
            "fabricante_id",
            "distribuidor_id",
            "articulo_id",
            "articulo_referencia",
            "articulo_referencia_corta",
            "articulo_descripcion",
            "articulo_envase_id",
            "articulo_contenido_unidad",
            "articulo_envase_cantidad",
            "articulo_envase_peso",
            "articulo_envase_unidad_medida",
            "articulo_envase_peso_total",
            "transporte_pallet_tipo",
            "transporte_cajas_por_capa",
            "transporte_capas_por_pallet",
            "transporte_cajas_por_pallet",
            "transporte_unidades_por_pallet",
            "transporte_kg_por_pallet",
            "transporte_observaciones",
            "articulo_familia_id",
            "articulo_grupo_id",
            "articulo_subfamilia_id",
            "categoria",
            "articulo_status_activo",
            "articulo_status_en_lista",
        }
        has_legacy_active_col = "activo" in columns
        if expected.issubset(set(columns)) and not has_legacy_active_col:
            return

        rows = conn.exec_driver_sql("SELECT * FROM productos_ireks").fetchall()
        idx = {name: pos for pos, name in enumerate(columns)}

        def _get(row: Sequence[Any], key: str) -> str:
            pos = idx.get(key)
            if pos is None:
                return ""
            value = row[pos]
            return "" if value is None else str(value).strip()

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("ALTER TABLE productos_ireks RENAME TO productos_ireks_old_schema")
        conn.exec_driver_sql(
            """
            CREATE TABLE productos_ireks (
                id INTEGER PRIMARY KEY,
                almacen_id TEXT NOT NULL DEFAULT '',
                fabricante_id TEXT NOT NULL DEFAULT '',
                distribuidor_id TEXT NOT NULL DEFAULT '',
                articulo_id TEXT NOT NULL DEFAULT '',
                articulo_referencia TEXT NOT NULL DEFAULT '',
                articulo_referencia_corta TEXT NOT NULL DEFAULT '',
                articulo_descripcion TEXT NOT NULL DEFAULT '',
                articulo_envase_id TEXT NOT NULL DEFAULT '',
                articulo_contenido_unidad TEXT NOT NULL DEFAULT '',
                articulo_envase_cantidad REAL NOT NULL DEFAULT 0,
                articulo_envase_peso REAL NOT NULL DEFAULT 0,
                articulo_envase_unidad_medida TEXT NOT NULL DEFAULT '',
                articulo_envase_peso_total REAL NOT NULL DEFAULT 0,
                transporte_pallet_tipo TEXT NOT NULL DEFAULT '',
                transporte_cajas_por_capa REAL NOT NULL DEFAULT 0,
                transporte_capas_por_pallet REAL NOT NULL DEFAULT 0,
                transporte_cajas_por_pallet REAL NOT NULL DEFAULT 0,
                transporte_unidades_por_pallet REAL NOT NULL DEFAULT 0,
                transporte_kg_por_pallet REAL NOT NULL DEFAULT 0,
                transporte_observaciones TEXT NOT NULL DEFAULT '',
                articulo_familia_id TEXT NOT NULL DEFAULT '',
                articulo_grupo_id TEXT NOT NULL DEFAULT '',
                articulo_subfamilia_id TEXT NOT NULL DEFAULT '',
                categoria TEXT NOT NULL DEFAULT '',
                articulo_status_activo BOOLEAN NOT NULL DEFAULT 1,
                articulo_status_en_lista BOOLEAN NOT NULL DEFAULT 0
            )
            """
        )
        for row in rows:
            raw_active = (_get(row, "activo") or "1").lower()
            activo = 0 if raw_active in {"0", "false", "no", "n"} else 1
            raw_status_activo = (_get(row, "articulo_status_activo") or "").lower()
            raw_status_en_lista = (_get(row, "articulo_status_en_lista") or "").lower()
            parsed_status_activo = None
            parsed_status_en_lista = None
            if raw_status_activo:
                parsed_status_activo = 0 if raw_status_activo in {"0", "false", "no", "n"} else 1
            if raw_status_en_lista:
                parsed_status_en_lista = 1 if raw_status_en_lista in {"1", "true", "si", "sí", "s", "y", "yes"} else 0
            if parsed_status_activo is None and parsed_status_en_lista is None:
                status_activo = activo
                status_en_lista = 0
            elif parsed_status_activo is None:
                status_en_lista = parsed_status_en_lista or 0
                status_activo = activo
            elif parsed_status_en_lista is None:
                status_activo = parsed_status_activo
                status_en_lista = 0
            else:
                status_activo = parsed_status_activo
                status_en_lista = parsed_status_en_lista
            activo = status_activo
            try:
                envase_cantidad = float((_get(row, "articulo_envase_cantidad") or _get(row, "cantidad_envase") or "0").replace(",", "."))
            except Exception:
                envase_cantidad = 0.0
            try:
                envase_peso = float((_get(row, "articulo_envase_peso") or "0").replace(",", "."))
            except Exception:
                envase_peso = 0.0
            row_id_raw = _get(row, "id")
            row_id = int(row_id_raw) if row_id_raw.isdigit() else None
            conn.exec_driver_sql(
                """
                INSERT INTO productos_ireks (
                    id, almacen_id, fabricante_id, distribuidor_id, articulo_id, articulo_referencia,
                    articulo_referencia_corta, articulo_descripcion, articulo_envase_id, articulo_contenido_unidad,
                    articulo_envase_cantidad, articulo_envase_peso, articulo_envase_unidad_medida, articulo_envase_peso_total,
                    transporte_pallet_tipo, transporte_cajas_por_capa, transporte_capas_por_pallet,
                    transporte_cajas_por_pallet, transporte_unidades_por_pallet, transporte_kg_por_pallet,
                    transporte_observaciones,
                    articulo_familia_id, articulo_grupo_id, articulo_subfamilia_id,
                    categoria, articulo_status_activo, articulo_status_en_lista
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    _get(row, "almacen_id"),
                    _get(row, "fabricante_id") or _get(row, "marca"),
                    _get(row, "distribuidor_id"),
                    _get(row, "articulo_id") or str(uuid4()),
                    _get(row, "articulo_referencia") or _get(row, "referencia") or _get(row, "codigo"),
                    _get(row, "articulo_referencia_corta") or _get(row, "codigo"),
                    _get(row, "articulo_descripcion") or _get(row, "nombre"),
                    _get(row, "articulo_envase_id") or _get(row, "unidad_envase"),
                    _get(row, "articulo_contenido_unidad") or _get(row, "unidad_contenido"),
                    envase_cantidad,
                    envase_peso,
                    _get(row, "articulo_envase_unidad_medida"),
                    envase_cantidad * envase_peso,
                    _get(row, "transporte_pallet_tipo"),
                    _get(row, "transporte_cajas_por_capa") or 0,
                    _get(row, "transporte_capas_por_pallet") or 0,
                    _get(row, "transporte_cajas_por_pallet") or 0,
                    _get(row, "transporte_unidades_por_pallet") or 0,
                    _get(row, "transporte_kg_por_pallet") or 0,
                    _get(row, "transporte_observaciones"),
                    _get(row, "articulo_familia_id") or _get(row, "familia"),
                    _get(row, "articulo_grupo_id") or _get(row, "familia"),
                    _get(row, "articulo_subfamilia_id") or _get(row, "subfamilia"),
                    _get(row, "categoria"),
                    status_activo,
                    status_en_lista,
                ),
            )
        conn.exec_driver_sql("DROP TABLE productos_ireks_old_schema")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _extract_cliente_value(row: Sequence[Any], idx: dict[str, int], key: str) -> str:
    pos = idx.get(key)
    if pos is None:
        return ""
    val = row[pos]
    return "" if val is None else str(val).strip()


def _migrate_client_table() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "clientes" not in tables:
            return

        info = conn.exec_driver_sql("PRAGMA table_info(clientes)").fetchall()
        columns = [row[1] for row in info]
        if "cliente_grupo" in columns and "cliente_actividad" not in columns:
            conn.exec_driver_sql("ALTER TABLE clientes RENAME COLUMN cliente_grupo TO cliente_actividad")
            info = conn.exec_driver_sql("PRAGMA table_info(clientes)").fetchall()
            columns = [row[1] for row in info]
        is_exact = set(columns) == set(CLIENTE_COLUMNS) and len(columns) == len(CLIENTE_COLUMNS)
        pk_ok = any(row[1] == "cliente_id" and int(row[5] or 0) == 1 for row in info)
        if is_exact and pk_ok:
            return

        rows = conn.exec_driver_sql("SELECT * FROM clientes").fetchall()
        idx = {name: pos for pos, name in enumerate(columns)}

        prepared: list[tuple] = []
        used_ids: set[str] = set()
        used_codes: set[int] = set()
        max_code = 0
        for row in rows:
            cliente_id = (
                _extract_cliente_value(row, idx, "cliente_id")
                or _extract_cliente_value(row, idx, "empresa_id")
                or _extract_cliente_value(row, idx, "id")
                or str(uuid4())
            )
            if cliente_id in used_ids:
                cliente_id = str(uuid4())
            used_ids.add(cliente_id)

            nombre_comercial = (
                _extract_cliente_value(row, idx, "cliente_nombre_comercial")
                or _extract_cliente_value(row, idx, "nombre_comercial")
            )
            nombre_fiscal = (
                _extract_cliente_value(row, idx, "cliente_nombre_fiscal")
                or _extract_cliente_value(row, idx, "nombre_fiscal")
            )
            if not nombre_comercial and nombre_fiscal:
                nombre_comercial = nombre_fiscal
            if not nombre_fiscal and nombre_comercial:
                nombre_fiscal = nombre_comercial

            cliente_nombre_interno = _extract_cliente_value(row, idx, "cliente_nombre_interno")
            cliente_abreviatura = _extract_cliente_value(row, idx, "cliente_abreviatura") or _extract_cliente_value(row, idx, "abreviatura")
            cliente_cif = _extract_cliente_value(row, idx, "cliente_cif")
            cliente_telefono = _extract_cliente_value(row, idx, "cliente_telefono") or _extract_cliente_value(row, idx, "telefono")
            cliente_email = _extract_cliente_value(row, idx, "cliente_email") or _extract_cliente_value(row, idx, "email")
            cliente_direccion = _extract_cliente_value(row, idx, "cliente_direccion") or _extract_cliente_value(row, idx, "direccion")
            cliente_direccion_cp = _extract_cliente_value(row, idx, "cliente_direccion_cp")
            cliente_direccion_localidad_id = _extract_cliente_value(row, idx, "cliente_direccion_localidad_id")
            cliente_direccion_municipio_id = _extract_cliente_value(row, idx, "cliente_direccion_municipio_id")
            cliente_direccion_provincia_id = _extract_cliente_value(row, idx, "cliente_direccion_provincia_id")
            cliente_direccion_isla_id = _extract_cliente_value(row, idx, "cliente_direccion_isla_id")
            cliente_tipo = _extract_cliente_value(row, idx, "cliente_tipo")
            cliente_actividad = _extract_cliente_value(row, idx, "cliente_actividad") or _extract_cliente_value(row, idx, "cliente_grupo")
            raw_prospeccion = _extract_cliente_value(row, idx, "cliente_prospeccion")
            cliente_prospeccion = 0 if raw_prospeccion.lower() in {"", "0", "false", "no", "n"} else 1
            distribuidor_id = _extract_cliente_value(row, idx, "distribuidor_id")

            raw_activo = _extract_cliente_value(row, idx, "activo")
            activo = 0 if raw_activo.lower() in {"0", "false", "no", "n", ""} else 1
            raw_code = (
                _extract_cliente_value(row, idx, "cliente_codigo")
                or _extract_cliente_value(row, idx, "codigo_cliente")
                or _extract_cliente_value(row, idx, "codigo")
            )
            code = 0
            try:
                code = int(raw_code)
            except Exception:
                code = 0
            if code <= 0 or code in used_codes:
                code = 0
            else:
                used_codes.add(code)
                max_code = max(max_code, code)

            prepared.append(
                (
                    cliente_id,
                    code,
                    nombre_comercial,
                    nombre_fiscal,
                    cliente_nombre_interno,
                    cliente_abreviatura,
                    cliente_cif,
                    cliente_telefono,
                    cliente_email,
                    cliente_direccion,
                    cliente_direccion_cp,
                    cliente_direccion_localidad_id,
                    cliente_direccion_municipio_id,
                    cliente_direccion_provincia_id,
                    cliente_direccion_isla_id,
                    cliente_tipo,
                    cliente_actividad,
                    cliente_prospeccion,
                    distribuidor_id,
                    activo,
                )
            )

        normalized: list[tuple] = []
        for item in prepared:
            code = int(item[1] or 0)
            if code <= 0:
                max_code += 1
                code = max_code
            normalized.append((item[0], code, *item[2:]))
        prepared = normalized

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("ALTER TABLE clientes RENAME TO clientes_old_schema")
        conn.exec_driver_sql(
            """
            CREATE TABLE clientes (
                cliente_id TEXT PRIMARY KEY NOT NULL,
                cliente_codigo INTEGER NOT NULL UNIQUE,
                cliente_nombre_comercial TEXT NOT NULL DEFAULT '',
                cliente_nombre_fiscal TEXT NOT NULL DEFAULT '',
                cliente_nombre_interno TEXT NOT NULL DEFAULT '',
                cliente_abreviatura TEXT NOT NULL DEFAULT '',
                cliente_cif TEXT NOT NULL DEFAULT '',
                cliente_telefono TEXT NOT NULL DEFAULT '',
                cliente_email TEXT NOT NULL DEFAULT '',
                cliente_direccion TEXT NOT NULL DEFAULT '',
                cliente_direccion_cp TEXT NOT NULL DEFAULT '',
                cliente_direccion_localidad_id TEXT NOT NULL DEFAULT '',
                cliente_direccion_municipio_id TEXT NOT NULL DEFAULT '',
                cliente_direccion_provincia_id TEXT NOT NULL DEFAULT '',
                cliente_direccion_isla_id TEXT NOT NULL DEFAULT '',
                cliente_tipo TEXT NOT NULL DEFAULT '',
                cliente_actividad TEXT NOT NULL DEFAULT '',
                cliente_prospeccion BOOLEAN NOT NULL DEFAULT 0,
                distribuidor_id TEXT NOT NULL DEFAULT '',
                activo BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )
        for item in prepared:
            conn.exec_driver_sql(
                """
                INSERT INTO clientes (
                    cliente_id, cliente_codigo, cliente_nombre_comercial, cliente_nombre_fiscal, cliente_nombre_interno, cliente_abreviatura,
                    cliente_cif, cliente_telefono, cliente_email, cliente_direccion, cliente_direccion_cp,
                    cliente_direccion_localidad_id, cliente_direccion_municipio_id, cliente_direccion_provincia_id,
                    cliente_direccion_isla_id, cliente_tipo, cliente_actividad, cliente_prospeccion, distribuidor_id, activo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                item,
            )
        conn.exec_driver_sql("DROP TABLE clientes_old_schema")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _migrate_contact_columns() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "contactos" not in tables:
            return

        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(contactos)").fetchall()]
        if "cliente_id" not in columns and "empresa_id" in columns:
            conn.exec_driver_sql("ALTER TABLE contactos RENAME COLUMN empresa_id TO cliente_id")
            columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(contactos)").fetchall()]
        if "cliente_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE contactos ADD COLUMN cliente_id TEXT")
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(contactos)").fetchall()]
        if "nombre" not in columns:
            conn.exec_driver_sql("ALTER TABLE contactos ADD COLUMN nombre TEXT DEFAULT ''")
        if "apellidos" not in columns:
            conn.exec_driver_sql("ALTER TABLE contactos ADD COLUMN apellidos TEXT DEFAULT ''")
        if "cargo" not in columns:
            conn.exec_driver_sql("ALTER TABLE contactos ADD COLUMN cargo TEXT DEFAULT ''")
        if "nif" not in columns:
            conn.exec_driver_sql("ALTER TABLE contactos ADD COLUMN nif TEXT DEFAULT ''")
        if "telefono" not in columns:
            conn.exec_driver_sql("ALTER TABLE contactos ADD COLUMN telefono TEXT DEFAULT ''")
        if "email" not in columns:
            conn.exec_driver_sql("ALTER TABLE contactos ADD COLUMN email TEXT DEFAULT ''")
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(contactos)").fetchall()]
        if "contacto_codigo" not in columns:
            conn.exec_driver_sql("ALTER TABLE contactos ADD COLUMN contacto_codigo INTEGER DEFAULT 0")
            columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(contactos)").fetchall()]
        if "contacto_codigo" in columns:
            max_code_row = conn.exec_driver_sql(
                "SELECT COALESCE(MAX(contacto_codigo), 0) FROM contactos WHERE contacto_codigo IS NOT NULL AND contacto_codigo > 0"
            ).fetchone()
            max_code = int(max_code_row[0] if max_code_row else 0)
            rows = conn.exec_driver_sql(
                "SELECT contacto_id FROM contactos WHERE contacto_codigo IS NULL OR contacto_codigo = 0 ORDER BY contacto_id"
            ).fetchall()
            for row in rows:
                max_code += 1
                conn.exec_driver_sql(
                    "UPDATE contactos SET contacto_codigo = ? WHERE contacto_id = ?",
                    (max_code, row[0]),
                )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_contactos_contacto_codigo ON contactos (contacto_codigo)"
            )
            conn.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS trg_contactos_codigo_autogen
                AFTER INSERT ON contactos
                FOR EACH ROW
                WHEN NEW.contacto_codigo IS NULL OR NEW.contacto_codigo = 0
                BEGIN
                    UPDATE contactos
                    SET contacto_codigo = (
                        SELECT COALESCE(MAX(contacto_codigo), 0) + 1
                        FROM contactos
                        WHERE contacto_id <> NEW.contacto_id
                    )
                    WHERE contacto_id = NEW.contacto_id;
                END;
                """
            )


def _migrate_contactos_cliente_fk() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "contactos" not in tables or "clientes" not in tables:
            return
        foreign_keys = conn.exec_driver_sql("PRAGMA foreign_key_list(contactos)").fetchall()
        if not any(row[2] == "clientes_old_schema" for row in foreign_keys):
            return

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("DROP TRIGGER IF EXISTS trg_contactos_codigo_autogen")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ux_contactos_contacto_codigo")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_contactos_contacto_codigo")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_contactos_cliente_id")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_contactos_nombre")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_contactos_apellidos")
        conn.exec_driver_sql("ALTER TABLE contactos RENAME TO contactos_old_schema")
        conn.exec_driver_sql(
            """
            CREATE TABLE contactos (
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                contacto_id VARCHAR(36) NOT NULL,
                contacto_codigo INTEGER NOT NULL,
                cliente_id VARCHAR(36) NOT NULL,
                nombre VARCHAR(255) NOT NULL,
                apellidos VARCHAR(255) NOT NULL,
                cargo VARCHAR(255) NOT NULL,
                nif VARCHAR(50) NOT NULL,
                telefono VARCHAR(50) NOT NULL,
                email VARCHAR(255) NOT NULL,
                PRIMARY KEY (contacto_id),
                FOREIGN KEY(cliente_id) REFERENCES clientes (cliente_id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO contactos (
                created_at, updated_at, contacto_id, contacto_codigo, cliente_id,
                nombre, apellidos, cargo, nif, telefono, email
            )
            SELECT
                COALESCE(created_at, CURRENT_TIMESTAMP),
                COALESCE(updated_at, CURRENT_TIMESTAMP),
                contacto_id,
                contacto_codigo,
                cliente_id,
                COALESCE(nombre, ''),
                COALESCE(apellidos, ''),
                COALESCE(cargo, ''),
                COALESCE(nif, ''),
                COALESCE(telefono, ''),
                COALESCE(email, '')
            FROM contactos_old_schema
            """
        )
        conn.exec_driver_sql("DROP TABLE contactos_old_schema")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_contactos_contacto_codigo ON contactos (contacto_codigo)")
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_contactos_codigo_autogen
            AFTER INSERT ON contactos
            FOR EACH ROW
            WHEN NEW.contacto_codigo IS NULL OR NEW.contacto_codigo = 0
            BEGIN
                UPDATE contactos
                SET contacto_codigo = (
                    SELECT COALESCE(MAX(contacto_codigo), 0) + 1
                    FROM contactos
                    WHERE contacto_id <> NEW.contacto_id
                )
                WHERE contacto_id = NEW.contacto_id;
            END;
            """
        )
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _ensure_indexes() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "almacenes_catalogo" in tables:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_almacenes_catalogo_nombre ON almacenes_catalogo (almacen_nombre)")
        if "almacen_movimientos" in tables:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_almacen_movimientos_almacen_id ON almacen_movimientos (almacen_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_almacen_movimientos_articulo_id ON almacen_movimientos (articulo_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_almacen_movimientos_pedido_numero ON almacen_movimientos (pedido_numero)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_almacen_movimientos_pedido_albaran ON almacen_movimientos (pedido_albaran_numero)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_almacen_movimientos_lote ON almacen_movimientos (articulo_lote)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_almacen_movimientos_caducidad ON almacen_movimientos (articulo_caducidad)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_almacen_movimientos_fecha_pedido ON almacen_movimientos (fecha_pedido)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_almacen_movimientos_albaran_item_id ON almacen_movimientos (albaran_item_id)"
            )
        if "almacen_stock" in tables:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_almacen_stock_almacen_id ON almacen_stock (almacen_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_almacen_stock_articulo_id ON almacen_stock (articulo_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_fabricantes_codigo ON fabricantes (fabricante_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_fabricantes_nombre ON fabricantes (fabricante_nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_familias_fabricante_id ON familias (fabricante_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_familias_codigo ON familias (articulo_familia_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_familias_nombre ON familias (articulo_familia_nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_subfamilias_familia_id ON subfamilias (articulo_familia_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_subfamilias_codigo ON subfamilias (articulo_subfamilia_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_subfamilias_nombre ON subfamilias (articulo_subfamilia_nombre)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_clientes_cliente_codigo ON clientes (cliente_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_clientes_cliente_codigo ON clientes (cliente_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_clientes_nombre_comercial ON clientes (cliente_nombre_comercial)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_clientes_nombre_fiscal ON clientes (cliente_nombre_fiscal)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_contactos_cliente_id ON contactos (cliente_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_contactos_nombre ON contactos (nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_contactos_apellidos ON contactos (apellidos)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_provincias_codigo ON provincias (provincia_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_provincias_nombre ON provincias (provincia_nombre)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_islas_codigo ON islas (isla_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_islas_nombre ON islas (isla_nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_islas_provincia_id ON islas (provincia_id)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_municipios_codigo ON municipios (municipio_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_municipios_nombre ON municipios (municipio_nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_municipios_isla_id ON municipios (isla_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_municipios_provincia_id ON municipios (provincia_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_codigos_postales_codigo ON codigos_postales (codigo_postal)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_localidades_nombre ON localidades (localidad_nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_localidades_municipio_id ON localidades (municipio_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_localidades_codigo_postal ON localidades (codigo_postal)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_cursos_curso_fecha ON cursos (curso_fecha)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_cursos_curso_nombre ON cursos (curso_nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_recetas_cliente_id ON recetas (cliente_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_recetas_codigo_receta ON recetas (codigo_receta)")
        if "receta_lineas" in tables:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_receta_lineas_proceso_nombre ON receta_lineas (proceso_nombre)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_receta_lineas_tipo_linea ON receta_lineas (tipo_linea)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_receta_lineas_proceso_origen_nombre ON receta_lineas (proceso_origen_nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_asistentes_curso_id ON asistentes (curso_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_asistentes_contacto_id ON asistentes (contacto_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_asistentes_cliente_id ON asistentes (cliente_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_asistentes_status_confirmacion ON asistentes (status_confirmacion)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_tecnicos_nombre ON tecnicos (nombre)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_tecnicos_apellidos ON tecnicos (apellidos)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_tecnicos_codigo ON tecnicos (tecnico_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_cursos_tecnicos_curso_id ON cursos_tecnicos (curso_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_cursos_tecnicos_tecnico_id ON cursos_tecnicos (tecnico_id)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_productos_ireks_articulo_id ON productos_ireks (articulo_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_productos_ireks_referencia ON productos_ireks (articulo_referencia)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_productos_ireks_descripcion ON productos_ireks (articulo_descripcion)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_materias_primas_proveedor_id ON materias_primas (proveedor_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_materias_primas_distribuidor_id ON materias_primas (distribuidor_id)")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_materias_primas_referencia ON materias_primas (articulo_referencia_distribuidor)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_materias_primas_descripcion ON materias_primas (articulo_descripcion)"
        )
        if "materias_primas_precios" in tables:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_materias_primas_precios_articulo_id ON materias_primas_precios (articulo_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_materias_primas_precios_fecha ON materias_primas_precios (fecha_precio)"
            )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_materias_primas_precios_articulo_fecha ON materias_primas_precios (articulo_id, fecha_precio)"
            )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_referencias_distribuidor_articulo_id ON referencias_distribuidor (articulo_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_referencias_distribuidor_distribuidor_id ON referencias_distribuidor (distribuidor_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_referencias_distribuidor_referencia ON referencias_distribuidor (articulo_referencia_distribuidor)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_referencias_distribuidor_descripcion ON referencias_distribuidor (articulo_descripcion_distribuidor)"
        )
        if "ventas_import_lotes" in tables:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_ventas_import_lotes_periodo ON ventas_import_lotes (periodo)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_ventas_import_lotes_hash ON ventas_import_lotes (archivo_hash)")
        if "ventas_mensuales_raw" in tables:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_ventas_mensuales_raw_periodo ON ventas_mensuales_raw (periodo)")
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_ventas_mensuales_raw_articulo_id ON ventas_mensuales_raw (articulo_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_ventas_mensuales_raw_codigo ON ventas_mensuales_raw (articulo_codigo_origen)"
            )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_almacen_id ON pedidos (almacen_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_fecha ON pedidos (pedido_fecha)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_numero ON pedidos (pedido_numero)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_albaran ON pedidos (pedido_albaran_numero)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_factura ON pedidos (pedido_factura_numero)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_ref ON pedidos (pedido_ref)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_items_pedido_id ON pedidos_items (pedido_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_items_numero ON pedidos_items (pedido_numero)")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_pedidos_items_albaran ON pedidos_items (pedido_albaran_numero)"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_items_fecha ON pedidos_items (pedido_item_fecha)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_items_articulo_id ON pedidos_items (articulo_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_almacen_id ON albaranes (almacen_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_pedido_id ON albaranes (pedido_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_numero ON albaranes (albaran_numero)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_fecha ON albaranes (albaran_fecha)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_pedido_id ON albaranes_items (pedido_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_albaran_id ON albaranes_items (albaran_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_numero ON albaranes_items (albaran_numero)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_fecha ON albaranes_items (albaran_fecha)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_codigo ON albaranes_items (articulo_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_articulo_id ON albaranes_items (articulo_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_cantidad ON albaranes_items (articulo_cantidad)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_lote ON albaranes_items (articulo_lote)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_albaranes_items_caducidad ON albaranes_items (articulo_caducidad)")
        if "facturas" in tables:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_almacen_id ON facturas (almacen_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_pedido_id ON facturas (pedido_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_numero ON facturas (factura_numero)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_fecha ON facturas (factura_fecha)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_albaran ON facturas (albaran_numero)")
        if "facturas_items" in tables:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_pedido_id ON facturas_items (pedido_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_factura_id ON facturas_items (factura_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_numero ON facturas_items (factura_numero)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_fecha ON facturas_items (factura_fecha)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_albaran ON facturas_items (albaran_numero)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_codigo ON facturas_items (articulo_codigo)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_articulo_id ON facturas_items (articulo_id)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_lote ON facturas_items (articulo_lote)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_facturas_items_caducidad ON facturas_items (articulo_caducidad)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_pendientes_pedido_id ON pedidos_pendientes (pedido_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_pendientes_albaran_id ON pedidos_pendientes (albaran_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_pendientes_articulo_id ON pedidos_pendientes (articulo_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_pendientes_estado ON pedidos_pendientes (estado)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_pedidos_pendientes_fecha ON pedidos_pendientes (fecha_registro)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_distribuidores_codigo ON distribuidores (distribuidor_codigo)")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_distribuidores_nombre_comercial ON distribuidores (distribuidor_nombre_comercial)"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_proveedores_codigo ON proveedores (proveedor_codigo)")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_proveedores_nombre_comercial ON proveedores (proveedor_nombre_comercial)"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_envases_codigo ON envases (envase_codigo)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_envases_nombre ON envases (envase_nombre)")


def _migrate_asistentes_columns() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "asistentes" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(asistentes)").fetchall()]
        if "status_confirmacion" not in columns:
            conn.exec_driver_sql("ALTER TABLE asistentes ADD COLUMN status_confirmacion BOOLEAN NOT NULL DEFAULT 0")


def _migrate_asistentes_fks() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if not {"asistentes", "cursos", "contactos", "clientes"}.issubset(tables):
            return
        foreign_keys = conn.exec_driver_sql("PRAGMA foreign_key_list(asistentes)").fetchall()
        if not any(str(row[2]).endswith("_old_schema") for row in foreign_keys):
            return

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_asistentes_curso_id")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_asistentes_contacto_id")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_asistentes_cliente_id")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_asistentes_status_confirmacion")
        conn.exec_driver_sql("ALTER TABLE asistentes RENAME TO asistentes_old_schema")
        conn.exec_driver_sql(
            """
            CREATE TABLE asistentes (
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                curso_id VARCHAR(36) NOT NULL,
                contacto_id VARCHAR(36) NOT NULL,
                cliente_id VARCHAR(36) NOT NULL,
                observaciones VARCHAR NOT NULL,
                status_confirmacion BOOLEAN NOT NULL DEFAULT 0,
                PRIMARY KEY (curso_id, contacto_id),
                FOREIGN KEY(curso_id) REFERENCES cursos (curso_id),
                FOREIGN KEY(contacto_id) REFERENCES contactos (contacto_id),
                FOREIGN KEY(cliente_id) REFERENCES clientes (cliente_id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO asistentes (
                created_at, updated_at, curso_id, contacto_id, cliente_id,
                observaciones, status_confirmacion
            )
            SELECT
                COALESCE(created_at, CURRENT_TIMESTAMP),
                COALESCE(updated_at, CURRENT_TIMESTAMP),
                curso_id,
                contacto_id,
                cliente_id,
                COALESCE(observaciones, ''),
                COALESCE(status_confirmacion, 0)
            FROM asistentes_old_schema
            """
        )
        conn.exec_driver_sql("DROP TABLE asistentes_old_schema")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _migrate_tecnicos_columns() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "tecnicos" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(tecnicos)").fetchall()]
        if "tecnico_codigo" not in columns:
            conn.exec_driver_sql("ALTER TABLE tecnicos ADD COLUMN tecnico_codigo INTEGER DEFAULT 0")
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(tecnicos)").fetchall()]
        for field in ("nombre", "apellidos", "movil", "interno", "email"):
            if field not in columns:
                conn.exec_driver_sql(f"ALTER TABLE tecnicos ADD COLUMN {field} TEXT DEFAULT ''")
        max_code_row = conn.exec_driver_sql(
            "SELECT COALESCE(MAX(tecnico_codigo), 0) FROM tecnicos WHERE tecnico_codigo IS NOT NULL AND tecnico_codigo > 0"
        ).fetchone()
        max_code = int(max_code_row[0] if max_code_row else 0)
        rows = conn.exec_driver_sql(
            "SELECT tecnico_id FROM tecnicos WHERE tecnico_codigo IS NULL OR tecnico_codigo = 0 ORDER BY tecnico_id"
        ).fetchall()
        for row in rows:
            max_code += 1
            conn.exec_driver_sql("UPDATE tecnicos SET tecnico_codigo = ? WHERE tecnico_id = ?", (max_code, row[0]))
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_tecnicos_codigo ON tecnicos (tecnico_codigo)")


def _migrate_ingredientes_std_columns() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "materias_primas" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(materias_primas)").fetchall()]
        if "proveedor_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE materias_primas ADD COLUMN proveedor_id TEXT NOT NULL DEFAULT ''")
        if "distribuidor_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE materias_primas ADD COLUMN distribuidor_id TEXT NOT NULL DEFAULT ''")
        conn.exec_driver_sql(
            """
            UPDATE materias_primas
            SET proveedor_id = TRIM(COALESCE(distribuidor_id, ''))
            WHERE TRIM(COALESCE(proveedor_id, '')) = '' AND TRIM(COALESCE(distribuidor_id, '')) <> ''
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE materias_primas
            SET distribuidor_id = TRIM(COALESCE(proveedor_id, ''))
            WHERE TRIM(COALESCE(distribuidor_id, '')) = '' AND TRIM(COALESCE(proveedor_id, '')) <> ''
            """
        )
        new_columns = {
            "categoria": "TEXT NOT NULL DEFAULT ''",
            "formato": "TEXT NOT NULL DEFAULT ''",
            "formato_cantidad": "REAL NOT NULL DEFAULT 0",
            "formato_unidad": "TEXT NOT NULL DEFAULT 'kg'",
            "pvp_formato": "REAL NOT NULL DEFAULT 0",
            "pvp_unidad_medida": "REAL NOT NULL DEFAULT 0",
        }
        for column, ddl in new_columns.items():
            if column not in columns:
                conn.exec_driver_sql(f"ALTER TABLE materias_primas ADD COLUMN {column} {ddl}")


def _migrate_recetas_cliente_fk() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "recetas" not in tables:
            return
        foreign_keys = conn.exec_driver_sql("PRAGMA foreign_key_list(recetas)").fetchall()
        if not any(row[2] == "clientes_old_schema" for row in foreign_keys):
            return

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("ALTER TABLE recetas RENAME TO recetas_old_schema")
        conn.exec_driver_sql(
            """
            CREATE TABLE recetas (
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                id INTEGER NOT NULL,
                cliente_id VARCHAR(36) NOT NULL,
                nombre VARCHAR(255) NOT NULL,
                codigo_receta VARCHAR(100) NOT NULL,
                version VARCHAR(20) NOT NULL,
                es_base BOOLEAN NOT NULL,
                receta_base_id INTEGER,
                masa_final_deseada_g FLOAT NOT NULL,
                peso_pieza_g FLOAT NOT NULL,
                numero_piezas INTEGER NOT NULL,
                total_harinas_g FLOAT NOT NULL,
                total_liquidos_g FLOAT NOT NULL,
                hidratacion_pct FLOAT NOT NULL,
                total_porcentaje_panadero FLOAT NOT NULL,
                masa_total_g FLOAT NOT NULL,
                coste_total FLOAT NOT NULL,
                coste_kg FLOAT NOT NULL,
                coste_pieza FLOAT NOT NULL,
                merma_pct FLOAT NOT NULL,
                observaciones VARCHAR NOT NULL,
                proceso VARCHAR NOT NULL,
                estado VARCHAR(30) NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(cliente_id) REFERENCES clientes (cliente_id),
                FOREIGN KEY(receta_base_id) REFERENCES recetas (id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO recetas (
                created_at, updated_at, id, cliente_id, nombre, codigo_receta, version, es_base,
                receta_base_id, masa_final_deseada_g, peso_pieza_g, numero_piezas,
                total_harinas_g, total_liquidos_g, hidratacion_pct, total_porcentaje_panadero,
                masa_total_g, coste_total, coste_kg, coste_pieza, merma_pct,
                observaciones, proceso, estado
            )
            SELECT
                created_at, updated_at, id, cliente_id, nombre, codigo_receta, version, es_base,
                receta_base_id, masa_final_deseada_g, peso_pieza_g, numero_piezas,
                total_harinas_g, total_liquidos_g, hidratacion_pct, total_porcentaje_panadero,
                masa_total_g, coste_total, coste_kg, coste_pieza, merma_pct,
                observaciones, proceso, estado
            FROM recetas_old_schema
            """
        )
        conn.exec_driver_sql("DROP TABLE recetas_old_schema")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _migrate_receta_child_fks() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "recetas" not in tables:
            return

        def has_old_fk(table: str) -> bool:
            if table not in tables:
                return False
            return any(row[2] == "recetas_old_schema" for row in conn.exec_driver_sql(f"PRAGMA foreign_key_list({table})").fetchall())

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")

        if has_old_fk("receta_lineas"):
            conn.exec_driver_sql("ALTER TABLE receta_lineas RENAME TO receta_lineas_old_schema")
            conn.exec_driver_sql(
                """
                CREATE TABLE receta_lineas (
                    id INTEGER NOT NULL,
                    receta_id INTEGER NOT NULL,
                    orden INTEGER NOT NULL,
                    tipo_origen VARCHAR(20) NOT NULL,
                    ingrediente_id INTEGER,
                    nombre_mostrado VARCHAR(255) NOT NULL,
                    codigo_ingrediente VARCHAR(100) NOT NULL,
                    familia VARCHAR(100) NOT NULL,
                    subfamilia VARCHAR(100) NOT NULL,
                    es_harina BOOLEAN NOT NULL,
                    es_liquido BOOLEAN NOT NULL,
                    cantidad_base_g FLOAT NOT NULL,
                    porcentaje_panadero FLOAT NOT NULL,
                    cantidad_calculada_g FLOAT NOT NULL,
                    precio_kg_snapshot FLOAT NOT NULL,
                    coste_linea FLOAT NOT NULL,
                    tipo_linea VARCHAR(20) NOT NULL DEFAULT 'ingrediente',
                    proceso_nombre VARCHAR(120) NOT NULL DEFAULT 'Masa final',
                    proceso_origen_nombre VARCHAR(120) NOT NULL DEFAULT '',
                    cantidad_origen_g FLOAT NOT NULL DEFAULT 0,
                    es_subreceta BOOLEAN NOT NULL,
                    subreceta_id INTEGER,
                    notas VARCHAR NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(receta_id) REFERENCES recetas (id),
                    FOREIGN KEY(subreceta_id) REFERENCES recetas (id)
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO receta_lineas (
                    id, receta_id, orden, tipo_origen, ingrediente_id, nombre_mostrado,
                    codigo_ingrediente, familia, subfamilia, es_harina, es_liquido,
                    cantidad_base_g, porcentaje_panadero, cantidad_calculada_g,
                    precio_kg_snapshot, coste_linea, tipo_linea, proceso_nombre, proceso_origen_nombre, cantidad_origen_g,
                    es_subreceta, subreceta_id, notas
                )
                SELECT
                    id, receta_id, orden, tipo_origen, ingrediente_id, nombre_mostrado,
                    codigo_ingrediente, familia, subfamilia, es_harina, es_liquido,
                    cantidad_base_g, porcentaje_panadero, cantidad_calculada_g,
                    precio_kg_snapshot, coste_linea, 'ingrediente', 'Masa final', '', 0, es_subreceta, subreceta_id, notas
                FROM receta_lineas_old_schema
                """
            )
            conn.exec_driver_sql("DROP TABLE receta_lineas_old_schema")

        if has_old_fk("receta_versiones"):
            conn.exec_driver_sql("ALTER TABLE receta_versiones RENAME TO receta_versiones_old_schema")
            conn.exec_driver_sql(
                """
                CREATE TABLE receta_versiones (
                    id INTEGER NOT NULL,
                    receta_id INTEGER NOT NULL,
                    version VARCHAR(20) NOT NULL,
                    snapshot_json VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    comentario VARCHAR NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(receta_id) REFERENCES recetas (id)
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO receta_versiones (id, receta_id, version, snapshot_json, created_at, comentario)
                SELECT id, receta_id, version, snapshot_json, created_at, comentario
                FROM receta_versiones_old_schema
                """
            )
            conn.exec_driver_sql("DROP TABLE receta_versiones_old_schema")

        if has_old_fk("escandallos"):
            conn.exec_driver_sql("ALTER TABLE escandallos RENAME TO escandallos_old_schema")
            conn.exec_driver_sql(
                """
                CREATE TABLE escandallos (
                    id INTEGER NOT NULL,
                    receta_id INTEGER NOT NULL,
                    fecha_calculo DATETIME NOT NULL,
                    masa_total_g FLOAT NOT NULL,
                    coste_total FLOAT NOT NULL,
                    coste_kg FLOAT NOT NULL,
                    coste_pieza FLOAT NOT NULL,
                    detalle_json VARCHAR NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(receta_id) REFERENCES recetas (id)
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO escandallos (
                    id, receta_id, fecha_calculo, masa_total_g, coste_total,
                    coste_kg, coste_pieza, detalle_json
                )
                SELECT
                    id, receta_id, fecha_calculo, masa_total_g, coste_total,
                    coste_kg, coste_pieza, detalle_json
                FROM escandallos_old_schema
                """
            )
            conn.exec_driver_sql("DROP TABLE escandallos_old_schema")

        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _migrate_recetas_technical_fields() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "recetas" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(recetas)").fetchall()]
        if "escandallo_detalle_json" not in columns:
            conn.exec_driver_sql("ALTER TABLE recetas ADD COLUMN escandallo_detalle_json TEXT NOT NULL DEFAULT ''")
        if "parametros_elaboracion_json" not in columns:
            conn.exec_driver_sql("ALTER TABLE recetas ADD COLUMN parametros_elaboracion_json TEXT NOT NULL DEFAULT ''")


def _migrate_receta_lineas_process_fields() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "receta_lineas" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(receta_lineas)").fetchall()]
        if "proceso_nombre" not in columns:
            conn.exec_driver_sql("ALTER TABLE receta_lineas ADD COLUMN proceso_nombre TEXT NOT NULL DEFAULT 'Masa final'")
        if "tipo_linea" not in columns:
            conn.exec_driver_sql("ALTER TABLE receta_lineas ADD COLUMN tipo_linea TEXT NOT NULL DEFAULT 'ingrediente'")
        if "proceso_origen_nombre" not in columns:
            conn.exec_driver_sql("ALTER TABLE receta_lineas ADD COLUMN proceso_origen_nombre TEXT NOT NULL DEFAULT ''")
        if "cantidad_origen_g" not in columns:
            conn.exec_driver_sql("ALTER TABLE receta_lineas ADD COLUMN cantidad_origen_g FLOAT NOT NULL DEFAULT 0")
        conn.exec_driver_sql(
            """
            UPDATE receta_lineas
            SET proceso_nombre = 'Masa final'
            WHERE TRIM(COALESCE(proceso_nombre, '')) = ''
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE receta_lineas
            SET tipo_linea = 'ingrediente'
            WHERE TRIM(COALESCE(tipo_linea, '')) = ''
            """
        )


def _migrate_ingredientes_std_to_materias_primas() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "ingredientes_std" not in tables or "materias_primas" not in tables:
            return
        current_count_row = conn.exec_driver_sql("SELECT COUNT(*) FROM materias_primas").fetchone()
        current_count = int(current_count_row[0] if current_count_row else 0)
        if current_count > 0:
            return
        rows = conn.exec_driver_sql(
            """
            SELECT
                TRIM(COALESCE(codigo, '')),
                TRIM(COALESCE(nombre, '')),
                TRIM(COALESCE(familia, '')),
                TRIM(COALESCE(subfamilia, '')),
                TRIM(COALESCE(distribuidor_id, ''))
            FROM ingredientes_std
            WHERE TRIM(COALESCE(nombre, '')) <> ''
            """
        ).fetchall()
        for codigo, nombre, familia, subfamilia, distribuidor_id in rows:
            conn.exec_driver_sql(
                """
                INSERT INTO materias_primas (
                    articulo_id,
                    articulo_referencia_distribuidor,
                    proveedor_id,
                    distribuidor_id,
                    articulo_descripcion,
                    articulo_grupo_id,
                    articulo_familia_id,
                    articulo_subfamilia_id,
                    activo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (str(uuid4()), codigo, distribuidor_id, distribuidor_id, nombre, familia, familia, subfamilia),
            )


def _ensure_distribuidores_autogen() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "distribuidores" not in tables:
            return
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_distribuidores_codigo_autogen
            AFTER INSERT ON distribuidores
            FOR EACH ROW
            WHEN NEW.distribuidor_codigo IS NULL OR NEW.distribuidor_codigo = 0
            BEGIN
                UPDATE distribuidores
                SET distribuidor_codigo = (
                    SELECT COALESCE(MAX(distribuidor_codigo), 0) + 1
                    FROM distribuidores
                    WHERE distribuidor_id <> NEW.distribuidor_id
                )
                WHERE distribuidor_id = NEW.distribuidor_id;
            END;
            """
        )


def _ensure_tecnicos_autogen() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "tecnicos" not in tables:
            return
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_tecnicos_codigo_autogen
            AFTER INSERT ON tecnicos
            FOR EACH ROW
            WHEN NEW.tecnico_codigo IS NULL OR NEW.tecnico_codigo = 0
            BEGIN
                UPDATE tecnicos
                SET tecnico_codigo = (
                    SELECT COALESCE(MAX(tecnico_codigo), 0) + 1
                    FROM tecnicos
                    WHERE tecnico_id <> NEW.tecnico_id
                )
                WHERE tecnico_id = NEW.tecnico_id;
            END;
            """
        )


def _ensure_envases_autogen() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "envases" not in tables:
            return
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_envases_codigo_autogen
            AFTER INSERT ON envases
            FOR EACH ROW
            WHEN NEW.envase_codigo IS NULL OR NEW.envase_codigo = 0
            BEGIN
                UPDATE envases
                SET envase_codigo = (
                    SELECT COALESCE(MAX(envase_codigo), 0) + 1
                    FROM envases
                    WHERE envase_id <> NEW.envase_id
                )
                WHERE envase_id = NEW.envase_id;
            END;
            """
        )


def _ensure_ventas_total_kg() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "ventas" not in tables:
            return
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_ventas_total_kg_insert
            AFTER INSERT ON ventas
            FOR EACH ROW
            BEGIN
                UPDATE ventas
                SET total_kg = COALESCE(NEW.venta_kilos, 0) * COALESCE(NEW.venta_kilos_SC, 0)
                WHERE venta_id = NEW.venta_id;
            END;
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_ventas_total_kg_update
            AFTER UPDATE OF venta_kilos, venta_kilos_SC ON ventas
            FOR EACH ROW
            BEGIN
                UPDATE ventas
                SET total_kg = COALESCE(NEW.venta_kilos, 0) * COALESCE(NEW.venta_kilos_SC, 0)
                WHERE venta_id = NEW.venta_id;
            END;
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE ventas
            SET total_kg = COALESCE(venta_kilos, 0) * COALESCE(venta_kilos_SC, 0)
            WHERE COALESCE(total_kg, -1) <> (COALESCE(venta_kilos, 0) * COALESCE(venta_kilos_SC, 0))
            """
        )


def _ensure_proveedores_autogen() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "proveedores" not in tables:
            return
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_proveedores_codigo_autogen
            AFTER INSERT ON proveedores
            FOR EACH ROW
            WHEN NEW.proveedor_codigo IS NULL OR NEW.proveedor_codigo = 0
            BEGIN
                UPDATE proveedores
                SET proveedor_codigo = (
                    SELECT COALESCE(MAX(proveedor_codigo), 0) + 1
                    FROM proveedores
                    WHERE proveedor_id <> NEW.proveedor_id
                )
                WHERE proveedor_id = NEW.proveedor_id;
            END;
            """
        )


def _migrate_sales_tables() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table in (
            "ventas",
            "ventas_mensuales_consolidadas",
            "ventas_conciliacion_ajustes",
            "ventas_incidencias",
            "ventas_mes_cierres",
        ):
            if table in tables:
                conn.exec_driver_sql(f"DROP TABLE {table}")

        if "ventas_import_lotes" in tables:
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(ventas_import_lotes)").fetchall()}
            expected = {"lote_id", "fuente", "cliente_id", "periodo", "archivo_nombre", "archivo_hash", "estado", "creado_en"}
            if not expected.issubset(columns) or "distribuidor_id" in columns:
                conn.exec_driver_sql("DROP TABLE ventas_import_lotes")

        if "ventas_mensuales_raw" in tables:
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(ventas_mensuales_raw)").fetchall()}
            expected = {
                "raw_id",
                "lote_id",
                "fuente",
                "cliente_id",
                "periodo",
                "articulo_codigo_origen",
                "articulo_id",
                "articulo_descripcion_origen",
                "venta_kilos",
                "venta_kilos_sc",
                "venta_euros",
                "payload_json",
            }
            legacy = {"tipo_dist", "distribuidor_id", "unidades", "peso_envase_kg", "kg", "euros", "incidencia"}
            if not expected.issubset(columns) or columns.intersection(legacy):
                conn.exec_driver_sql("DROP TABLE ventas_mensuales_raw")


def _ensure_pedidos_items_sync() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "pedidos_items" not in tables or "pedidos" not in tables:
            return
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_pedidos_items_sync_insert
            AFTER INSERT ON pedidos_items
            FOR EACH ROW
            BEGIN
                UPDATE pedidos_items
                SET
                    pedido_numero = COALESCE((SELECT pedido_numero FROM pedidos WHERE pedido_id = NEW.pedido_id), ''),
                    pedido_albaran_numero = COALESCE((SELECT pedido_albaran_numero FROM pedidos WHERE pedido_id = NEW.pedido_id), ''),
                    pedido_item_fecha = COALESCE((SELECT pedido_fecha FROM pedidos WHERE pedido_id = NEW.pedido_id), NEW.pedido_item_fecha)
                WHERE item_id = NEW.item_id;
            END;
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_pedidos_items_sync_update
            AFTER UPDATE OF pedido_id ON pedidos_items
            FOR EACH ROW
            BEGIN
                UPDATE pedidos_items
                SET
                    pedido_numero = COALESCE((SELECT pedido_numero FROM pedidos WHERE pedido_id = NEW.pedido_id), ''),
                    pedido_albaran_numero = COALESCE((SELECT pedido_albaran_numero FROM pedidos WHERE pedido_id = NEW.pedido_id), ''),
                    pedido_item_fecha = COALESCE((SELECT pedido_fecha FROM pedidos WHERE pedido_id = NEW.pedido_id), NEW.pedido_item_fecha)
                WHERE item_id = NEW.item_id;
            END;
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE pedidos_items
            SET
                pedido_numero = COALESCE((SELECT p.pedido_numero FROM pedidos p WHERE p.pedido_id = pedidos_items.pedido_id), ''),
                pedido_albaran_numero = COALESCE((SELECT p.pedido_albaran_numero FROM pedidos p WHERE p.pedido_id = pedidos_items.pedido_id), ''),
                pedido_item_fecha = COALESCE((SELECT p.pedido_fecha FROM pedidos p WHERE p.pedido_id = pedidos_items.pedido_id), pedido_item_fecha)
            """
        )


def _ensure_almacen_stock_sync() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "almacen_movimientos" not in tables or "almacen_stock" not in tables:
            return
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_almacen_stock_insert
            AFTER INSERT ON almacen_movimientos
            FOR EACH ROW
            BEGIN
                INSERT INTO almacen_stock (almacen_id, articulo_id, cantidad_total)
                VALUES (NEW.almacen_id, NEW.articulo_id, COALESCE(NEW.cantidad, 0))
                ON CONFLICT(almacen_id, articulo_id)
                DO UPDATE SET cantidad_total = COALESCE(cantidad_total, 0) + COALESCE(NEW.cantidad, 0);
            END;
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_almacen_stock_delete
            AFTER DELETE ON almacen_movimientos
            FOR EACH ROW
            BEGIN
                UPDATE almacen_stock
                SET cantidad_total = COALESCE(cantidad_total, 0) - COALESCE(OLD.cantidad, 0)
                WHERE almacen_id = OLD.almacen_id AND articulo_id = OLD.articulo_id;

                DELETE FROM almacen_stock
                WHERE almacen_id = OLD.almacen_id
                  AND articulo_id = OLD.articulo_id
                  AND COALESCE(cantidad_total, 0) <= 0;
            END;
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS trg_almacen_stock_update
            AFTER UPDATE OF almacen_id, articulo_id, cantidad ON almacen_movimientos
            FOR EACH ROW
            BEGIN
                UPDATE almacen_stock
                SET cantidad_total = COALESCE(cantidad_total, 0) - COALESCE(OLD.cantidad, 0)
                WHERE almacen_id = OLD.almacen_id AND articulo_id = OLD.articulo_id;

                DELETE FROM almacen_stock
                WHERE almacen_id = OLD.almacen_id
                  AND articulo_id = OLD.articulo_id
                  AND COALESCE(cantidad_total, 0) <= 0;

                INSERT INTO almacen_stock (almacen_id, articulo_id, cantidad_total)
                VALUES (NEW.almacen_id, NEW.articulo_id, COALESCE(NEW.cantidad, 0))
                ON CONFLICT(almacen_id, articulo_id)
                DO UPDATE SET cantidad_total = COALESCE(cantidad_total, 0) + COALESCE(NEW.cantidad, 0);
            END;
            """
        )
        conn.exec_driver_sql("DELETE FROM almacen_stock")
        conn.exec_driver_sql(
            """
            INSERT INTO almacen_stock (almacen_id, articulo_id, cantidad_total)
            SELECT almacen_id, articulo_id, COALESCE(SUM(cantidad), 0)
            FROM almacen_movimientos
            GROUP BY almacen_id, articulo_id
            HAVING COALESCE(SUM(cantidad), 0) > 0
            """
        )


def _normalize_almacen_movimientos_dates() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "almacen_movimientos" not in tables:
            return
        conn.exec_driver_sql(
            """
            UPDATE almacen_movimientos
            SET fecha_pedido = DATE('now')
            WHERE fecha_pedido IS NULL OR TRIM(CAST(fecha_pedido AS TEXT)) = ''
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE almacen_movimientos
            SET articulo_caducidad = NULL
            WHERE articulo_caducidad IS NOT NULL AND TRIM(CAST(articulo_caducidad AS TEXT)) = ''
            """
        )


def _normalize_albaranes_items_dates() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "albaranes_items" not in tables:
            return
        conn.exec_driver_sql(
            """
            UPDATE albaranes_items
            SET articulo_caducidad = NULL
            WHERE articulo_caducidad IS NOT NULL AND TRIM(CAST(articulo_caducidad AS TEXT)) = ''
            """
        )


def _migrate_albaranes_items_schema() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "albaranes_items" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(albaranes_items)").fetchall()]
        if "articulo_codigo" not in columns:
            conn.exec_driver_sql("ALTER TABLE albaranes_items ADD COLUMN articulo_codigo TEXT NOT NULL DEFAULT ''")
        if "articulo_cantidad" not in columns:
            conn.exec_driver_sql("ALTER TABLE albaranes_items ADD COLUMN articulo_cantidad REAL NOT NULL DEFAULT 0")
        conn.exec_driver_sql(
            """
            UPDATE albaranes_items
            SET articulo_codigo = (
                SELECT COALESCE(NULLIF(TRIM(COALESCE(p.articulo_referencia, '')), ''), TRIM(COALESCE(p.articulo_referencia_corta, '')), '')
                FROM productos_ireks p
                WHERE p.articulo_id = albaranes_items.articulo_id
                LIMIT 1
            )
            WHERE TRIM(COALESCE(articulo_codigo, '')) = ''
            """
        )


def _migrate_facturas_items_schema() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "facturas_items" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(facturas_items)").fetchall()]
        if "dto_pct" not in columns:
            conn.exec_driver_sql("ALTER TABLE facturas_items ADD COLUMN dto_pct REAL NOT NULL DEFAULT 20")


def _migrate_tarifa_precios_schema() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "tarifa_precios_ireks" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(tarifa_precios_ireks)").fetchall()]
        if "descuento_pct" not in columns:
            conn.exec_driver_sql("ALTER TABLE tarifa_precios_ireks ADD COLUMN descuento_pct REAL NOT NULL DEFAULT 0")


def _migrate_almacen_movimientos_schema() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "almacen_movimientos" not in tables:
            return
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(almacen_movimientos)").fetchall()]
        if "albaran_item_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE almacen_movimientos ADD COLUMN albaran_item_id TEXT NOT NULL DEFAULT ''")


def _ensure_default_almacen() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "almacenes_catalogo" not in tables:
            return
        total_row = conn.exec_driver_sql("SELECT COUNT(*) FROM almacenes_catalogo").fetchone()
        total = int(total_row[0] if total_row else 0)
        if total > 0:
            return
        conn.exec_driver_sql(
            "INSERT INTO almacenes_catalogo (almacen_id, almacen_nombre) VALUES (?, ?)",
            (str(uuid4()), "Central"),
        )


def _migrate_codigos_postales_table() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "codigos_postales" not in tables:
            return

        info = conn.exec_driver_sql("PRAGMA table_info(codigos_postales)").fetchall()
        columns = [row[1] for row in info]
        has_required = "municipio_id" in columns and "codigo_postal" in columns
        if not has_required:
            return
        pk_municipio = any(row[1] == "municipio_id" and int(row[5] or 0) > 0 for row in info)
        pk_codigo = any(row[1] == "codigo_postal" and int(row[5] or 0) > 0 for row in info)
        if pk_municipio and pk_codigo:
            return

        rows = conn.exec_driver_sql(
            """
            SELECT DISTINCT TRIM(COALESCE(municipio_id, '')), TRIM(COALESCE(codigo_postal, ''))
            FROM codigos_postales
            WHERE TRIM(COALESCE(municipio_id, '')) <> ''
              AND TRIM(COALESCE(codigo_postal, '')) <> ''
            """
        ).fetchall()

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("ALTER TABLE codigos_postales RENAME TO codigos_postales_old_schema")
        conn.exec_driver_sql(
            """
            CREATE TABLE codigos_postales (
                municipio_id TEXT NOT NULL,
                codigo_postal TEXT NOT NULL,
                PRIMARY KEY (municipio_id, codigo_postal),
                FOREIGN KEY (municipio_id) REFERENCES municipios (municipio_id)
            )
            """
        )
        for municipio_id, codigo_postal in rows:
            conn.exec_driver_sql(
                "INSERT INTO codigos_postales (municipio_id, codigo_postal) VALUES (?, ?)",
                (municipio_id, codigo_postal),
            )
        conn.exec_driver_sql("DROP TABLE codigos_postales_old_schema")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _migrate_localidades_table() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "localidades" not in tables:
            return

        info = conn.exec_driver_sql("PRAGMA table_info(localidades)").fetchall()
        columns = [row[1] for row in info]
        if not {"localidad_id", "municipio_id", "localidad_nombre", "codigo_postal"}.issubset(set(columns)):
            return

        cp_info = next((row for row in info if row[1] == "codigo_postal"), None)
        cp_notnull = int(cp_info[3] or 0) if cp_info else 0
        if cp_notnull == 0:
            return

        rows = conn.exec_driver_sql(
            """
            SELECT
                TRIM(COALESCE(localidad_id, '')),
                TRIM(COALESCE(municipio_id, '')),
                TRIM(COALESCE(localidad_nombre, '')),
                NULLIF(TRIM(COALESCE(codigo_postal, '')), '')
            FROM localidades
            WHERE TRIM(COALESCE(localidad_id, '')) <> ''
              AND TRIM(COALESCE(municipio_id, '')) <> ''
              AND TRIM(COALESCE(localidad_nombre, '')) <> ''
            """
        ).fetchall()

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("ALTER TABLE localidades RENAME TO localidades_old_schema")
        conn.exec_driver_sql(
            """
            CREATE TABLE localidades (
                localidad_id TEXT PRIMARY KEY NOT NULL,
                municipio_id TEXT NOT NULL,
                localidad_nombre TEXT NOT NULL DEFAULT '',
                codigo_postal TEXT,
                FOREIGN KEY (municipio_id, codigo_postal)
                    REFERENCES codigos_postales (municipio_id, codigo_postal)
            )
            """
        )
        for localidad_id, municipio_id, localidad_nombre, codigo_postal in rows:
            conn.exec_driver_sql(
                """
                INSERT INTO localidades (localidad_id, municipio_id, localidad_nombre, codigo_postal)
                VALUES (?, ?, ?, ?)
                """,
                (localidad_id, municipio_id, localidad_nombre, codigo_postal),
            )
        conn.exec_driver_sql("DROP TABLE localidades_old_schema")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _migrate_nutrition_table_name() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "materias_primas_valores_nutricionales" in tables and "productos_valores_nutricionales" not in tables:
            conn.exec_driver_sql(
                "ALTER TABLE materias_primas_valores_nutricionales RENAME TO productos_valores_nutricionales"
            )


def _migrate_pedidos_estado_column() -> None:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "pedidos" not in tables:
            return
        columns = {str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(pedidos)").fetchall()}
        if "pedido_estado" not in columns:
            conn.exec_driver_sql("ALTER TABLE pedidos ADD COLUMN pedido_estado TEXT NOT NULL DEFAULT ''")


def _ensure_pedidos_email_log_table() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS pedidos_email_log (
                log_id TEXT PRIMARY KEY,
                pedido_id TEXT NOT NULL,
                pedido_numero TEXT NOT NULL DEFAULT '',
                destino_email TEXT NOT NULL DEFAULT '',
                asunto TEXT NOT NULL DEFAULT '',
                adjunto_path TEXT NOT NULL DEFAULT '',
                modo_envio TEXT NOT NULL DEFAULT '',
                estado TEXT NOT NULL DEFAULT '',
                error_detalle TEXT NOT NULL DEFAULT '',
                creado_en TEXT NOT NULL DEFAULT (DATETIME('now'))
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_pedidos_email_log_pedido_id ON pedidos_email_log (pedido_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_pedidos_email_log_creado_en ON pedidos_email_log (creado_en)"
        )


def _ensure_productos_ireks_referencias_export_view() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP VIEW IF EXISTS productos_ireks_referencias_distribuidor")
        conn.exec_driver_sql(
            """
            CREATE VIEW productos_ireks_referencias_distribuidor AS
            SELECT
                p.articulo_id AS articulo_id,
                p.articulo_referencia AS articulo_referencia,
                p.articulo_referencia_corta AS articulo_referencia_corta,
                p.articulo_descripcion AS articulo_descripcion,
                p.articulo_envase_cantidad AS articulo_envase_cantidad,
                p.articulo_envase_peso AS articulo_envase_peso,
                p.articulo_envase_unidad_medida AS articulo_envase_unidad_medida,
                p.articulo_envase_peso_total AS articulo_envase_peso_total,
                p.fabricante_id AS fabricante_id,
                f.fabricante_nombre AS fabricante_nombre,
                p.articulo_familia_id AS articulo_familia_id,
                fam.articulo_familia_nombre AS articulo_familia_nombre,
                p.articulo_subfamilia_id AS articulo_subfamilia_id,
                sub.articulo_subfamilia_nombre AS articulo_subfamilia_nombre,
                p.distribuidor_id AS distribuidor_id_principal,
                d0.distribuidor_nombre_comercial AS distribuidor_principal_nombre,
                rd.distribuidor_id AS referencia_distribuidor_id,
                d.distribuidor_nombre_comercial AS referencia_distribuidor_nombre,
                rd.articulo_referencia_distribuidor AS articulo_referencia_distribuidor,
                rd.articulo_descripcion_distribuidor AS articulo_descripcion_distribuidor,
                p.categoria AS categoria,
                p.articulo_status_activo AS articulo_status_activo,
                p.articulo_status_en_lista AS articulo_status_en_lista
            FROM productos_ireks p
            LEFT JOIN fabricantes f ON f.fabricante_id = p.fabricante_id
            LEFT JOIN familias fam ON fam.articulo_familia_id = p.articulo_familia_id
            LEFT JOIN subfamilias sub ON sub.articulo_subfamilia_id = p.articulo_subfamilia_id
            LEFT JOIN distribuidores d0 ON d0.distribuidor_id = p.distribuidor_id
            LEFT JOIN referencias_distribuidor rd ON rd.articulo_id = p.articulo_id
            LEFT JOIN distribuidores d ON d.distribuidor_id = rd.distribuidor_id
            """
        )


def init_db() -> None:
    import app.models.entities  # noqa: F401

    _migrate_ingredient_columns()
    _migrate_almacen_table()
    _migrate_almacen_movimientos_schema()
    _normalize_almacen_movimientos_dates()
    _migrate_sales_tables()
    SQLModel.metadata.create_all(engine)
    _migrate_albaranes_items_schema()
    _migrate_facturas_items_schema()
    _migrate_tarifa_precios_schema()
    _normalize_albaranes_items_dates()
    _migrate_productos_ireks_schema()
    _migrate_client_table()
    _migrate_contact_columns()
    _migrate_contactos_cliente_fk()
    _migrate_asistentes_columns()
    _migrate_asistentes_fks()
    _migrate_tecnicos_columns()
    _migrate_ingredientes_std_columns()
    _migrate_recetas_cliente_fk()
    _migrate_receta_child_fks()
    _migrate_recetas_technical_fields()
    _migrate_receta_lineas_process_fields()
    _migrate_ingredientes_std_to_materias_primas()
    _migrate_nutrition_table_name()
    _migrate_pedidos_estado_column()
    _ensure_pedidos_email_log_table()
    _ensure_productos_ireks_referencias_export_view()
    _migrate_codigos_postales_table()
    _migrate_localidades_table()
    _ensure_distribuidores_autogen()
    _ensure_tecnicos_autogen()
    _ensure_proveedores_autogen()
    _ensure_envases_autogen()
    _ensure_pedidos_items_sync()
    _ensure_almacen_stock_sync()
    _ensure_default_almacen()
    _ensure_indexes()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def repair_cliente_contacto_links() -> dict[str, int]:
    with engine.begin() as conn:
        before_orphans_row = conn.exec_driver_sql(
            """
            SELECT COUNT(*)
            FROM contactos ct
            LEFT JOIN clientes cl ON cl.cliente_id = ct.cliente_id
            WHERE cl.cliente_id IS NULL
            """
        ).fetchone()
        before_orphans = before_orphans_row[0] if before_orphans_row else 0
        conn.exec_driver_sql("UPDATE contactos SET cliente_id = TRIM(cliente_id) WHERE cliente_id IS NOT NULL")
        after_orphans_row = conn.exec_driver_sql(
            """
            SELECT COUNT(*)
            FROM contactos ct
            LEFT JOIN clientes cl ON cl.cliente_id = ct.cliente_id
            WHERE cl.cliente_id IS NULL
            """
        ).fetchone()
        after_orphans = after_orphans_row[0] if after_orphans_row else 0
    return {
        "updated_links": 0,
        "orphans_before": int(before_orphans or 0),
        "orphans_after": int(after_orphans or 0),
    }


def get_orphan_contact_count() -> int:
    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "clientes" not in tables or "contactos" not in tables:
            return 0
        value_row = conn.exec_driver_sql(
            """
            SELECT COUNT(*)
            FROM contactos ct
            LEFT JOIN clientes cl ON cl.cliente_id = ct.cliente_id
            WHERE cl.cliente_id IS NULL
            """
        ).fetchone()
        value = value_row[0] if value_row else 0
    return int(value or 0)


def create_missing_clients_for_contact_links() -> int:
    with engine.begin() as conn:
        orphan_ids = [
            row[0]
            for row in conn.exec_driver_sql(
                """
                SELECT DISTINCT ct.cliente_id
                FROM contactos ct
                LEFT JOIN clientes cl ON cl.cliente_id = ct.cliente_id
                WHERE cl.cliente_id IS NULL
                  AND ct.cliente_id IS NOT NULL
                  AND TRIM(ct.cliente_id) <> ''
                """
            ).fetchall()
        ]
        created = 0
        max_code_row = conn.exec_driver_sql("SELECT COALESCE(MAX(cliente_codigo), 0) FROM clientes").fetchone()
        max_code = int(max_code_row[0] if max_code_row else 0)
        for cliente_id in orphan_ids:
            max_code += 1
            conn.exec_driver_sql(
                """
                INSERT INTO clientes (
                    cliente_id, cliente_codigo, cliente_nombre_comercial, cliente_nombre_fiscal, cliente_nombre_interno, cliente_abreviatura,
                    cliente_cif, cliente_telefono, cliente_email, cliente_direccion, cliente_direccion_cp,
                    cliente_direccion_localidad_id, cliente_direccion_municipio_id, cliente_direccion_provincia_id,
                    cliente_direccion_isla_id, cliente_tipo, cliente_actividad, cliente_prospeccion, distribuidor_id, activo
                )
                VALUES (?, ?, ?, ?, '', '', '', '', '', '', '', '', '', '', '', '', '', 0, '', 0)
                """,
                (
                    cliente_id,
                    max_code,
                    f"EMPRESA PENDIENTE {str(cliente_id)[:8]}",
                    f"EMPRESA PENDIENTE {str(cliente_id)[:8]}",
                ),
            )
            created += 1
    return created


def run_integrity_check() -> list[str]:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA integrity_check").fetchall()
    return [str(row[0]) for row in rows]


def optimize_database() -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA optimize")
        conn.exec_driver_sql("ANALYZE")
    with sqlite3.connect(DB_PATH) as raw_conn:
        raw_conn.execute("VACUUM")


def backup_database(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return destination


def get_database_status() -> dict[str, object]:
    counts: dict[str, int] = {
        "almacen_movimientos": 0,
        "almacen_stock": 0,
        "albaranes": 0,
        "albaranes_items": 0,
        "pedidos_pendientes": 0,
        "fabricantes": 0,
        "familias": 0,
        "subfamilias": 0,
        "productos_ireks": 0,
        "clientes": 0,
        "contactos": 0,
        "distribuidores": 0,
        "envases": 0,
        "materias_primas": 0,
        "referencias_distribuidor": 0,
        "pedidos": 0,
        "pedidos_items": 0,
        "ventas": 0,
        "cursos": 0,
        "asistentes": 0,
        "tecnicos": 0,
        "cursos_tecnicos": 0,
        "cursos_documentos": 0,
        "provincias": 0,
        "islas": 0,
        "municipios": 0,
        "codigos_postales": 0,
        "localidades": 0,
    }
    if DB_PATH.exists():
        with engine.begin() as conn:
            tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            for table in counts:
                if table in tables:
                    value_row = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table}").fetchone()
                    value = value_row[0] if value_row else 0
                    counts[table] = int(value or 0)
    return {
        "db_path": str(DB_PATH),
        "legacy_db_path": str(LEGACY_DB_PATH),
        "db_exists": DB_PATH.exists(),
        "legacy_exists": LEGACY_DB_PATH.exists(),
        "db_size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        "counts": counts,
        "orphan_contact_links": get_orphan_contact_count() if DB_PATH.exists() else 0,
    }




