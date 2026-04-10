from typing import TypeVar

from sqlmodel import Session, and_, or_, select

from app.models import IngredienteIreks, IngredienteStd
from app.repositories.base import BaseRepository

IngredientModel = TypeVar("IngredientModel", IngredienteIreks, IngredienteStd)


class IngredientRepository(BaseRepository[IngredientModel]):
    def search(
        self,
        session: Session,
        term: str = "",
        familia: str = "",
        subfamilia: str = "",
    ) -> list[IngredientModel]:
        conditions = []
        if term.strip():
            like_term = f"%{term.strip()}%"
            conditions.append(
                or_(
                    self.model.codigo.like(like_term),
                    self.model.nombre.like(like_term),
                    self.model.familia.like(like_term),
                    self.model.subfamilia.like(like_term),
                )
            )
        if familia.strip():
            conditions.append(self.model.familia == familia.strip())
        if subfamilia.strip():
            conditions.append(self.model.subfamilia == subfamilia.strip())

        stmt = select(self.model)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(self.model.nombre)
        return list(session.exec(stmt))


class IngredientIreksRepository(IngredientRepository[IngredienteIreks]):
    def __init__(self) -> None:
        super().__init__(IngredienteIreks)


class IngredientStdRepository(IngredientRepository[IngredienteStd]):
    def __init__(self) -> None:
        super().__init__(IngredienteStd)
