from typing import Any
from pathlib import Path
import re

from sqlmodel import Session

from app.core.database import engine
from app.models import IngredienteIreks, IngredienteStd
from app.services.import_service import ImportService
from app.ui.widgets.entity_page import EntityPage
from app.viewmodels import IngredientIreksViewModel, IngredientStdViewModel


def ingredient_schema(include_referencia: bool) -> list[dict[str, Any]]:
    schema: list[dict[str, Any]] = [
        {"name": "codigo", "label": "Codigo"},
        {"name": "nombre", "label": "Nombre"},
        {"name": "familia", "label": "Familia"},
        {"name": "subfamilia", "label": "Subfamilia"},
        {"name": "marca", "label": "Marca"},
        {"name": "formato_envase", "label": "Formato envase"},
        {"name": "unidad_envase", "label": "Unidad envase"},
        {"name": "cantidad_envase", "label": "Cantidad envase", "type": "float"},
        {"name": "precio_unidad", "label": "Precio unidad", "type": "float"},
        {"name": "precio_kg", "label": "Precio kg", "type": "float"},
        {"name": "es_harina", "label": "Es harina", "type": "bool"},
        {"name": "es_liquido", "label": "Es liquido", "type": "bool"},
        {"name": "es_grasa", "label": "Es grasa", "type": "bool"},
        {"name": "es_mejorante", "label": "Es mejorante", "type": "bool"},
        {"name": "activo", "label": "Activo", "type": "bool", "default": True},
    ]
    if include_referencia:
        schema.insert(1, {"name": "referencia", "label": "Referencia"})
    return schema


class _BaseIngredientsPage(EntityPage):
    def __init__(self, title: str, schema: list[dict], vm, include_referencia: bool) -> None:
        self.vm = vm
        self.import_service = ImportService()
        self.include_referencia = include_referencia
        super().__init__(
            title=title,
            columns=[
                ("id", "ID"),
                ("codigo", "Codigo"),
                ("nombre", "Nombre"),
                ("familia", "Familia"),
                ("subfamilia", "Subfamilia"),
                ("precio_kg", "Precio/kg"),
                ("es_harina", "Harina"),
                ("es_liquido", "Liquido"),
                ("activo", "Activo"),
            ],
            schema=schema,
            list_fn=self._list,
            create_fn=self._create,
            update_fn=self._update,
            delete_fn=self._delete,
            include_filters=True,
            import_fn=self._import,
        )

    def _list(self, term: str, familia: str, subfamilia: str) -> list:
        with Session(engine) as session:
            return self.vm.list(session, term, familia, subfamilia)

    def _create(self, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.create(session, payload)

    def _update(self, entity_id: int, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.update(session, entity_id, payload)

    def _delete(self, entity_id: int) -> bool:
        with Session(engine) as session:
            return self.vm.delete(session, entity_id)

    def _import(self, file_path: str) -> tuple[int, list[str]]:
        aliases = {
            "codigo": ["cod", "codigo_producto"],
            "nombre": ["ingrediente", "producto", "descripcion"],
            "familia": ["grupo"],
            "subfamilia": ["subgrupo"],
            "marca": ["fabricante"],
            "formato_envase": ["formato"],
            "unidad_envase": ["unidad"],
            "cantidad_envase": ["contenido_envase", "cantidad"],
            "precio_unidad": ["pvp_unidad", "precio_ud"],
            "precio_kg": ["pvp_kg", "precio"],
            "es_harina": ["harina"],
            "es_liquido": ["liquido", "agua"],
            "es_grasa": ["grasa"],
            "es_mejorante": ["mejorante"],
            "activo": ["estado", "habilitado"],
        }
        if self.include_referencia:
            aliases["referencia"] = ["ref", "referencia_ireks"]

        with Session(engine) as session:
            prefix = "IRK" if self.include_referencia else "STD"
            next_number = self._next_code_number(session, prefix) + 1

            def create_row(payload: dict[str, Any]) -> None:
                nonlocal next_number
                payload["codigo"] = f"{prefix}-{next_number:05d}"
                next_number += 1
                self.vm.create(session, payload)

            return self.import_service.import_with_schema(
                file_path=Path(file_path),
                schema=self.schema,
                create_fn=create_row,
                required_fields=["referencia", "nombre"] if self.include_referencia else ["nombre"],
                aliases=aliases,
            )

    def _next_code_number(self, session: Session, prefix: str) -> int:
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
        max_number = 0
        for row in self.vm.repository.list_all(session):
            match = pattern.match((row.codigo or "").strip())
            if match:
                max_number = max(max_number, int(match.group(1)))
        return max_number


class IngredientsIreksPage(_BaseIngredientsPage):
    def __init__(self) -> None:
        super().__init__(
            title="Ingredientes IREKS",
            schema=ingredient_schema(include_referencia=True),
            vm=IngredientIreksViewModel(),
            include_referencia=True,
        )


class IngredientsStdPage(_BaseIngredientsPage):
    def __init__(self) -> None:
        super().__init__(
            title="Materias Primas Estandar",
            schema=ingredient_schema(include_referencia=False),
            vm=IngredientStdViewModel(),
            include_referencia=False,
        )
