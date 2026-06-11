from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.core.database import engine
from app.core.pagination import DEFAULT_PAGE_LIMIT, page_items
from app.models import Tecnico
from app.services.import_service import ImportService
from app.viewmodels.technician_viewmodel import TechnicianViewModel
from app.schemas.technicians import TechnicianDetail, TechnicianListItem, TechnicianListResponse


class TechnicianService:
    def __init__(self) -> None:
        self.vm = TechnicianViewModel()
        self.import_service = ImportService()

    def list(self, term: str = "") -> list[Tecnico]:
        with Session(engine) as session:
            return self.vm.list(session, term)

    def list_payload(
        self,
        term: str = "",
        *,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> TechnicianListResponse:
        rows = self.list(term)
        page_rows = page_items(rows, limit=limit, offset=offset)
        return TechnicianListResponse(
            items=TechnicianListItem.list_from_entities(page_rows),
            total=len(rows),
            limit=limit,
            offset=offset,
        )

    def detail_payload(self, tecnico_id: str) -> TechnicianDetail | None:
        with Session(engine) as session:
            entity = self.vm.get(session, tecnico_id)
            if entity is None:
                return None
            return TechnicianDetail.from_entity(entity)

    def create(self, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.create(session, payload)

    def update(self, tecnico_id: str, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.update(session, tecnico_id, payload)

    def delete(self, tecnico_id: str) -> bool:
        with Session(engine) as session:
            return self.vm.delete(session, tecnico_id)

    def import_file(self, file_path: Path) -> tuple[int, list[str]]:
        schema = [
            {"name": "tecnico_id", "label": "tecnico_id"},
            {"name": "tecnico_codigo", "label": "codigo"},
            {"name": "nombre", "label": "Nombre"},
            {"name": "apellidos", "label": "Apellidos"},
            {"name": "movil", "label": "Movil"},
            {"name": "interno", "label": "interno"},
            {"name": "email", "label": "email"},
        ]
        aliases = {
            "nombre": ["nombre", "tecnico_nombre"],
            "apellidos": ["apellidos", "tecnico_apellidos"],
            "movil": ["movil", "móvil", "telefono", "tel", "telefono_movil"],
            "interno": ["interno", "ext", "extension"],
            "email": ["email", "correo", "mail"],
            "tecnico_id": ["tecnico_id", "tecnico_uuid"],
            "tecnico_codigo": ["codigo", "cod", "tecnico_codigo"],
        }

        def create_payload(payload: dict) -> None:
            self.create(
                {
                    "nombre": str(payload.get("nombre") or "").strip(),
                    "apellidos": str(payload.get("apellidos") or "").strip(),
                    "movil": str(payload.get("movil") or "").strip(),
                    "interno": str(payload.get("interno") or "").strip(),
                    "email": str(payload.get("email") or "").strip(),
                }
            )

        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=create_payload,
            required_fields=["nombre"],
            aliases=aliases,
        )
