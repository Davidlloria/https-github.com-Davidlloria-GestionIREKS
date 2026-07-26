from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, select

from app.core.database import engine as default_engine
from app.models import ClienteAgenda


@dataclass(slots=True)
class CustomerAgendaService:
    engine: object = default_engine

    def related_agenda(self, cliente_id: str) -> list[ClienteAgenda]:
        clean_id = str(cliente_id or "").strip()
        if not clean_id:
            return []
        with Session(self.engine) as session:
            return list(
                session.exec(
                    select(ClienteAgenda)
                    .where(ClienteAgenda.cliente_id == clean_id)
                    .order_by(
                        ClienteAgenda.fecha_actividad.desc(),
                        ClienteAgenda.updated_at.desc(),
                        ClienteAgenda.created_at.desc(),
                    )
                )
            )

    def get_activity(self, agenda_id: str) -> ClienteAgenda | None:
        clean_id = str(agenda_id or "").strip()
        if not clean_id:
            return None
        with Session(self.engine) as session:
            return session.get(ClienteAgenda, clean_id)

    def create_activity(self, payload: dict) -> ClienteAgenda:
        with Session(self.engine) as session:
            activity = ClienteAgenda(
                cliente_id=str(payload.get("cliente_id") or "").strip(),
                fecha_actividad=self._coerce_date(payload.get("fecha_actividad"), default=date.today()),
                tipo=str(payload.get("tipo") or "nota").strip() or "nota",
                estado=str(payload.get("estado") or "pendiente").strip() or "pendiente",
                resumen=str(payload.get("resumen") or "").strip(),
                detalle=str(payload.get("detalle") or "").strip(),
                fecha_seguimiento=self._coerce_optional_date(payload.get("fecha_seguimiento")),
                prioridad=str(payload.get("prioridad") or "normal").strip() or "normal",
                responsable=str(payload.get("responsable") or "").strip(),
            )
            session.add(activity)
            session.commit()
            session.refresh(activity)
            return activity

    def update_activity(self, agenda_id: str, payload: dict) -> ClienteAgenda:
        clean_id = str(agenda_id or "").strip()
        if not clean_id:
            raise ValueError("Actividad no encontrada.")
        with Session(self.engine) as session:
            activity = session.get(ClienteAgenda, clean_id)
            if activity is None:
                raise ValueError("Actividad no encontrada.")
            activity.fecha_actividad = self._coerce_date(
                payload.get("fecha_actividad"), default=activity.fecha_actividad or date.today()
            )
            activity.tipo = str(payload.get("tipo") or activity.tipo or "nota").strip() or "nota"
            activity.estado = str(payload.get("estado") or activity.estado or "pendiente").strip() or "pendiente"
            activity.resumen = str(payload.get("resumen") or "").strip()
            activity.detalle = str(payload.get("detalle") or "").strip()
            activity.fecha_seguimiento = self._coerce_optional_date(payload.get("fecha_seguimiento"))
            activity.prioridad = str(payload.get("prioridad") or activity.prioridad or "normal").strip() or "normal"
            activity.responsable = str(payload.get("responsable") or "").strip()
            session.add(activity)
            session.commit()
            session.refresh(activity)
            return activity

    def upsert_activity(self, agenda_id: str, payload: dict) -> ClienteAgenda:
        clean_id = str(agenda_id or "").strip()
        if clean_id:
            return self.update_activity(clean_id, payload)
        return self.create_activity(payload)

    def delete_activity(self, agenda_id: str) -> bool:
        clean_id = str(agenda_id or "").strip()
        if not clean_id:
            return False
        with Session(self.engine) as session:
            activity = session.get(ClienteAgenda, clean_id)
            if activity is None:
                return False
            session.delete(activity)
            session.commit()
            return True

    @staticmethod
    def _coerce_date(value: object, *, default: date) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        if not text:
            return default
        try:
            return date.fromisoformat(text)
        except ValueError:
            return default

    @staticmethod
    def _coerce_optional_date(value: object) -> date | None:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
