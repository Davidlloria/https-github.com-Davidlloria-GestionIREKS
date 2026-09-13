from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import Connection, Engine

from app.core.database import engine


@dataclass(frozen=True, slots=True)
class WarehouseEntryIntegrityAudit:
    orphan_albaranes: int = 0
    orphan_albaran_items: int = 0
    valid_items_missing_entry: int = 0
    entry_links_without_item: int = 0
    unlinked_positive_entries: int = 0
    duplicate_entry_groups: int = 0
    mismatched_entries: int = 0
    stock_mismatches: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WarehouseEntryRepairResult:
    before: WarehouseEntryIntegrityAudit
    after: WarehouseEntryIntegrityAudit
    deleted_orphan_albaranes: int = 0
    deleted_orphan_items: int = 0
    created_entries: int = 0
    updated_entries: int = 0
    deleted_duplicate_entries: int = 0
    rebuilt_stock_rows: int = 0
    unresolved_orphan_albaranes: int = 0
    integrity_check: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["before"] = self.before.as_dict()
        payload["after"] = self.after.as_dict()
        return payload


class WarehouseEntryRepairService:
    """Audita y repara la correspondencia albaran/entrada de almacen."""

    def __init__(self, database_engine: Engine = engine) -> None:
        self.engine = database_engine

    def audit(self) -> WarehouseEntryIntegrityAudit:
        with self.engine.connect() as conn:
            return self._audit(conn)

    def repair(self) -> WarehouseEntryRepairResult:
        with self.engine.begin() as conn:
            before = self._audit(conn)
            deleted_albaranes, deleted_items, unresolved = (
                self._delete_proven_orphan_duplicates(conn)
            )
            created_entries = self._create_missing_entries(conn)
            deleted_duplicate_entries = self._delete_duplicate_entries(conn)
            updated_entries = self._synchronize_linked_entries(conn)
            rebuilt_stock_rows = self._rebuild_stock(conn)
            after = self._audit(conn)
            integrity_row = conn.exec_driver_sql("PRAGMA integrity_check").fetchone()
            integrity_check = str(integrity_row[0] if integrity_row else "")
        return WarehouseEntryRepairResult(
            before=before,
            after=after,
            deleted_orphan_albaranes=deleted_albaranes,
            deleted_orphan_items=deleted_items,
            created_entries=created_entries,
            updated_entries=updated_entries,
            deleted_duplicate_entries=deleted_duplicate_entries,
            rebuilt_stock_rows=rebuilt_stock_rows,
            unresolved_orphan_albaranes=unresolved,
            integrity_check=integrity_check,
        )

    @staticmethod
    def _scalar(conn: Connection, sql: str) -> int:
        row = conn.exec_driver_sql(sql).fetchone()
        return int(row[0] if row else 0)

    def _audit(self, conn: Connection) -> WarehouseEntryIntegrityAudit:
        return WarehouseEntryIntegrityAudit(
            orphan_albaranes=self._scalar(
                conn,
                "SELECT COUNT(*) FROM albaranes a LEFT JOIN pedidos p ON p.pedido_id=a.pedido_id WHERE p.pedido_id IS NULL",
            ),
            orphan_albaran_items=self._scalar(
                conn,
                "SELECT COUNT(*) FROM albaranes_items ai LEFT JOIN pedidos p ON p.pedido_id=ai.pedido_id LEFT JOIN albaranes a ON a.albaran_id=ai.albaran_id WHERE p.pedido_id IS NULL OR a.albaran_id IS NULL",
            ),
            valid_items_missing_entry=self._scalar(
                conn,
                """SELECT COUNT(*) FROM albaranes_items ai JOIN pedidos p ON p.pedido_id=ai.pedido_id JOIN albaranes a ON a.albaran_id=ai.albaran_id JOIN productos_ireks pr ON pr.articulo_id=ai.articulo_id LEFT JOIN almacen_movimientos m ON m.albaran_item_id=ai.item_id AND m.cantidad>0 AND m.id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos) WHERE ai.articulo_cantidad>0 AND m.id IS NULL""",
            ),
            entry_links_without_item=self._scalar(
                conn,
                """SELECT COUNT(*) FROM almacen_movimientos m LEFT JOIN albaranes_items ai ON ai.item_id=m.albaran_item_id WHERE m.cantidad>0 AND m.id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos) AND TRIM(COALESCE(m.albaran_item_id,''))<>'' AND ai.item_id IS NULL""",
            ),
            unlinked_positive_entries=self._scalar(
                conn,
                "SELECT COUNT(*) FROM almacen_movimientos WHERE cantidad>0 AND id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos) AND TRIM(COALESCE(albaran_item_id,''))=''",
            ),
            duplicate_entry_groups=self._scalar(
                conn,
                """SELECT COUNT(*) FROM (SELECT albaran_item_id FROM almacen_movimientos WHERE cantidad>0 AND id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos) AND TRIM(COALESCE(albaran_item_id,''))<>'' GROUP BY albaran_item_id HAVING COUNT(*)>1) duplicates""",
            ),
            mismatched_entries=self._scalar(
                conn,
                """SELECT COUNT(*) FROM almacen_movimientos m JOIN albaranes_items ai ON ai.item_id=m.albaran_item_id JOIN albaranes a ON a.albaran_id=ai.albaran_id JOIN pedidos p ON p.pedido_id=ai.pedido_id WHERE m.cantidad>0 AND m.id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos) AND (m.articulo_id<>ai.articulo_id OR ABS(m.cantidad-ai.articulo_cantidad)>0.000001 OR COALESCE(m.articulo_lote,'')<>COALESCE(ai.articulo_lote,'') OR COALESCE(m.articulo_caducidad,'')<>COALESCE(ai.articulo_caducidad,'') OR COALESCE(m.fecha_pedido,'')<>COALESCE(ai.albaran_fecha,'') OR COALESCE(m.pedido_albaran_numero,'')<>COALESCE(a.albaran_numero,'') OR COALESCE(m.pedido_numero,'')<>COALESCE(p.pedido_numero,'') OR COALESCE(m.almacen_id,'')<>COALESCE(p.almacen_id,''))""",
            ),
            stock_mismatches=self._scalar(
                conn,
                """SELECT COUNT(*) FROM (SELECT totals.almacen_id,totals.articulo_id FROM (SELECT almacen_id,articulo_id,SUM(cantidad) cantidad FROM almacen_movimientos GROUP BY almacen_id,articulo_id HAVING SUM(cantidad)>0) totals LEFT JOIN almacen_stock stock ON stock.almacen_id=totals.almacen_id AND stock.articulo_id=totals.articulo_id WHERE ABS(totals.cantidad-COALESCE(stock.cantidad_total,0))>0.000001 UNION ALL SELECT stock.almacen_id,stock.articulo_id FROM almacen_stock stock LEFT JOIN (SELECT almacen_id,articulo_id FROM almacen_movimientos GROUP BY almacen_id,articulo_id HAVING SUM(cantidad)>0) totals ON totals.almacen_id=stock.almacen_id AND totals.articulo_id=stock.articulo_id WHERE totals.articulo_id IS NULL) differences""",
            ),
        )

    def _delete_proven_orphan_duplicates(
        self, conn: Connection
    ) -> tuple[int, int, int]:
        product_ids_by_code: dict[str, set[str]] = {}
        for row in conn.exec_driver_sql(
            "SELECT articulo_id,articulo_referencia,articulo_referencia_corta FROM productos_ireks"
        ).fetchall():
            articulo_id = str(row[0] or "").strip().upper()
            for raw_code in (row[1], row[2]):
                code = str(raw_code or "").strip().upper()
                if code and articulo_id:
                    product_ids_by_code.setdefault(code, set()).add(articulo_id)

        orphan_albaranes = conn.exec_driver_sql(
            """SELECT a.albaran_id,a.almacen_id,a.albaran_numero,a.albaran_fecha FROM albaranes a LEFT JOIN pedidos p ON p.pedido_id=a.pedido_id WHERE p.pedido_id IS NULL ORDER BY a.albaran_fecha,a.albaran_numero,a.albaran_id"""
        ).fetchall()
        deleted_albaranes = 0
        deleted_items = 0
        unresolved = 0
        for orphan in orphan_albaranes:
            orphan_id = str(orphan[0] or "").strip()
            valid_rows = conn.exec_driver_sql(
                """SELECT a.albaran_id FROM albaranes a JOIN pedidos p ON p.pedido_id=a.pedido_id WHERE a.almacen_id=? AND a.albaran_numero=? AND a.albaran_fecha=?""",
                (orphan[1], orphan[2], orphan[3]),
            ).fetchall()
            if len(valid_rows) != 1:
                unresolved += 1
                continue
            item_sql = """SELECT item_id,articulo_id,articulo_codigo,articulo_cantidad,articulo_lote,articulo_caducidad FROM albaranes_items WHERE albaran_id=?"""
            orphan_items = conn.exec_driver_sql(item_sql, (orphan_id,)).fetchall()
            valid_items = conn.exec_driver_sql(item_sql, (valid_rows[0][0],)).fetchall()
            orphan_signatures = Counter(
                self._item_signature(row, product_ids_by_code) for row in orphan_items
            )
            valid_signatures = Counter(
                self._item_signature(row, product_ids_by_code) for row in valid_items
            )
            linked_moves = self._scalar_for_param(
                conn,
                "SELECT COUNT(*) FROM almacen_movimientos WHERE albaran_item_id IN (SELECT item_id FROM albaranes_items WHERE albaran_id=?)",
                (orphan_id,),
            )
            if orphan_signatures != valid_signatures or linked_moves:
                unresolved += 1
                continue
            deleted_items += len(orphan_items)
            conn.exec_driver_sql(
                "DELETE FROM albaranes_items WHERE albaran_id=?", (orphan_id,)
            )
            conn.exec_driver_sql(
                "DELETE FROM albaranes WHERE albaran_id=?", (orphan_id,)
            )
            deleted_albaranes += 1
        return deleted_albaranes, deleted_items, unresolved

    @staticmethod
    def _scalar_for_param(conn: Connection, sql: str, params: tuple[Any, ...]) -> int:
        row = conn.exec_driver_sql(sql, params).fetchone()
        return int(row[0] if row else 0)

    @staticmethod
    def _item_signature(
        row: Any, product_ids_by_code: dict[str, set[str]]
    ) -> tuple[Any, ...]:
        articulo_id = str(row[1] or "").strip().upper()
        code = str(row[2] or "").strip().upper()
        if not articulo_id:
            candidates = product_ids_by_code.get(code, set())
            if len(candidates) == 1:
                articulo_id = next(iter(candidates))
        identity = f"id:{articulo_id}" if articulo_id else f"code:{code}"
        return (
            identity,
            round(float(row[3] or 0.0), 6),
            str(row[4] or "").strip().upper(),
            str(row[5] or "").strip(),
        )

    @staticmethod
    def _create_missing_entries(conn: Connection) -> int:
        rows = conn.exec_driver_sql(
            """SELECT ai.item_id,p.almacen_id,ai.articulo_id,p.pedido_numero,a.albaran_numero,ai.articulo_cantidad,ai.articulo_lote,ai.articulo_caducidad,ai.albaran_fecha FROM albaranes_items ai JOIN pedidos p ON p.pedido_id=ai.pedido_id JOIN albaranes a ON a.albaran_id=ai.albaran_id JOIN productos_ireks pr ON pr.articulo_id=ai.articulo_id LEFT JOIN almacen_movimientos m ON m.albaran_item_id=ai.item_id AND m.cantidad>0 AND m.id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos) WHERE ai.articulo_cantidad>0 AND m.id IS NULL"""
        ).fetchall()
        for row in rows:
            conn.exec_driver_sql(
                """INSERT INTO almacen_movimientos (almacen_id,articulo_id,pedido_numero,pedido_albaran_numero,cantidad,articulo_lote,articulo_caducidad,fecha_pedido,albaran_item_id) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[0],
                ),
            )
        return len(rows)

    @staticmethod
    def _delete_duplicate_entries(conn: Connection) -> int:
        groups = conn.exec_driver_sql(
            """SELECT albaran_item_id FROM almacen_movimientos WHERE cantidad>0 AND id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos) AND TRIM(COALESCE(albaran_item_id,''))<>'' GROUP BY albaran_item_id HAVING COUNT(*)>1"""
        ).fetchall()
        deleted = 0
        for group in groups:
            ids = [
                int(row[0])
                for row in conn.exec_driver_sql(
                    "SELECT id FROM almacen_movimientos WHERE cantidad>0 AND id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos) AND albaran_item_id=? ORDER BY id",
                    (group[0],),
                ).fetchall()
            ]
            for movement_id in ids[1:]:
                conn.exec_driver_sql(
                    "DELETE FROM almacen_movimientos WHERE id=?", (movement_id,)
                )
                deleted += 1
        return deleted

    @staticmethod
    def _synchronize_linked_entries(conn: Connection) -> int:
        rows = conn.exec_driver_sql(
            """SELECT m.id,m.almacen_id,p.almacen_id,m.articulo_id,ai.articulo_id,m.pedido_numero,p.pedido_numero,m.pedido_albaran_numero,a.albaran_numero,m.cantidad,ai.articulo_cantidad,m.articulo_lote,ai.articulo_lote,m.articulo_caducidad,ai.articulo_caducidad,m.fecha_pedido,ai.albaran_fecha FROM almacen_movimientos m JOIN albaranes_items ai ON ai.item_id=m.albaran_item_id JOIN albaranes a ON a.albaran_id=ai.albaran_id JOIN pedidos p ON p.pedido_id=ai.pedido_id WHERE m.cantidad>0 AND m.id NOT IN (SELECT movimiento_id FROM pedidos_faltantes_movimientos)"""
        ).fetchall()
        updated = 0
        for row in rows:
            current = (
                str(row[1] or ""),
                str(row[3] or ""),
                str(row[5] or ""),
                str(row[7] or ""),
                round(float(row[9] or 0.0), 6),
                str(row[11] or ""),
                str(row[13] or ""),
                str(row[15] or ""),
            )
            expected = (
                str(row[2] or ""),
                str(row[4] or ""),
                str(row[6] or ""),
                str(row[8] or ""),
                round(float(row[10] or 0.0), 6),
                str(row[12] or ""),
                str(row[14] or ""),
                str(row[16] or ""),
            )
            if current == expected:
                continue
            conn.exec_driver_sql(
                """UPDATE almacen_movimientos SET almacen_id=?,articulo_id=?,pedido_numero=?,pedido_albaran_numero=?,cantidad=?,articulo_lote=?,articulo_caducidad=?,fecha_pedido=? WHERE id=?""",
                (
                    row[2],
                    row[4],
                    row[6],
                    row[8],
                    row[10],
                    row[12],
                    row[14],
                    row[16],
                    row[0],
                ),
            )
            updated += 1
        return updated

    @staticmethod
    def _rebuild_stock(conn: Connection) -> int:
        conn.exec_driver_sql("DELETE FROM almacen_stock")
        conn.exec_driver_sql(
            """INSERT INTO almacen_stock (almacen_id,articulo_id,cantidad_total) SELECT almacen_id,articulo_id,SUM(cantidad) FROM almacen_movimientos GROUP BY almacen_id,articulo_id HAVING SUM(cantidad)>0"""
        )
        row = conn.exec_driver_sql("SELECT COUNT(*) FROM almacen_stock").fetchone()
        return int(row[0] if row else 0)


__all__ = [
    "WarehouseEntryIntegrityAudit",
    "WarehouseEntryRepairResult",
    "WarehouseEntryRepairService",
]
