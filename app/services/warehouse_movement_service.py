from __future__ import annotations

from typing import Any, cast
from uuid import uuid4
from datetime import date

from sqlmodel import Session, select

from app.core.database import engine
from app.models import AlmacenMovimiento, Fabricante, Familia, IngredienteIreks, Subfamilia
from app.schemas.warehouse import WarehouseManualMovementCreate, WarehouseMovementRead


def _col(expr: object) -> Any:
    return cast(Any, expr)


class WarehouseStockConflictError(ValueError):
    """Raised when a movement conflicts with current warehouse stock."""


class WarehouseMovementService:
    def expiration_payload(self, almacen_id: str = "") -> tuple[list[AlmacenMovimiento], list[IngredienteIreks]]:
        with Session(engine) as session:
            query = select(AlmacenMovimiento).where(_col(AlmacenMovimiento.articulo_caducidad).is_not(None))
            if almacen_id:
                query = query.where(AlmacenMovimiento.almacen_id == almacen_id)
            moves = list(
                session.exec(
                    query.order_by(
                        _col(AlmacenMovimiento.articulo_caducidad).asc(),
                        _col(AlmacenMovimiento.fecha_pedido).desc(),
                        _col(AlmacenMovimiento.id).desc(),
                    )
                )
            )
            return moves, self._items_for_moves(session, moves)

    def movement_payload(
        self, *, almacen_id: str = "", mode: str = "all"
    ) -> tuple[
        list[AlmacenMovimiento],
        list[IngredienteIreks],
        list[tuple[str | None, str | None]],
        list[tuple[str | None, str | None]],
        list[tuple[str | None, str | None]],
    ]:
        with Session(engine) as session:
            stmt = select(AlmacenMovimiento)
            if almacen_id:
                stmt = stmt.where(AlmacenMovimiento.almacen_id == almacen_id)
            if mode == "out":
                stmt = stmt.where(_col(AlmacenMovimiento.cantidad) < 0)
            elif mode == "in":
                stmt = stmt.where(_col(AlmacenMovimiento.cantidad) > 0)
            moves = list(
                session.exec(
                    stmt.order_by(
                        _col(AlmacenMovimiento.fecha_pedido).desc(),
                        _col(AlmacenMovimiento.id).desc(),
                    )
                )
            )
            items = self._items_for_moves(session, moves)
            manufacturer_rows = list(session.exec(select(Fabricante.fabricante_id, Fabricante.fabricante_nombre)))
            family_rows = list(session.exec(select(Familia.articulo_familia_id, Familia.articulo_familia_nombre)))
            subfamily_rows = list(
                session.exec(select(Subfamilia.articulo_subfamilia_id, Subfamilia.articulo_subfamilia_nombre))
            )
        return moves, items, manufacturer_rows, family_rows, subfamily_rows

    def _items_for_moves(self, session: Session, moves: list[AlmacenMovimiento]) -> list[IngredienteIreks]:
        articulo_ids = sorted(
            {
                str(getattr(x, "articulo_id", "") or "").strip()
                for x in moves
                if str(getattr(x, "articulo_id", "") or "").strip()
            }
        )
        if not articulo_ids:
            return []
        return list(session.exec(select(IngredienteIreks).where(_col(IngredienteIreks.articulo_id).in_(articulo_ids))))

    def current_stock_for(
        self, *, almacen_id: str = "", articulo_id: str, lote: str = "", caducidad: date | None = None
    ) -> float:
        with Session(engine) as session:
            stmt = select(AlmacenMovimiento).where(AlmacenMovimiento.articulo_id == articulo_id)
            if almacen_id:
                stmt = stmt.where(AlmacenMovimiento.almacen_id == almacen_id)
            if lote:
                stmt = stmt.where(AlmacenMovimiento.articulo_lote == lote)
            rows = list(session.exec(stmt))
        total = 0.0
        for row in rows:
            row_cad = getattr(row, "articulo_caducidad", None)
            if caducidad and row_cad and row_cad != caducidad:
                continue
            total += float(getattr(row, "cantidad", 0.0) or 0.0)
        return total

    def article_options(self, almacen_id: str = "") -> list[tuple[str, str, str]]:
        with Session(engine) as session:
            stmt = select(IngredienteIreks)
            if almacen_id:
                stmt = stmt.where(IngredienteIreks.almacen_id == almacen_id)
            items = list(
                session.exec(
                    stmt.order_by(IngredienteIreks.articulo_referencia_corta, IngredienteIreks.articulo_descripcion)
                )
            )
        result: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for item in items:
            articulo_id = str(getattr(item, "articulo_id", "") or "").strip()
            if not articulo_id or articulo_id in seen:
                continue
            seen.add(articulo_id)
            ref = str(getattr(item, "articulo_referencia_corta", "") or "").strip() or articulo_id
            nombre = str(getattr(item, "articulo_descripcion", "") or "").strip()
            result.append((articulo_id, ref, nombre))
        return result

    def reverse_manual_move(self, mov: AlmacenMovimiento) -> None:
        qty = float(getattr(mov, "cantidad", 0.0) or 0.0)
        reverse = AlmacenMovimiento(
            almacen_id=str(getattr(mov, "almacen_id", "") or "").strip(),
            articulo_id=str(getattr(mov, "articulo_id", "") or "").strip(),
            pedido_numero=f"MANUAL-REV-{date.today().strftime('%Y%m%d')}",
            pedido_albaran_numero=f"MANUAL-REV|REF:{int(getattr(mov, 'id', 0) or 0)}",
            cantidad=-qty,
            articulo_lote=str(getattr(mov, "articulo_lote", "") or "").strip(),
            articulo_caducidad=getattr(mov, "articulo_caducidad", None),
            fecha_pedido=date.today(),
            albaran_item_id=str(uuid4()),
        )
        with Session(engine) as session:
            session.add(reverse)
            session.commit()

    def save_manual_move(
        self,
        *,
        payload: dict[str, Any],
        mode: str,
        almacen_id: str,
        existing: AlmacenMovimiento | None,
        fecha_pedido: date,
        caducidad: date | None,
        albaran: str,
    ) -> AlmacenMovimiento:
        articulo_id = str(payload.get("articulo_id") or "").strip()
        if not articulo_id:
            raise ValueError("Articulo_ID es obligatorio.")
        cantidad_raw = str(payload.get("cantidad") or "").strip().replace(",", ".")
        try:
            cantidad_abs = abs(float(cantidad_raw))
        except Exception:
            raise ValueError("Cantidad no valida.") from None
        if cantidad_abs <= 0:
            raise ValueError("La cantidad debe ser mayor que 0.")
        lote = str(payload.get("articulo_lote") or "").strip()
        cantidad_signed = cantidad_abs if mode == "in" else -cantidad_abs
        if mode == "out":
            stock = self.current_stock_for(
                almacen_id=almacen_id,
                articulo_id=articulo_id,
                lote=lote,
                caducidad=caducidad,
            )
            if existing is not None:
                stock -= float(getattr(existing, "cantidad", 0.0) or 0.0)
            if stock + cantidad_signed < -0.0001:
                raise WarehouseStockConflictError("La salida manual dejaria stock negativo para ese producto/lote.")
        with Session(engine) as session:
            if existing is None:
                row = AlmacenMovimiento(
                    almacen_id=almacen_id,
                    articulo_id=articulo_id,
                    pedido_numero=f"MANUAL-{date.today().strftime('%Y%m%d')}",
                    pedido_albaran_numero=albaran,
                    cantidad=cantidad_signed,
                    articulo_lote=lote,
                    articulo_caducidad=caducidad,
                    fecha_pedido=fecha_pedido,
                    albaran_item_id=str(uuid4()),
                )
                session.add(row)
            else:
                current = session.get(AlmacenMovimiento, int(getattr(existing, "id", 0) or 0))
                if current is None:
                    raise ValueError("No se encontro el movimiento para editar.")
                current.articulo_id = articulo_id
                current.cantidad = cantidad_signed
                current.articulo_lote = lote
                current.articulo_caducidad = caducidad
                current.fecha_pedido = fecha_pedido
                current.pedido_albaran_numero = albaran
                session.add(current)
                row = current
            session.commit()
            session.refresh(row)
            return row

    def create_manual_move_from_payload(self, payload: WarehouseManualMovementCreate | dict) -> WarehouseMovementRead:
        data = self._payload_dict(payload, WarehouseManualMovementCreate)
        mode = str(data.get("mode") or "in").strip().lower()
        if mode not in {"in", "out"}:
            raise ValueError("Modo de movimiento no valido.")
        row = self.save_manual_move(
            payload={
                "articulo_id": data["articulo_id"],
                "cantidad": data["cantidad"],
                "articulo_lote": data.get("articulo_lote", ""),
            },
            mode=mode,
            almacen_id=str(data["almacen_id"]),
            existing=None,
            fecha_pedido=data["fecha_pedido"],
            caducidad=data.get("articulo_caducidad"),
            albaran=str(data.get("pedido_albaran_numero") or ""),
        )
        return WarehouseMovementRead.from_entity(row)

    @staticmethod
    def _payload_dict(payload: object, schema_cls: type) -> dict:
        if isinstance(payload, dict):
            model = schema_cls.model_validate(payload)
        else:
            model = schema_cls.model_validate(payload)
        return model.model_dump()
