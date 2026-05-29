from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlmodel import Session, select

from app.models import IngredienteStd, Proveedor
from app.repositories.provider_repository import ProviderRepository


class ProviderViewModel:
    def __init__(self, repository: ProviderRepository | None = None) -> None:
        self.repository = repository or ProviderRepository()

    def list(self, session: Session, term: str = "") -> list[Proveedor]:
        return self.repository.search(session, term)

    def create(self, session: Session, payload: dict) -> Proveedor:
        payload = self._normalize_payload(payload)
        payload.pop("proveedor_codigo", None)
        payload.pop("distribuidor_codigo", None)
        self._normalize_ids(payload, force=True)
        self._ensure_proveedor_codigo(session, payload, force=True)
        entity = Proveedor(**payload)
        return self.repository.create(session, entity)

    def update(self, session: Session, proveedor_id: str, payload: dict) -> Proveedor:
        payload = self._normalize_payload(payload)
        # El codigo no se edita manualmente ni por importacion.
        payload.pop("proveedor_codigo", None)
        payload.pop("distribuidor_codigo", None)
        self._normalize_ids(payload, force=False)
        self._ensure_proveedor_codigo(session, payload, force=False)
        entity = self.repository.get_by_id(session, proveedor_id)
        if not entity:
            raise ValueError("Proveedor no encontrado")
        for key, value in payload.items():
            setattr(entity, key, value)
        return self.repository.update(session, entity)

    def delete(self, session: Session, proveedor_id: str) -> bool:
        return self.repository.delete(session, proveedor_id)

    def list_articles_by_provider(self, session: Session, proveedor_id: str) -> list[IngredienteStd]:
        if not proveedor_id:
            return []
        stmt = (
            select(IngredienteStd)
            .where(IngredienteStd.proveedor_id == proveedor_id)
            .order_by(IngredienteStd.articulo_descripcion)
        )
        return list(session.exec(stmt))

    def _normalize_payload(self, payload: dict) -> dict:
        data = dict(payload)
        if "proveedor_id" not in data and "distribuidor_id" in data:
            data["proveedor_id"] = data.get("distribuidor_id")
        if "proveedor_codigo" not in data and "distribuidor_codigo" in data:
            data["proveedor_codigo"] = data.get("distribuidor_codigo")
        if "proveedor_razon_social" not in data and "distribuidor_razon_social" in data:
            data["proveedor_razon_social"] = data.get("distribuidor_razon_social")
        if "proveedor_nombre_comercial" not in data and "distribuidor_nombre_comercial" in data:
            data["proveedor_nombre_comercial"] = data.get("distribuidor_nombre_comercial")
        if "proveedor_cif" not in data and "distribuidor_cif" in data:
            data["proveedor_cif"] = data.get("distribuidor_cif")
        if "proveedor_telefono" not in data and "distribuidor_telefono" in data:
            data["proveedor_telefono"] = data.get("distribuidor_telefono")
        if "proveedor_contacto" not in data and "distribuidor_contacto" in data:
            data["proveedor_contacto"] = data.get("distribuidor_contacto")
        return data

    def _normalize_ids(self, payload: dict, force: bool) -> None:
        if not force and "proveedor_id" not in payload:
            return
        proveedor_id = (payload.get("proveedor_id") or "").strip()
        payload["proveedor_id"] = proveedor_id or str(uuid4())

    def _ensure_proveedor_codigo(self, session: Session, payload: dict, force: bool) -> None:
        if not force and "proveedor_codigo" not in payload:
            return
        raw = payload.get("proveedor_codigo")
        if raw not in (None, ""):
            try:
                value = int(str(raw).strip())
                if value > 0:
                    payload["proveedor_codigo"] = value
                    return
            except ValueError:
                pass
        next_code = int(
            session.execute(text("SELECT COALESCE(MAX(proveedor_codigo), 0) + 1 FROM proveedores")).one()[0]
        )
        payload["proveedor_codigo"] = next_code
