from __future__ import annotations

from datetime import date, datetime
import json
from math import isfinite

from sqlmodel import Session, select

from app.core.database import engine
from app.models import (
    AlbaranItem, AlmacenMovimiento, Pedido, PedidoFaltante, PedidoIncidencia,
    PedidoIncidenciaImagen, PedidoRecepcionRevision, PedidoRecepcionReparto, PedidoRecepcionAsignacion, PedidoFaltanteMovimiento,
)
from app.services.order_query_service import OrderQueryService
from app.services.order_receipt_assignment_service import (
    receipt_fingerprint, save_receipt_split, sync_receipt_pending,
)


SHORTAGE_STATES = {
    "pendiente": "Pendiente de comprobar", "confirmado": "Recepción confirmada",
    "reclamada": "Reclamada", "resuelta": "Resuelta",
}


class OrderShortageService:
    def __init__(self, *, db_engine=None):
        self.engine = db_engine if db_engine is not None else engine

    def list_for_order(self, pedido_id: str) -> dict[str, PedidoFaltante]:
        with Session(self.engine) as session:
            return {row.incidencia_id: row for row in session.exec(
                select(PedidoFaltante).join(PedidoIncidencia)
                .where(PedidoIncidencia.pedido_id == pedido_id))}

    def create(self, *, pedido_id: str, item_id: str, received: float,
               observations: str, incident_date: date) -> str:
        with Session(self.engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            item = session.get(AlbaranItem, item_id)
            if item is None or item.pedido_id != pedido_id:
                raise ValueError("Selecciona una línea del albarán de este pedido.")
            if incident_date < item.albaran_fecha:
                raise ValueError("La fecha del recuento no puede ser anterior al albarán.")
            if session.exec(select(PedidoFaltante).where(PedidoFaltante.albaran_item_id == item_id)).first():
                raise ValueError("Esta línea ya tiene un faltante registrado. Abre su seguimiento.")
            if session.exec(select(PedidoFaltante).where(PedidoFaltante.reposicion_item_id == item_id)).first():
                raise ValueError("Esta recepción ya justifica una reposición. Revisa su seguimiento antes de registrar otro faltante.")
            missing = item.articulo_cantidad - received
            if (not isfinite(received) or received < 0 or not isfinite(missing)
                    or missing <= 0 or not float(missing).is_integer()):
                raise ValueError("El faltante debe ser un número entero de unidades mayor que cero.")
            if not observations.strip():
                raise ValueError("Describe el recuento del almacén.")
            incident = PedidoIncidencia(pedido_id=pedido_id, albaran_item_id=item_id,
                unidades_afectadas=int(missing), observaciones=observations.strip(), fecha_incidencia=incident_date)
            session.add(incident)
            session.flush()
            shortage = PedidoFaltante(incidencia_id=incident.incidencia_id, albaran_item_id=item_id,
                cantidad_documentada=item.articulo_cantidad, cantidad_recibida=received,
                huella=receipt_fingerprint(item))
            self._history(shortage, "Registrada", observations.strip())
            session.add(shortage)
            session.commit()
            return incident.incidencia_id

    @staticmethod
    def _history(shortage: PedidoFaltante, action: str, detail: str) -> None:
        entries = json.loads(shortage.historial)
        entries.append({"fecha": datetime.now().isoformat(timespec="seconds"), "accion": action, "detalle": detail})
        shortage.historial = json.dumps(entries, ensure_ascii=False)

    @staticmethod
    def _load(session: Session, incident_id: str):
        shortage = session.get(PedidoFaltante, incident_id)
        incident = session.get(PedidoIncidencia, incident_id)
        item = session.get(AlbaranItem, shortage.albaran_item_id) if shortage else None
        if shortage is None or incident is None or item is None:
            raise ValueError("El faltante o su línea ya no existe.")
        if shortage.huella != receipt_fingerprint(item):
            raise ValueError("El albarán ha cambiado. Revisa el faltante antes de continuar.")
        return shortage, incident, item

    def update_count(self, incident_id: str, received: float, reason: str) -> None:
        with Session(self.engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            shortage, incident, item = self._load(session, incident_id)
            missing = shortage.cantidad_documentada - received
            if shortage.estado != "pendiente":
                raise ValueError("Solo se puede corregir el recuento antes de confirmar la recepción.")
            if (not isfinite(received) or received < 0 or missing <= 0 or not float(missing).is_integer()
                    or not reason.strip()):
                raise ValueError("Indica un faltante entero mayor que cero y el motivo de la corrección.")
            self._history(shortage, "Recuento corregido", f"{shortage.cantidad_recibida:g} → {received:g} uds.; {reason.strip()}")
            shortage.cantidad_recibida = received
            incident.unidades_afectadas = int(missing)
            session.add(shortage)
            session.add(incident)
            session.commit()

    @staticmethod
    def _allocations(session: Session, item: AlbaranItem) -> dict[str, float]:
        allocations: dict[str, dict[str, float]] = {}
        OrderQueryService()._build_operational_assignment(session, item.pedido_id, receipt_allocations=allocations)
        return allocations.get(item.item_id, {})

    def confirm(self, incident_id: str, *, expected_received: float | None = None) -> None:
        with Session(self.engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            shortage, incident, item = self._load(session, incident_id)
            if expected_received is not None and shortage.cantidad_recibida != expected_received:
                raise ValueError("El recuento ha cambiado. Vuelve a abrir el seguimiento antes de confirmar.")
            if shortage.confirmado or shortage.estado == "resuelta":
                raise ValueError("El faltante ya se ha confirmado o resuelto.")
            if session.exec(select(PedidoIncidenciaImagen).where(
                    PedidoIncidenciaImagen.incidencia_id == incident_id)).first() is None:
                raise ValueError("Adjunta el justificante del almacén antes de confirmar.")
            self._adjust(session, shortage, incident, item, shortage.cantidad_recibida)
            shortage.confirmado = True
            shortage.estado = "confirmado"
            session.add(shortage)
            sync_receipt_pending(session, incident.pedido_id)
            session.commit()

    def _adjust(self, session: Session, shortage: PedidoFaltante, incident: PedidoIncidencia,
                item: AlbaranItem, quantity: float) -> None:
        previous = item.cantidad_operativa
        delta = quantity - previous
        allocations = self._allocations(session, item)
        old_allocations = dict(allocations)
        if allocations.get(incident.pedido_id, 0) + delta < -1e-6:
            raise ValueError("El faltante supera las unidades asignadas a este pedido. Revisa la asignación de recepción.")
        review = session.get(PedidoRecepcionRevision, item.item_id)
        if review and (review.estado in {"pendiente", "parcial"} or review.huella != receipt_fingerprint(item)):
            raise ValueError("Revisa y confirma la asignación de esta recepción antes de corregirla.")
        excess = previous - sum(allocations.values())
        if excess < -1e-6:
            raise ValueError("La asignación de recepción es inconsistente.")
        allocations[incident.pedido_id] = max(0.0, allocations.get(incident.pedido_id, 0) + delta)
        order = session.get(Pedido, incident.pedido_id)
        movements = list(session.exec(select(AlmacenMovimiento).where(AlmacenMovimiento.albaran_item_id == item.item_id)))
        if (order is None or not movements or any(
                m.almacen_id != order.almacen_id or m.articulo_id != item.articulo_id
                or m.articulo_lote != item.articulo_lote or m.articulo_caducidad != item.articulo_caducidad
                for m in movements) or abs(sum(m.cantidad for m in movements) - previous) > 1e-6):
            raise ValueError("La entrada de stock no coincide con esta línea. Revisa su vinculación antes de confirmar.")
        item.cantidad_recibida_confirmada = quantity
        session.add(item)
        if review is None:
            review = PedidoRecepcionRevision(albaran_item_id=item.item_id, estado="confirmado", excedente=excess)
            for pid, amount in old_allocations.items():
                session.add(PedidoRecepcionReparto(albaran_item_id=item.item_id, pedido_id=pid, cantidad=amount))
            legacy = session.get(PedidoRecepcionAsignacion, item.item_id)
            if legacy:
                session.delete(legacy)
        # Preserve the previous allocation as the basis for the existing capacity checks.
        if review:
            review.huella = receipt_fingerprint(item)
            session.add(review)
        session.flush()
        save_receipt_split(session, item, allocations, max(0.0, excess),
            fingerprint=receipt_fingerprint(item), version=review.version if review else 0)
        movement = AlmacenMovimiento(almacen_id=order.almacen_id, articulo_id=item.articulo_id,
            pedido_numero=order.pedido_numero, pedido_albaran_numero=item.albaran_numero,
            cantidad=delta, articulo_lote=item.articulo_lote, articulo_caducidad=item.articulo_caducidad,
            fecha_pedido=item.albaran_fecha, albaran_item_id=item.item_id)
        session.add(movement)
        session.flush()
        session.add(PedidoFaltanteMovimiento(movimiento_id=movement.id, incidencia_id=incident.incidencia_id))
        shortage.huella = receipt_fingerprint(item)
        numbers = {p.pedido_id: p.pedido_numero or "Sin número" for p in session.exec(
            select(Pedido).where(Pedido.pedido_id.in_(list(allocations))))}
        before_text = "; ".join(f"pedido {numbers.get(pid, 'Sin número')}: {qty:g} uds." for pid, qty in old_allocations.items())
        after_text = "; ".join(f"pedido {numbers.get(pid, 'Sin número')}: {qty:g} uds." for pid, qty in allocations.items())
        self._history(shortage, "Corrección de recepción",
            f"{previous:g} → {quantity:g} uds.; ajuste de stock {delta:+g}; movimiento {movement.id}; "
            f"asignación anterior: {before_text}; asignación resultante: {after_text}")
        session.add(shortage)

    def mark_claimed(self, incident_id: str, reference: str) -> None:
        if not reference.strip():
            raise ValueError("Indica la referencia o el detalle de la reclamación.")
        with Session(self.engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            shortage, incident, item = self._load(session, incident_id)
            if shortage.estado != "confirmado":
                raise ValueError("Confirma primero la recepción; la reclamación no se puede repetir.")
            shortage.estado = "reclamada"
            self._history(shortage, "Reclamada", reference.strip())
            session.add(shortage)
            session.commit()

    def replacement_options(self, incident_id: str) -> list[AlbaranItem]:
        with Session(self.engine) as session:
            shortage, incident, item = self._load(session, incident_id)
            order = session.get(Pedido, incident.pedido_id)
            return list(session.exec(select(AlbaranItem).join(Pedido, Pedido.pedido_id == AlbaranItem.pedido_id)
                .where(Pedido.almacen_id == order.almacen_id, AlbaranItem.articulo_id == item.articulo_id,
                    AlbaranItem.item_id != item.item_id, AlbaranItem.albaran_fecha >= incident.fecha_incidencia)
                .order_by(AlbaranItem.albaran_fecha, AlbaranItem.albaran_numero)))

    def resolve(self, incident_id: str, resolution: str, reference: str, replacement_id: str = "") -> None:
        if resolution not in {"reposicion", "abono", "error_recuento"} or not reference.strip():
            raise ValueError("Selecciona una solución e indica su justificante o referencia.")
        with Session(self.engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            shortage, incident, item = self._load(session, incident_id)
            if shortage.estado == "resuelta":
                raise ValueError("La incidencia ya está resuelta.")
            if not shortage.confirmado and resolution != "error_recuento":
                raise ValueError("Confirma primero la recepción real.")
            missing = shortage.cantidad_documentada - shortage.cantidad_recibida
            if resolution == "error_recuento" and shortage.confirmado:
                self._adjust(session, shortage, incident, item, shortage.cantidad_documentada)
            elif resolution == "abono":
                _, stats, _ = OrderQueryService()._build_operational_assignment(session, incident.pedido_id)
                values = stats.get((incident.pedido_id, item.articulo_id), {})
                if values.get("ordered", 0) - values.get("received", 0) - values.get("cancelled", 0) < missing - 1e-6:
                    raise ValueError("El pedido ya no tiene ese faltante pendiente. Revisa las recepciones antes de cancelarlo.")
            elif resolution == "reposicion":
                replacement = session.get(AlbaranItem, replacement_id)
                target = session.get(Pedido, replacement.pedido_id) if replacement else None
                source = session.get(Pedido, incident.pedido_id)
                if (replacement is None or target is None or source is None or replacement.item_id == item.item_id
                        or target.almacen_id != source.almacen_id or replacement.articulo_id != item.articulo_id
                        or replacement.albaran_fecha < incident.fecha_incidencia):
                    raise ValueError("Selecciona una recepción posterior del mismo producto y almacén.")
                already_linked = sum(s.cantidad_documentada - s.cantidad_recibida for s in session.exec(
                    select(PedidoFaltante).join(PedidoIncidencia)
                    .where(PedidoFaltante.reposicion_item_id == replacement_id,
                           PedidoIncidencia.pedido_id == incident.pedido_id)))
                allocated = self._allocations(session, replacement).get(incident.pedido_id, 0)
                if allocated - already_linked < missing - 1e-6:
                    raise ValueError("La reposición no tiene suficientes unidades asignadas a este pedido y disponibles para vincular.")
                shortage.reposicion_item_id = replacement_id
            shortage.estado = "resuelta"
            shortage.resolucion = resolution
            shortage.referencia = reference.strip()
            label = {"reposicion": "Reposición recibida", "abono": "Abono y cancelación", "error_recuento": "Error de recuento"}[resolution]
            self._history(shortage, "Resuelta: " + label, reference.strip())
            session.add(shortage)
            session.flush()
            sync_receipt_pending(session, incident.pedido_id)
            session.commit()
