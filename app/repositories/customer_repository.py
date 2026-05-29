from sqlalchemy import String, cast
from sqlmodel import Session, col, or_, select

from app.models import Cliente
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Cliente]):
    def __init__(self) -> None:
        super().__init__(Cliente)

    def search(self, session: Session, term: str) -> list[Cliente]:
        if not term.strip():
            return self.list_all(session)
        like_term = f"%{term.strip()}%"
        stmt = (
            select(Cliente)
            .where(
                or_(
                    cast(col(Cliente.cliente_codigo), String).like(like_term),
                    col(Cliente.cliente_id).like(like_term),
                    col(Cliente.cliente_nombre_fiscal).like(like_term),
                    col(Cliente.cliente_nombre_comercial).like(like_term),
                    col(Cliente.cliente_nombre_interno).like(like_term),
                    col(Cliente.cliente_cif).like(like_term),
                    col(Cliente.cliente_telefono).like(like_term),
                    col(Cliente.cliente_email).like(like_term),
                    col(Cliente.cliente_direccion).like(like_term),
                    col(Cliente.cliente_tipo).like(like_term),
                    col(Cliente.cliente_grupo).like(like_term),
                )
            )
            .order_by(col(Cliente.cliente_nombre_comercial))
        )
        return list(session.exec(stmt))

    def list_all(self, session: Session) -> list[Cliente]:
        stmt = select(Cliente).order_by(col(Cliente.cliente_codigo), col(Cliente.cliente_nombre_comercial))
        return list(session.exec(stmt))

    def get_by_id(self, session: Session, entity_id: object) -> Cliente | None:
        return session.get(Cliente, entity_id)

    def delete(self, session: Session, entity_id: object) -> bool:
        entity = self.get_by_id(session, entity_id)
        if not entity:
            return False
        session.delete(entity)
        session.commit()
        return True

