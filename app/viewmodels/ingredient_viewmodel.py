from typing import Generic, TypeVar

from sqlmodel import Session

from app.models import IngredienteIreks, IngredienteStd
from app.repositories.ingredient_repository import (
    IngredientIreksRepository,
    IngredientRepository,
    IngredientStdRepository,
)

IngredientModel = TypeVar("IngredientModel", IngredienteIreks, IngredienteStd)


class IngredientViewModel(Generic[IngredientModel]):
    def __init__(self, repository: IngredientRepository[IngredientModel]) -> None:
        self.repository = repository

    def list(
        self, session: Session, term: str = "", familia: str = "", subfamilia: str = ""
    ) -> list[IngredientModel]:
        return self.repository.search(session, term, familia, subfamilia)

    def create(self, session: Session, payload: dict) -> IngredientModel:
        entity = self.repository.model(**payload)
        return self.repository.create(session, entity)

    def update(self, session: Session, entity_id: int, payload: dict) -> IngredientModel:
        entity = self.repository.get_by_id(session, entity_id)
        if not entity:
            raise ValueError("Ingrediente no encontrado")
        for key, value in payload.items():
            setattr(entity, key, value)
        return self.repository.update(session, entity)

    def delete(self, session: Session, entity_id: int) -> bool:
        return self.repository.delete(session, entity_id)


class IngredientIreksViewModel(IngredientViewModel[IngredienteIreks]):
    def __init__(self) -> None:
        super().__init__(IngredientIreksRepository())


class IngredientStdViewModel(IngredientViewModel[IngredienteStd]):
    def __init__(self) -> None:
        super().__init__(IngredientStdRepository())

