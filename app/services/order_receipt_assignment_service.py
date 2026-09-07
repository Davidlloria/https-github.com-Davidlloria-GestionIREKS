from __future__ import annotations

from math import isfinite
from dataclasses import dataclass
from datetime import date
import hashlib
import json

from sqlmodel import Session, select

from app.models import Albaran, AlbaranItem, Pedido, PedidoItem, PedidoRecepcionAsignacion
from app.models import IngredienteIreks, PedidoRecepcionRevision, PedidoRecepcionReparto, PedidoRecepcionCambio
from app.models import PedidoPendiente
from app.core.database import engine


def receipt_fingerprint(item: AlbaranItem) -> str:
    values = [item.pedido_id, item.albaran_id, item.articulo_id, item.articulo_codigo,
              item.articulo_cantidad, str(item.albaran_fecha), item.articulo_lote, str(item.articulo_caducidad)]
    return hashlib.sha256(json.dumps(values, ensure_ascii=True).encode()).hexdigest()


@dataclass
class ReceiptCandidate:
    pedido_id: str
    numero: str
    fecha: date
    pendiente: float


@dataclass
class ReceiptReview:
    item_id: str
    albaran: str
    articulo: str
    cantidad: float
    pendiente: bool
    huella: str
    version: int
    candidates: list[ReceiptCandidate]
    allocations: dict[str, float]
    excess: float
    history: list[str]


def receipt_candidates(session: Session, item: AlbaranItem) -> list[ReceiptCandidate]:
    from app.services.order_query_service import OrderQueryService
    _, stats, orders = OrderQueryService()._build_operational_assignment(session, item.pedido_id)
    own: dict[str, float] = {}
    review = session.get(PedidoRecepcionRevision, item.item_id)
    if review and review.estado != "pendiente" and review.huella == receipt_fingerprint(item):
        own = {r.pedido_id: r.cantidad for r in session.exec(select(PedidoRecepcionReparto).where(
            PedidoRecepcionReparto.albaran_item_id == item.item_id))}
    elif review is None:
        legacy = session.get(PedidoRecepcionAsignacion, item.item_id)
        if legacy:
            own = {legacy.pedido_id: item.articulo_cantidad}
    delivered = set(session.exec(select(Albaran.pedido_id)))
    result = []
    for (pid, article_id), values in stats.items():
        order = orders[pid]
        remaining = min(values["ordered"], values["ordered"] - values["received"] + own.get(pid, 0))
        if (article_id == item.articulo_id and remaining > 1e-9
                and order.pedido_fecha <= item.albaran_fecha
                and (pid in delivered or pid == item.pedido_id)):
            result.append(ReceiptCandidate(pid, order.pedido_numero or "Sin número", order.pedido_fecha, remaining))
    return result


def track_receipt(session: Session, item: AlbaranItem) -> None:
    if session.get(PedidoRecepcionRevision, item.item_id) is None:
        session.add(PedidoRecepcionRevision(albaran_item_id=item.item_id, huella=receipt_fingerprint(item)))
        session.flush()


def save_receipt_split(session: Session, item: AlbaranItem, allocations: dict[str, float], excess: float,
                       *, fingerprint: str, version: int, automatic: bool = False) -> None:
    review = session.get(PedidoRecepcionRevision, item.item_id)
    if fingerprint != receipt_fingerprint(item) or version != (review.version if review else 0):
        raise ValueError("La recepción ha cambiado. Vuelve a abrirla para revisar los datos.")
    values = [*allocations.values(), excess]
    if any(not isfinite(v) or v < 0 for v in values):
        raise ValueError("Las cantidades deben ser positivas o cero.")
    if abs(sum(values) - item.articulo_cantidad) > 1e-6:
        raise ValueError("Reparte todas las unidades recibidas o indica el excedente.")
    capacities = {row.pedido_id: row.pendiente for row in receipt_candidates(session, item)}
    for pid, amount in allocations.items():
        if amount > capacities.get(pid, 0) + 1e-6:
            raise ValueError("La asignación supera el pendiente disponible. Actualiza la recepción.")
    before = [(r.pedido_id, r.cantidad) for r in session.exec(select(PedidoRecepcionReparto).where(
        PedidoRecepcionReparto.albaran_item_id == item.item_id))]
    for row in list(session.exec(select(PedidoRecepcionReparto).where(
            PedidoRecepcionReparto.albaran_item_id == item.item_id))):
        session.delete(row)
    legacy = session.get(PedidoRecepcionAsignacion, item.item_id)
    if legacy:
        before.append((legacy.pedido_id, item.articulo_cantidad))
        session.delete(legacy)
    session.flush()
    for pid, quantity in allocations.items():
        if quantity > 0:
            session.add(PedidoRecepcionReparto(albaran_item_id=item.item_id, pedido_id=pid, cantidad=quantity))
    if review is None:
        review = PedidoRecepcionRevision(albaran_item_id=item.item_id)
    previous_excess = review.excedente
    review.estado = "automatico" if automatic else "confirmado"
    review.huella = fingerprint
    review.excedente = excess
    review.version += 1
    session.add(review)
    names = {row.pedido_id: row.numero for row in receipt_candidates(session, item)}
    detail = {"tipo": review.estado, "antes": before, "excedente_antes": previous_excess,
              "despues": [(names.get(pid, pid), quantity) for pid, quantity in allocations.items() if quantity],
              "excedente": excess}
    session.add(PedidoRecepcionCambio(albaran_item_id=item.item_id, detalle=json.dumps(detail, ensure_ascii=False)))
    session.flush()


def automate_receipts(session: Session, pedido_id: str) -> None:
    for item in session.exec(select(AlbaranItem).where(AlbaranItem.pedido_id == pedido_id).order_by(AlbaranItem.item_id)):
        review = session.get(PedidoRecepcionRevision, item.item_id)
        if review is None:
            continue  # Existing history is not silently redistributed.
        if review.huella != receipt_fingerprint(item):
            continue  # Changed confirmed data always needs human review.
        if review.estado != "pendiente":
            continue
        candidates = receipt_candidates(session, item)
        if len(candidates) == 1 and 0 < item.articulo_cantidad <= candidates[0].pendiente + 1e-6:
            save_receipt_split(session, item, {candidates[0].pedido_id: item.articulo_cantidad}, 0,
                               fingerprint=receipt_fingerprint(item), version=review.version, automatic=True)


def sync_receipt_pending(session: Session, pedido_id: str) -> None:
    from app.services.order_query_service import OrderQueryService
    _, stats, orders = OrderQueryService()._build_operational_assignment(session, pedido_id)
    if not orders:
        return
    for row in list(session.exec(select(PedidoPendiente).where(
            PedidoPendiente.pedido_id.in_(list(orders)), PedidoPendiente.estado == "pendiente"))):
        session.delete(row)
    delivered = {row.pedido_id: row.albaran_id for row in session.exec(select(Albaran).where(
        Albaran.pedido_id.in_(list(orders))))}
    for (pid, article_id), values in stats.items():
        pending = values["ordered"] - values["received"]
        if pid in delivered and pending > 1e-9:
            session.add(PedidoPendiente(pedido_id=pid, albaran_id=delivered[pid], articulo_id=article_id,
                cantidad_pedida=values["ordered"], cantidad_recibida=values["received"],
                cantidad_pendiente=pending, estado="pendiente"))
    session.flush()


def reconcile_historical_receipts(session: Session, pedido_id: str) -> int:
    """Queue unresolved historical surplus without changing the source documents."""
    from app.services.order_query_service import OrderQueryService
    unresolved: dict[str, dict[str, float]] = {}
    query = OrderQueryService()
    _, before, orders = query._build_operational_assignment(session, pedido_id, unassigned_receipts=unresolved)
    for item_id, allocations in unresolved.items():
        item = session.get(AlbaranItem, item_id)
        track_receipt(session, item)
        review = session.get(PedidoRecepcionRevision, item_id)
        review.estado = "parcial" if allocations else "pendiente"
        session.add(review)
        legacy = session.get(PedidoRecepcionAsignacion, item_id)
        if legacy is not None:
            session.delete(legacy)
        for pid, amount in allocations.items():
            session.add(PedidoRecepcionReparto(albaran_item_id=item_id, pedido_id=pid, cantidad=amount))
        session.add(PedidoRecepcionCambio(albaran_item_id=item_id, detalle=json.dumps({
            "tipo": "Sobrante histórico pendiente de revisión",
            "despues": [(orders[pid].pedido_numero or "Sin número", qty) for pid, qty in allocations.items()],
            "excedente": 0,
        }, ensure_ascii=False)))
    session.flush()
    _, after, _ = query._build_operational_assignment(session, pedido_id)
    if before != after:
        raise ValueError("La revisión histórica alteraría asignaciones válidas; se cancela la operación.")
    sync_receipt_pending(session, pedido_id)
    return len(unresolved)


class ReceiptAssignmentService:
    def pending_count(self, almacen_id: str = "", pedido_id: str = "") -> int:
        with Session(engine) as session:
            query = (select(AlbaranItem, PedidoRecepcionRevision)
                     .join(PedidoRecepcionRevision, PedidoRecepcionRevision.albaran_item_id == AlbaranItem.item_id)
                     .join(Pedido, Pedido.pedido_id == AlbaranItem.pedido_id))
            if almacen_id:
                query = query.where(Pedido.almacen_id == almacen_id)
            if pedido_id:
                query = query.where(Pedido.pedido_id == pedido_id)
            return sum(review.estado in {"pendiente", "parcial"} or review.huella != receipt_fingerprint(item)
                       for item, review in session.exec(query))

    def list_reviews(self, almacen_id: str = "", pedido_id: str = "", pending_only: bool = True) -> list[ReceiptReview]:
        result = []
        with Session(engine) as session:
            query = select(AlbaranItem, Pedido).join(Pedido, Pedido.pedido_id == AlbaranItem.pedido_id)
            if almacen_id:
                query = query.where(Pedido.almacen_id == almacen_id)
            if pedido_id:
                query = query.where(Pedido.pedido_id == pedido_id)
            for item, _ in session.exec(query.order_by(AlbaranItem.albaran_fecha, AlbaranItem.item_id)):
                review = session.get(PedidoRecepcionRevision, item.item_id)
                legacy = session.get(PedidoRecepcionAsignacion, item.item_id)
                if not review and not legacy:
                    continue
                pending = bool(review and (review.estado in {"pendiente", "parcial"} or review.huella != receipt_fingerprint(item)))
                if pending_only and not pending:
                    continue
                article = session.exec(select(IngredienteIreks).where(
                    IngredienteIreks.articulo_id == item.articulo_id)).first()
                allocations = {r.pedido_id: r.cantidad for r in session.exec(select(PedidoRecepcionReparto).where(
                    PedidoRecepcionReparto.albaran_item_id == item.item_id))} if (
                        review and review.estado != "pendiente" and review.huella == receipt_fingerprint(item)) else {}
                if legacy and not review:
                    allocations = {legacy.pedido_id: item.articulo_cantidad}
                history = []
                for r in session.exec(
                    select(PedidoRecepcionCambio).where(PedidoRecepcionCambio.albaran_item_id == item.item_id)
                    .order_by(PedidoRecepcionCambio.fecha)):
                    detail = json.loads(r.detalle)
                    destination = "; ".join(f"Pedido {number}: {qty:g} uds." for number, qty in detail["despues"])
                    history.append(f"{r.fecha:%d/%m/%Y %H:%M} · {detail['tipo']} · {destination} · Excedente: {detail['excedente']:g}")
                result.append(ReceiptReview(item.item_id, item.albaran_numero,
                    article.articulo_descripcion if article else item.articulo_codigo or "Artículo sin identificar",
                    item.articulo_cantidad, pending, receipt_fingerprint(item), review.version if review else 0,
                    receipt_candidates(session, item), allocations, review.excedente if review and not pending else 0, history))
        return result

    def confirm(self, review: ReceiptReview, allocations: dict[str, float], excess: float) -> None:
        with Session(engine) as session:
            # Serialize confirmations so two dialogs cannot consume the same pending units.
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            item = session.get(AlbaranItem, review.item_id)
            if item is None:
                raise ValueError("La recepción ya no existe.")
            save_receipt_split(session, item, allocations, excess, fingerprint=review.huella, version=review.version)
            sync_receipt_pending(session, item.pedido_id)
            session.commit()


def assign_order_receipt(session: Session, albaran_item_id: str, pedido_id: str) -> None:
    """Assign a complete delivery line within the caller's transaction."""
    item = session.get(AlbaranItem, albaran_item_id)
    target = session.get(Pedido, pedido_id)
    source = session.get(Pedido, item.pedido_id) if item else None
    delivery = session.get(Albaran, item.albaran_id) if item else None
    if not item or not target or not source or not delivery:
        raise ValueError("Delivery line, document and orders must exist")
    review = session.get(PedidoRecepcionRevision, albaran_item_id)
    if review:
        save_receipt_split(session, item, {pedido_id: item.articulo_cantidad}, 0,
                           fingerprint=receipt_fingerprint(item), version=review.version)
        sync_receipt_pending(session, item.pedido_id)
        return
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
