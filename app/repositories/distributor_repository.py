from sqlalchemy import String, cast
from sqlmodel import Session, col, or_, select

from app.models import Distribuidor
from app.repositories.base import BaseRepository


class DistributorRepository(BaseRepository[Distribuidor]):
    def __init__(self) -> None:
        super().__init__(Distribuidor)

    def list_all(self, session: Session) -> list[Distribuidor]:
        stmt = select(Distribuidor).order_by(col(Distribuidor.distribuidor_codigo), col(Distribuidor.distribuidor_nombre_comercial))
        return list(session.exec(stmt))

    def search(self, session: Session, term: str) -> list[Distribuidor]:
        if not term.strip():
            return self.list_all(session)
        like_term = f"%{term.strip()}%"
        stmt = (
            select(Distribuidor)
            .where(
                or_(
                    cast(col(Distribuidor.distribuidor_codigo), String).like(like_term),
                    col(Distribuidor.distribuidor_id).like(like_term),
                    col(Distribuidor.distribuidor_razon_social).like(like_term),
                    col(Distribuidor.distribuidor_nombre_comercial).like(like_term),
                    col(Distribuidor.distribuidor_cif).like(like_term),
                    col(Distribuidor.distribuidor_telefono).like(like_term),
                    col(Distribuidor.distribuidor_contacto).like(like_term),
                )
            )
            .order_by(col(Distribuidor.distribuidor_codigo), col(Distribuidor.distribuidor_nombre_comercial))
        )
        return list(session.exec(stmt))

    def get_by_id(self, session: Session, entity_id: object) -> Distribuidor | None:
        return session.get(Distribuidor, entity_id)

    def delete(self, session: Session, entity_id: object) -> bool:
        entity = self.get_by_id(session, entity_id)
        if not entity:
            return False
        session.delete(entity)
        session.commit()
        return True
