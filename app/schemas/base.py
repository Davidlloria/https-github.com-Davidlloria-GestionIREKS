from __future__ import annotations

from typing import Any, TypeVar

from pydantic import ConfigDict
from sqlmodel import SQLModel


SchemaT = TypeVar("SchemaT", bound="AppSchema")


class AppSchema(SQLModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    @classmethod
    def from_entity(cls: type[SchemaT], entity: object) -> SchemaT:
        return cls.model_validate(entity, from_attributes=True)

    @classmethod
    def list_from_entities(cls: type[SchemaT], rows: list[object]) -> list[SchemaT]:
        return [cls.from_entity(row) for row in rows]

    def to_payload(self, *, exclude_none: bool = False) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=exclude_none)


class PaginatedResponse(AppSchema):
    total: int = 0
    limit: int = 0
    offset: int = 0
