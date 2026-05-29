from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4
from datetime import date

from sqlmodel import Session, select

from app.core.database import engine
from app.models import AlmacenMovimiento, AlmacenStock, IngredienteIreks, InventarioCabecera, InventarioDetalle
from app.schemas.warehouse import (
    InventoryAdjustmentPayload,
    InventoryDetailRead,
    InventoryExportPayload as ApiInventoryExportPayload,
    InventoryHeaderRead,
    WarehouseMovementRead,
    WarehouseStockRead,
)


def _col(expr: object) -> Any:
    return cast(Any, expr)


@dataclass
class InventoryStockPayload:
    moves: list[AlmacenMovimiento]
    items: list[IngredienteIreks]


@dataclass
class InventoryHistoryDetailPayload:
    details: list[InventarioDetalle]
    items: list[IngredienteIreks]


@dataclass
class InventoryExportPayload:
    headers: list[InventarioCabecera]
    details: list[InventarioDetalle]
    items: list[IngredienteIreks]


class WarehouseInventoryService:
    def stock_summary_payload(self, almacen_id: str = "") -> list[WarehouseStockRead]:
        with Session(engine) as session:
            stmt = select(AlmacenStock)
            if almacen_id:
                stmt = stmt.where(AlmacenStock.almacen_id == almacen_id)
            rows = list(session.exec(stmt.order_by(AlmacenStock.almacen_id, AlmacenStock.articulo_id)))
        return WarehouseStockRead.list_from_entities(rows)

    def stock_payload(self, almacen_id: str = "") -> InventoryStockPayload:
        with Session(engine) as session:
            stmt = select(AlmacenMovimiento)
            if almacen_id:
                stmt = stmt.where(AlmacenMovimiento.almacen_id == almacen_id)
            moves = list(session.exec(stmt))
            return InventoryStockPayload(moves=moves, items=self._items_for_records(session, moves))

    def movement_payload_serializable(self, almacen_id: str = "") -> list[WarehouseMovementRead]:
        return WarehouseMovementRead.list_from_entities(self.stock_payload(almacen_id).moves)

    def apply_adjustments(self, *, pending: list[dict[str, Any]], almacen_id: str, contador: str, aprobador: str) -> int:
        return self._persist_adjustments(pending=pending, almacen_id=almacen_id, contador=contador, aprobador=aprobador).lineas

    def apply_adjustments_from_payload(self, payload: InventoryAdjustmentPayload) -> InventoryHeaderRead:
        almacen_id = str(payload.almacen_id or "").strip()
        contador = str(payload.contador or "").strip()
        aprobador = str(payload.aprobador or "").strip()
        if not almacen_id:
            raise ValueError("Indica almacen_id.")
        if not contador or not aprobador:
            raise ValueError("Indica contador y aprobador.")

        today = date.today()
        pending: list[dict[str, Any]] = []
        for adjustment in payload.adjustments:
            articulo_id = str(adjustment.articulo_id or "").strip()
            if not articulo_id:
                raise ValueError("Todas las lineas deben indicar articulo_id.")
            teorico = float(adjustment.teorico_uds or 0.0)
            conteo = float(adjustment.conteo_uds or 0.0)
            diferencia = float(adjustment.diferencia_uds or 0.0)
            if abs(diferencia) < 0.0001:
                diferencia = conteo - teorico
            if abs(diferencia) < 0.0001:
                continue
            mov = AlmacenMovimiento(
                almacen_id=almacen_id,
                articulo_id=articulo_id,
                pedido_numero=f"INV-{today.strftime('%Y%m%d')}",
                pedido_albaran_numero="INV-AJUSTE",
                cantidad=diferencia,
                articulo_lote=str(adjustment.articulo_lote or "").strip(),
                articulo_caducidad=adjustment.articulo_caducidad,
                fecha_pedido=today,
                albaran_item_id=str(uuid4()),
            )
            pending.append(
                {
                    "mov": mov,
                    "articulo_id": articulo_id,
                    "articulo_lote": str(adjustment.articulo_lote or "").strip(),
                    "articulo_caducidad": adjustment.articulo_caducidad,
                    "teorico_uds": teorico,
                    "conteo_uds": conteo,
                    "diferencia_uds": diferencia,
                    "kg_ajuste": float(adjustment.kg_ajuste or 0.0),
                }
            )
        if not pending:
            raise ValueError("No hay diferencias para ajustar.")
        return self._persist_adjustments(pending=pending, almacen_id=almacen_id, contador=contador, aprobador=aprobador)

    def _persist_adjustments(
        self,
        *,
        pending: list[dict[str, Any]],
        almacen_id: str,
        contador: str,
        aprobador: str,
    ) -> InventoryHeaderRead:
        today = date.today()
        clean_almacen_id = str(almacen_id or "").strip()
        clean_contador = str(contador or "").strip()
        clean_aprobador = str(aprobador or "").strip()
        with Session(engine) as session:
            inv_id = str(uuid4())
            total_ajustes = 0
            for payload in pending:
                mov = payload["mov"]
                if not isinstance(mov, AlmacenMovimiento):
                    continue
                mov.pedido_numero = inv_id
                mov.pedido_albaran_numero = f"INV-AJUSTE|CONT:{clean_contador}|APROB:{clean_aprobador}"
                session.add(mov)
                if abs(float(getattr(mov, "cantidad", 0.0) or 0.0)) > 0.0001:
                    total_ajustes += 1
                session.add(
                    InventarioDetalle(
                        inventario_id=inv_id,
                        almacen_id=clean_almacen_id,
                        articulo_id=str(payload.get("articulo_id", "") or "").strip(),
                        articulo_lote=str(payload.get("articulo_lote", "") or "").strip(),
                        articulo_caducidad=payload.get("articulo_caducidad"),
                        teorico_uds=float(payload.get("teorico_uds", 0.0) or 0.0),
                        conteo_uds=float(payload.get("conteo_uds", 0.0) or 0.0),
                        diferencia_uds=float(payload.get("diferencia_uds", 0.0) or 0.0),
                        kg_ajuste=float(payload.get("kg_ajuste", 0.0) or 0.0),
                    )
                )
            session.add(
                header := InventarioCabecera(
                    inventario_id=inv_id,
                    almacen_id=clean_almacen_id,
                    fecha=today,
                    contador=clean_contador,
                    aprobador=clean_aprobador,
                    estado="aprobado",
                    lineas=len(pending),
                    ajustes=total_ajustes,
                )
            )
            session.commit()
            session.refresh(header)
            return InventoryHeaderRead.from_entity(header)

    def history(self, almacen_id: str = "", limit: int = 50) -> list[InventarioCabecera]:
        with Session(engine) as session:
            stmt = select(InventarioCabecera)
            if almacen_id:
                stmt = stmt.where(InventarioCabecera.almacen_id == almacen_id)
            return list(
                session.exec(
                    stmt.order_by(
                        _col(InventarioCabecera.fecha).desc(),
                        _col(InventarioCabecera.inventario_id).desc(),
                    )
                )
            )[:limit]

    def history_payload(self, almacen_id: str = "", limit: int = 50) -> list[InventoryHeaderRead]:
        return InventoryHeaderRead.list_from_entities(self.history(almacen_id, limit))

    def history_detail(self, inventario_id: str) -> InventoryHistoryDetailPayload:
        with Session(engine) as session:
            detail_rows = list(
                session.exec(
                    select(InventarioDetalle)
                    .where(InventarioDetalle.inventario_id == inventario_id)
                    .order_by(_col(InventarioDetalle.id).asc())
                )
            )
            return InventoryHistoryDetailPayload(
                details=detail_rows,
                items=self._items_for_records(session, detail_rows),
            )

    def history_detail_payload(self, inventario_id: str) -> list[InventoryDetailRead]:
        return InventoryDetailRead.list_from_entities(self.history_detail(inventario_id).details)

    def export_payload(self, *, almacen_id: str = "", selected_id: str = "") -> InventoryExportPayload:
        with Session(engine) as session:
            head_stmt = select(InventarioCabecera)
            if almacen_id:
                head_stmt = head_stmt.where(InventarioCabecera.almacen_id == almacen_id)
            if selected_id:
                head_stmt = head_stmt.where(InventarioCabecera.inventario_id == selected_id)
            headers = list(
                session.exec(
                    head_stmt.order_by(
                        _col(InventarioCabecera.fecha).desc(),
                        _col(InventarioCabecera.inventario_id).desc(),
                    )
                )
            )
            inv_ids = [str(getattr(x, "inventario_id", "") or "").strip() for x in headers if str(getattr(x, "inventario_id", "") or "").strip()]
            details = (
                list(
                    session.exec(
                        select(InventarioDetalle)
                        .where(_col(InventarioDetalle.inventario_id).in_(inv_ids))
                        .order_by(_col(InventarioDetalle.inventario_id).asc(), _col(InventarioDetalle.id).asc())
                    )
                )
                if inv_ids
                else []
            )
            return InventoryExportPayload(headers=headers, details=details, items=self._items_for_records(session, details))

    def export_payload_serializable(self, *, almacen_id: str = "", selected_id: str = "") -> ApiInventoryExportPayload:
        payload = self.export_payload(almacen_id=almacen_id, selected_id=selected_id)
        return ApiInventoryExportPayload(
            headers=InventoryHeaderRead.list_from_entities(payload.headers),
            details=InventoryDetailRead.list_from_entities(payload.details),
        )

    def _items_for_records(self, session: Session, records: list[Any]) -> list[IngredienteIreks]:
        articulo_ids = sorted(
            {
                str(getattr(x, "articulo_id", "") or "").strip()
                for x in records
                if str(getattr(x, "articulo_id", "") or "").strip()
            }
        )
        if not articulo_ids:
            return []
        return list(session.exec(select(IngredienteIreks).where(_col(IngredienteIreks.articulo_id).in_(articulo_ids))))
