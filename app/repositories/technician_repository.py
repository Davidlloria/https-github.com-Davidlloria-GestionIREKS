from datetime import datetime

from sqlalchemy import String, cast
from sqlmodel import Session, col, or_, select

from app.models import Tecnico


class TechnicianRepository:
    def list_all(self, session: Session) -> list[Tecnico]:
        stmt = select(Tecnico).order_by(col(Tecnico.tecnico_codigo), col(Tecnico.apellidos), col(Tecnico.nombre))
        return list(session.exec(stmt))

    def search(self, session: Session, term: str) -> list[Tecnico]:
        if not term.strip():
            return self.list_all(session)
        like_term = f"%{term.strip()}%"
        stmt = (
            select(Tecnico)
            .where(
                or_(
                    col(Tecnico.nombre).like(like_term),
                    col(Tecnico.apellidos).like(like_term),
                    col(Tecnico.movil).like(like_term),
                    col(Tecnico.interno).like(like_term),
                    col(Tecnico.email).like(like_term),
                    col(Tecnico.tecnico_id).like(like_term),
                    cast(col(Tecnico.tecnico_codigo), String).like(like_term),
                )
            )
            .order_by(col(Tecnico.tecnico_codigo), col(Tecnico.apellidos), col(Tecnico.nombre))
        )
        return list(session.exec(stmt))

    def get_by_id(self, session: Session, tecnico_id: str) -> Tecnico | None:
        return session.get(Tecnico, tecnico_id)

    def create(self, session: Session, entity: Tecnico) -> Tecnico:
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    def update(self, session: Session, entity: Tecnico) -> Tecnico:
        entity.updated_at = datetime.utcnow()
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    def delete(self, session: Session, tecnico_id: str) -> bool:
        entity = self.get_by_id(session, tecnico_id)
        if not entity:
            return False
        session.delete(entity)
        session.commit()
        return True
