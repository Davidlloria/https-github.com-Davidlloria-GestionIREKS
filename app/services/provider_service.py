from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.core.database import engine
from app.models import IngredienteStd, Proveedor
from app.services.import_service import ImportService
from app.viewmodels.provider_viewmodel import ProviderViewModel


class ProviderService:
    def __init__(self) -> None:
        self.vm = ProviderViewModel()
        self.import_service = ImportService()

    def list(self, term: str = "") -> list[Proveedor]:
        with Session(engine) as session:
            return self.vm.list(session, term)

    def create(self, payload: dict) -> Proveedor:
        with Session(engine) as session:
            return self.vm.create(session, payload)

    def update(self, proveedor_id: str, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.update(session, proveedor_id, payload)

    def delete(self, proveedor_id: str) -> bool:
        with Session(engine) as session:
            return self.vm.delete(session, proveedor_id)

    def list_articles_by_provider(self, proveedor_id: str) -> list[IngredienteStd]:
        with Session(engine) as session:
            return self.vm.list_articles_by_provider(session, proveedor_id)

    def import_file(self, file_path: Path) -> tuple[int, list[str]]:
        schema = [
            {"name": "distribuidor_id", "label": "Distribuidor_ID"},
            {"name": "distribuidor_codigo", "label": "Distribuidor_Codigo"},
            {"name": "distribuidor_razon_social", "label": "Distribuidor_Razon_Social"},
            {"name": "distribuidor_nombre_comercial", "label": "Distribuidor_Nombre_Comercial"},
            {"name": "distribuidor_cif", "label": "Distribuidor_CIF"},
            {"name": "distribuidor_telefono", "label": "Distribuidor_Telefono"},
            {"name": "distribuidor_contacto", "label": "Distribuidor_Contacto"},
        ]
        aliases = {
            "distribuidor_id": ["id"],
            "distribuidor_codigo": ["codigo", "cod", "cod_distribuidor"],
            "distribuidor_razon_social": ["razon_social", "nombre_fiscal"],
            "distribuidor_nombre_comercial": ["nombre", "nombre_comercial", "distribuidor"],
            "distribuidor_cif": ["cif", "nif"],
            "distribuidor_telefono": ["telefono", "movil"],
            "distribuidor_contacto": ["contacto", "persona_contacto"],
        }
        with Session(engine) as session:

            def create_provider(payload: dict) -> None:
                self.vm.create(session, payload)

            return self.import_service.import_with_schema(
                file_path=file_path,
                schema=schema,
                create_fn=create_provider,
                required_fields=["distribuidor_id", "distribuidor_razon_social"],
                aliases=aliases,
            )
