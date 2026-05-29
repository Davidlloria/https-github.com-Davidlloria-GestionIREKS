from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlmodel import Session, select

from app.models import Distribuidor, IngredienteStd
from app.repositories.distributor_repository import DistributorRepository


class DistributorViewModel:
    def __init__(self, repository: DistributorRepository | None = None) -> None:
        self.repository = repository or DistributorRepository()

    def list(self, session: Session, term: str = "") -> list[Distribuidor]:
        return self.repository.search(session, term)

    def create(self, session: Session, payload: dict) -> Distribuidor:
        self._normalize_ids(payload, force=True)
        self._ensure_distribuidor_codigo(session, payload, force=True)
        entity = Distribuidor(**payload)
        return self.repository.create(session, entity)

    def update(self, session: Session, distribuidor_id: str, payload: dict) -> Distribuidor:
        self._normalize_ids(payload, force=False)
        self._ensure_distribuidor_codigo(session, payload, force=False)
        entity = self.repository.get_by_id(session, distribuidor_id)
        if not entity:
            raise ValueError("Distribuidor no encontrado")
        for key, value in payload.items():
            setattr(entity, key, value)
        return self.repository.update(session, entity)

    def delete(self, session: Session, distribuidor_id: str) -> bool:
        return self.repository.delete(session, distribuidor_id)

    def list_articles_by_distributor(self, session: Session, distribuidor_id: str) -> list[IngredienteStd]:
        if not distribuidor_id:
            return []
        stmt = (
            select(IngredienteStd)
            .where(IngredienteStd.distribuidor_id == distribuidor_id)
            .order_by(IngredienteStd.articulo_descripcion)
        )
        return list(session.exec(stmt))

    def _normalize_ids(self, payload: dict, force: bool) -> None:
        if not force and "distribuidor_id" not in payload:
            return
        distribuidor_id = (payload.get("distribuidor_id") or "").strip()
        payload["distribuidor_id"] = distribuidor_id or str(uuid4())

    def _ensure_distribuidor_codigo(self, session: Session, payload: dict, force: bool) -> None:
        if not force and "distribuidor_codigo" not in payload:
            return
        raw = payload.get("distribuidor_codigo")
        if raw not in (None, ""):
            try:
                value = int(str(raw).strip())
                if value > 0:
                    payload["distribuidor_codigo"] = value
                    return
            except ValueError:
                pass
        next_code = int(
            session.execute(text("SELECT COALESCE(MAX(distribuidor_codigo), 0) + 1 FROM distribuidores")).one()[0]
        )
        payload["distribuidor_codigo"] = next_code
