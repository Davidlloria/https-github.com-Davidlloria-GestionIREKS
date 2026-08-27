from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.core.database import engine
from app.models import Cliente, IngredienteIreks, PromocionClienteProducto, RecetaLinea


@dataclass(frozen=True)
class CustomerProductPromotionRow:
    promotion: PromocionClienteProducto
    product: IngredienteIreks


class CustomerProductPromotionService:
    def __init__(self, *, db_engine: Any | None = None) -> None:
        self.engine = db_engine or engine

    def list_for_customer(self, cliente_id: str) -> list[CustomerProductPromotionRow]:
        customer_id = str(cliente_id or "").strip()
        if not customer_id:
            return []
        with Session(self.engine) as session:
            rows = list(
                session.exec(
                    select(PromocionClienteProducto, IngredienteIreks)
                    .join(IngredienteIreks, col(IngredienteIreks.id) == col(PromocionClienteProducto.producto_ireks_id))
                    .where(col(PromocionClienteProducto.cliente_id) == customer_id)
                    .order_by(col(PromocionClienteProducto.activa).desc(), col(IngredienteIreks.articulo_descripcion))
                )
            )
        return [CustomerProductPromotionRow(promotion=row[0], product=row[1]) for row in rows]

    def save(
        self,
        *,
        cliente_id: str,
        producto_ireks_id: int,
        unidades_compra: int,
        unidades_sin_cargo: int,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        activa: bool = True,
        observaciones: str = "",
        promotion_id: int | None = None,
    ) -> PromocionClienteProducto:
        customer_id = str(cliente_id or "").strip()
        buy = int(unidades_compra or 0)
        free = int(unidades_sin_cargo or 0)
        product_id = int(producto_ireks_id or 0)
        if not customer_id:
            raise ValueError("El cliente es obligatorio.")
        if product_id <= 0:
            raise ValueError("El producto IREKS es obligatorio.")
        if buy <= 0 or free <= 0:
            raise ValueError("Las unidades compradas y sin cargo deben ser mayores que cero.")
        if fecha_desde and fecha_hasta and fecha_hasta < fecha_desde:
            raise ValueError("La fecha hasta no puede ser anterior a la fecha desde.")

        with Session(self.engine) as session:
            if session.get(Cliente, customer_id) is None:
                raise ValueError("Cliente no encontrado.")
            if session.get(IngredienteIreks, product_id) is None:
                raise ValueError("Producto IREKS no encontrado.")
            self._ensure_no_overlap(
                session,
                cliente_id=customer_id,
                producto_ireks_id=product_id,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                activa=bool(activa),
                exclude_id=promotion_id,
            )
            promotion = session.get(PromocionClienteProducto, promotion_id) if promotion_id else None
            if promotion_id and promotion is None:
                raise ValueError("Promoción no encontrada.")
            if promotion is None:
                promotion = PromocionClienteProducto(cliente_id=customer_id, producto_ireks_id=product_id)
            promotion.cliente_id = customer_id
            promotion.producto_ireks_id = product_id
            promotion.unidades_compra = buy
            promotion.unidades_sin_cargo = free
            promotion.fecha_desde = fecha_desde
            promotion.fecha_hasta = fecha_hasta
            promotion.activa = bool(activa)
            promotion.observaciones = str(observaciones or "").strip()
            promotion.updated_at = datetime.now(UTC)
            session.add(promotion)
            session.commit()
            session.refresh(promotion)
            return promotion

    def delete(self, promotion_id: int) -> bool:
        with Session(self.engine) as session:
            promotion = session.get(PromocionClienteProducto, int(promotion_id or 0))
            if promotion is None:
                return False
            session.delete(promotion)
            session.commit()
            return True

    def apply_to_lines(
        self,
        cliente_id: str | None,
        lineas: list[RecetaLinea],
        *,
        on_date: date | None = None,
    ) -> list[RecetaLinea]:
        customer_id = str(cliente_id or "").strip()
        target_date = on_date or date.today()
        promotions = self._active_by_product(customer_id, target_date) if customer_id else {}
        for line in lineas:
            line.promocion_id_snapshot = None
            line.promocion_compra_snapshot = 0
            line.promocion_sin_cargo_snapshot = 0
            line.precio_kg_efectivo_snapshot = float(line.precio_kg_snapshot or 0.0)
            line.coste_sin_promocion = 0.0
            line.ahorro_promocion = 0.0
            if str(line.tipo_origen or "").strip().lower() != "ireks" or not line.ingrediente_id:
                continue
            promotion = promotions.get(int(line.ingrediente_id))
            if promotion is None:
                continue
            buy = int(promotion.unidades_compra or 0)
            free = int(promotion.unidades_sin_cargo or 0)
            if buy <= 0 or free <= 0:
                continue
            line.promocion_id_snapshot = promotion.id
            line.promocion_compra_snapshot = buy
            line.promocion_sin_cargo_snapshot = free
            line.precio_kg_efectivo_snapshot = float(line.precio_kg_snapshot or 0.0) * buy / (buy + free)
        return lineas

    def _active_by_product(self, cliente_id: str, on_date: date) -> dict[int, PromocionClienteProducto]:
        with Session(self.engine) as session:
            rows = list(
                session.exec(
                    select(PromocionClienteProducto)
                    .where(
                        col(PromocionClienteProducto.cliente_id) == cliente_id,
                        col(PromocionClienteProducto.activa).is_(True),
                    )
                    .order_by(col(PromocionClienteProducto.updated_at).desc(), col(PromocionClienteProducto.id).desc())
                )
            )
        result: dict[int, PromocionClienteProducto] = {}
        for row in rows:
            if row.fecha_desde and on_date < row.fecha_desde:
                continue
            if row.fecha_hasta and on_date > row.fecha_hasta:
                continue
            result.setdefault(int(row.producto_ireks_id), row)
        return result

    def _ensure_no_overlap(
        self,
        session: Session,
        *,
        cliente_id: str,
        producto_ireks_id: int,
        fecha_desde: date | None,
        fecha_hasta: date | None,
        activa: bool,
        exclude_id: int | None,
    ) -> None:
        if not activa:
            return
        rows = list(
            session.exec(
                select(PromocionClienteProducto).where(
                    col(PromocionClienteProducto.cliente_id) == cliente_id,
                    col(PromocionClienteProducto.producto_ireks_id) == producto_ireks_id,
                    col(PromocionClienteProducto.activa).is_(True),
                )
            )
        )
        start = fecha_desde or date.min
        end = fecha_hasta or date.max
        for row in rows:
            if exclude_id and row.id == exclude_id:
                continue
            other_start = row.fecha_desde or date.min
            other_end = row.fecha_hasta or date.max
            if start <= other_end and other_start <= end:
                raise ValueError("Ya existe una promoción activa solapada para este cliente y producto.")


__all__ = ["CustomerProductPromotionRow", "CustomerProductPromotionService"]
