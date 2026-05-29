from sqlalchemy import String, cast, update
from sqlmodel import Session, col, or_, select

from app.models import IngredienteStd, Proveedor
from app.repositories.base import BaseRepository


class ProviderRepository(BaseRepository[Proveedor]):
    def __init__(self) -> None:
        super().__init__(Proveedor)

    def list_all(self, session: Session) -> list[Proveedor]:
        stmt = select(Proveedor).order_by(col(Proveedor.proveedor_codigo), col(Proveedor.proveedor_nombre_comercial))
        return list(session.exec(stmt))

    def search(self, session: Session, term: str) -> list[Proveedor]:
        if not term.strip():
            return self.list_all(session)
        like_term = f"%{term.strip()}%"
        stmt = (
            select(Proveedor)
            .where(
                or_(
                    cast(col(Proveedor.proveedor_codigo), String).like(like_term),
                    col(Proveedor.proveedor_id).like(like_term),
                    col(Proveedor.proveedor_razon_social).like(like_term),
                    col(Proveedor.proveedor_nombre_comercial).like(like_term),
                    col(Proveedor.proveedor_cif).like(like_term),
                    col(Proveedor.proveedor_telefono).like(like_term),
                    col(Proveedor.proveedor_contacto).like(like_term),
                )
            )
            .order_by(col(Proveedor.proveedor_codigo), col(Proveedor.proveedor_nombre_comercial))
        )
        return list(session.exec(stmt))

    def get_by_id(self, session: Session, entity_id: object) -> Proveedor | None:
        return session.get(Proveedor, entity_id)

    def delete(self, session: Session, entity_id: object) -> bool:
        entity = self.get_by_id(session, entity_id)
        if not entity:
            return False
        provider_id = entity.proveedor_id
        session.execute(
            update(IngredienteStd)
            .where(col(IngredienteStd.proveedor_id) == provider_id)
            .values(proveedor_id="")
        )
        session.delete(entity)
        session.commit()
        return True
