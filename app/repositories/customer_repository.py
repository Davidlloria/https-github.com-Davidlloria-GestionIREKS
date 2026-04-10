from sqlmodel import Session, or_, select

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
                    Cliente.codigo.like(like_term),
                    Cliente.nombre_fiscal.like(like_term),
                    Cliente.nombre_comercial.like(like_term),
                    Cliente.contacto.like(like_term),
                )
            )
            .order_by(Cliente.nombre_comercial)
        )
        return list(session.exec(stmt))

