from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.database import engine
from app.models import IngredienteIreks
from app.services.import_service import ImportService


class IngredientEntityService:
    def __init__(self, vm, *, include_referencia: bool, schema: list[dict], required_fields: list[str]) -> None:
        self.vm = vm
        self.include_referencia = include_referencia
        self.schema = schema
        self.required_fields = required_fields
        self.import_service = ImportService()

    def list(self, term: str, familia: str = "", subfamilia: str = "", active_filter: str = "all") -> list:
        with Session(engine) as session:
            if self.include_referencia:
                return self.vm.list(session, term, familia, subfamilia)
            return self.vm.list(session, term, familia, subfamilia, active_filter=active_filter)

    def create(self, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.create(session, payload)

    def update(self, entity_id, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.update(session, entity_id, payload)

    def delete(self, entity_id) -> bool:
        with Session(engine) as session:
            return self.vm.delete(session, entity_id)

    def import_file(self, file_path: str, aliases: dict[str, list[str]]) -> tuple[int, list[str]]:
        with Session(engine) as session:
            if self.include_referencia:

                def create_row(payload: dict[str, Any]) -> None:
                    articulo_id = str(payload.get("articulo_id") or "").strip()
                    existing = None
                    if articulo_id:
                        existing = session.exec(
                            select(IngredienteIreks).where(IngredienteIreks.articulo_id == articulo_id)
                        ).first()
                    if existing:
                        self.vm.update(session, existing.id or 0, payload)
                    else:
                        self.vm.create(session, payload)

            else:

                def create_row(payload: dict[str, Any]) -> None:
                    self.vm.create(session, payload)

            return self.import_service.import_with_schema(
                file_path=Path(file_path),
                schema=self.schema,
                create_fn=create_row,
                required_fields=self.required_fields,
                aliases=aliases,
            )
