from datetime import UTC, datetime

from sqlalchemy import String, cast
from sqlmodel import Session, col, or_, select

from app.models import Contacto


class ContactRepository:
    def list_all(self, session: Session) -> list[Contacto]:
        stmt = select(Contacto).order_by(col(Contacto.contacto_codigo), col(Contacto.contacto_id))
        return list(session.exec(stmt))

    def search(self, session: Session, term: str) -> list[Contacto]:
        if not term.strip():
            return self.list_all(session)
        like_term = f"%{term.strip()}%"
        stmt = (
            select(Contacto)
            .where(
                or_(
                    col(Contacto.nombre).like(like_term),
                    col(Contacto.apellidos).like(like_term),
                    col(Contacto.cargo).like(like_term),
                    col(Contacto.nif).like(like_term),
                    col(Contacto.telefono).like(like_term),
                    col(Contacto.email).like(like_term),
                    col(Contacto.contacto_id).like(like_term),
                    col(Contacto.cliente_id).like(like_term),
                    cast(col(Contacto.contacto_codigo), String).like(like_term),
                )
            )
            .order_by(col(Contacto.contacto_codigo), col(Contacto.contacto_id))
        )
        return list(session.exec(stmt))

    def get_by_id(self, session: Session, contacto_id: str) -> Contacto | None:
        return session.get(Contacto, contacto_id)

    def create(self, session: Session, entity: Contacto) -> Contacto:
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    def update(self, session: Session, entity: Contacto) -> Contacto:
        entity.updated_at = datetime.now(UTC)
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    def delete(self, session: Session, contacto_id: str) -> bool:
        entity = self.get_by_id(session, contacto_id)
        if not entity:
            return False
        session.delete(entity)
        session.commit()
        return True
