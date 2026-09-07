from __future__ import annotations

from math import isfinite

from sqlmodel import Session, select

from app.models import Albaran, AlbaranItem, Pedido, PedidoItem, PedidoRecepcionAsignacion


def assign_order_receipt(session: Session, albaran_item_id: str, pedido_id: str) -> None:
    """Assign a complete delivery line within the caller's transaction."""
    item = session.get(AlbaranItem, albaran_item_id)
    target = session.get(Pedido, pedido_id)
    source = session.get(Pedido, item.pedido_id) if item else None
    delivery = session.get(Albaran, item.albaran_id) if item else None
    if not item or not target or not source or not delivery:
        raise ValueError("Delivery line, document and orders must exist")
    if not target.almacen_id or target.almacen_id != source.almacen_id:
        raise ValueError("Orders must belong to the same warehouse")
    if target.pedido_fecha > delivery.albaran_fecha:
        raise ValueError("The destination order cannot be later than the delivery")
    quantity = float(item.articulo_cantidad)
    ordered = sum(float(row.articulo_cantidad) for row in session.exec(
        select(PedidoItem).where(PedidoItem.pedido_id == pedido_id, PedidoItem.articulo_id == item.articulo_id)
    ))
    reserved = sum(float(row.articulo_cantidad) for row in session.exec(
        select(AlbaranItem)
        .join(PedidoRecepcionAsignacion, PedidoRecepcionAsignacion.albaran_item_id == AlbaranItem.item_id)
        .where(PedidoRecepcionAsignacion.pedido_id == pedido_id,
               AlbaranItem.articulo_id == item.articulo_id, AlbaranItem.item_id != albaran_item_id)
    ))
    if not isfinite(quantity) or quantity <= 0 or quantity + reserved > ordered + 1e-9:
        raise ValueError("Assigned quantity must be positive and cannot exceed ordered units")
    assignment = session.get(PedidoRecepcionAsignacion, albaran_item_id)
    if assignment is None:
        assignment = PedidoRecepcionAsignacion(albaran_item_id=albaran_item_id, pedido_id=pedido_id)
    else:
        assignment.pedido_id = pedido_id
    session.add(assignment)
    session.flush()
