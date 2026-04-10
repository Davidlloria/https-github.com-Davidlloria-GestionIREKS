from __future__ import annotations

from datetime import datetime
from typing import Generic, Optional, TypeVar

from sqlmodel import Session, SQLModel, select

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    def list_all(self, session: Session) -> list[ModelType]:
        stmt = select(self.model).order_by(getattr(self.model, "id"))
        return list(session.exec(stmt))

    def get_by_id(self, session: Session, entity_id: int) -> Optional[ModelType]:
        return session.get(self.model, entity_id)

    def create(self, session: Session, entity: ModelType) -> ModelType:
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    def update(self, session: Session, entity: ModelType) -> ModelType:
        if hasattr(entity, "updated_at"):
            setattr(entity, "updated_at", datetime.utcnow())
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    def delete(self, session: Session, entity_id: int) -> bool:
        entity = self.get_by_id(session, entity_id)
        if not entity:
            return False
        session.delete(entity)
        session.commit()
        return True
