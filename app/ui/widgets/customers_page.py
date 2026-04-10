from pathlib import Path

from sqlmodel import Session

from app.core.database import engine
from app.services.import_service import ImportService
from app.ui.widgets.entity_page import EntityPage
from app.viewmodels import CustomerViewModel


class CustomersPage(EntityPage):
    def __init__(self) -> None:
        self.vm = CustomerViewModel()
        self.import_service = ImportService()
        super().__init__(
            title="Clientes",
            columns=[
                ("id", "ID"),
                ("codigo", "Codigo"),
                ("nombre_comercial", "Nombre Comercial"),
                ("contacto", "Contacto"),
                ("telefono", "Telefono"),
                ("email", "Email"),
                ("activo", "Activo"),
            ],
            schema=[
                {"name": "codigo", "label": "Codigo"},
                {"name": "nombre_fiscal", "label": "Nombre fiscal"},
                {"name": "nombre_comercial", "label": "Nombre comercial"},
                {"name": "contacto", "label": "Contacto"},
                {"name": "telefono", "label": "Telefono"},
                {"name": "email", "label": "Email"},
                {"name": "direccion", "label": "Direccion", "type": "multiline"},
                {"name": "notas", "label": "Notas", "type": "multiline"},
                {"name": "activo", "label": "Activo", "type": "bool", "default": True},
            ],
            list_fn=self._list,
            create_fn=self._create,
            update_fn=self._update,
            delete_fn=self._delete,
            import_fn=self._import,
        )

    def _list(self, term: str) -> list:
        with Session(engine) as session:
            return self.vm.list(session, term)

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
            "codigo": ["cod", "codigo_cliente"],
            "nombre_fiscal": ["razon_social", "nombre_fiscal_cliente"],
            "nombre_comercial": ["cliente", "nombre", "nombre_cliente"],
            "contacto": ["persona_contacto"],
            "telefono": ["telefono_1", "movil", "tlf"],
            "email": ["correo", "correo_electronico"],
            "direccion": ["domicilio"],
            "notas": ["observaciones"],
            "activo": ["estado", "habilitado"],
        }
        with Session(engine) as session:
            return self.import_service.import_with_schema(
                file_path=Path(file_path),
                schema=self.schema,
                create_fn=lambda payload: self.vm.create(session, payload),
                required_fields=["codigo", "nombre_fiscal", "nombre_comercial"],
                aliases=aliases,
            )
