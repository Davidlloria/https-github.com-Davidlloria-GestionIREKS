from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.core.database import engine
from app.core.pagination import DEFAULT_PAGE_LIMIT, page_items
from app.models import Distribuidor
from app.schemas.distributors import DistributorDetail, DistributorListItem, DistributorListResponse
from app.services.import_service import ImportService
from app.viewmodels.distributor_viewmodel import DistributorViewModel


class DistributorService:
    def __init__(self) -> None:
        self.vm = DistributorViewModel()
        self.import_service = ImportService()

    def list(self, term: str = "") -> list[Distribuidor]:
        with Session(engine) as session:
            return self.vm.list(session, term)

    def list_payload(
        self,
        term: str = "",
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> DistributorListResponse:
        rows = self.list(term)
        page_rows = page_items(rows, limit=limit, offset=offset)
        return DistributorListResponse(
            items=DistributorListItem.list_from_entities(page_rows),
            total=len(rows),
            limit=limit,
            offset=offset,
        )

    def detail_payload(self, distribuidor_id: str) -> DistributorDetail | None:
        with Session(engine) as session:
            entity = self.vm.get(session, distribuidor_id)
            if entity is None:
                return None
            return DistributorDetail.from_entity(entity)

    def create(self, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.create(session, payload)

    def update(self, distribuidor_id: str, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.update(session, distribuidor_id, payload)

    def delete(self, distribuidor_id: str) -> bool:
        with Session(engine) as session:
            return self.vm.delete(session, distribuidor_id)

    def import_file(self, file_path: Path) -> tuple[int, list[str]]:
        schema = [
            {"name": "distribuidor_id", "label": "Distribuidor_ID"},
            {"name": "distribuidor_codigo", "label": "Codigo"},
            {"name": "distribuidor_razon_social", "label": "Razon social"},
            {"name": "distribuidor_nombre_comercial", "label": "Nombre comercial"},
            {"name": "distribuidor_cif", "label": "CIF"},
            {"name": "distribuidor_telefono", "label": "Telefono"},
            {"name": "distribuidor_contacto", "label": "Contacto"},
        ]
        aliases = {
            "distribuidor_id": ["id"],
            "distribuidor_codigo": ["codigo", "cod"],
            "distribuidor_razon_social": ["razon_social", "razon", "nombre_fiscal"],
            "distribuidor_nombre_comercial": ["nombre_comercial", "nombre"],
            "distribuidor_cif": ["cif", "nif"],
            "distribuidor_telefono": ["telefono", "tel"],
            "distribuidor_contacto": ["contacto"],
        }
        with Session(engine) as session:

            def create_row(payload: dict) -> None:
                data = dict(payload)
                data.pop("distribuidor_codigo", None)
                distribuidor_id = str(data.get("distribuidor_id") or "").strip()
                data["distribuidor_id"] = distribuidor_id
                data["distribuidor_nombre_comercial"] = str(data.get("distribuidor_nombre_comercial") or "").strip()
                if distribuidor_id:
                    existing = self.vm.repository.get_by_id(session, distribuidor_id)
                    if existing:
                        self.vm.update(session, distribuidor_id, data)
                        return
                self.vm.create(session, data)

            return self.import_service.import_with_schema(
                file_path=file_path,
                schema=schema,
                create_fn=create_row,
                required_fields=["distribuidor_id", "distribuidor_nombre_comercial"],
                aliases=aliases,
            )
