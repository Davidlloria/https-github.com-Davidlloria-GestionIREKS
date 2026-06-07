from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from app.core.database import engine as default_engine
from app.models import Asistente
from app.services.import_service import ImportService
from app.viewmodels.course_viewmodel import AsistenteListadoItem, CourseViewModel


@dataclass(slots=True)
class CourseAttendeeFlowService:
    engine: object = default_engine
    course_vm: CourseViewModel | None = None
    import_service: ImportService | None = None

    def __post_init__(self) -> None:
        if self.course_vm is None:
            self.course_vm = CourseViewModel()
        if self.import_service is None:
            self.import_service = ImportService()

    def list_attendees(self, curso_id: str) -> list[AsistenteListadoItem]:
        with Session(self.engine) as session:
            return self.course_vm.list_attendees(session, curso_id)

    def add_attendee(
        self,
        curso_id: str,
        contacto_id: str,
        cliente_id: str,
        observaciones: str = "",
        status_confirmacion: bool = False,
    ) -> Asistente:
        with Session(self.engine) as session:
            return self.course_vm.add_attendee(
                session,
                curso_id,
                contacto_id,
                cliente_id,
                observaciones,
                status_confirmacion,
            )

    def remove_attendee(self, curso_id: str, contacto_id: str) -> bool:
        with Session(self.engine) as session:
            return self.course_vm.remove_attendee(session, curso_id, contacto_id)

    def set_attendee_confirmation(self, curso_id: str, contacto_id: str, status: bool) -> Asistente:
        with Session(self.engine) as session:
            return self.course_vm.set_attendee_confirmation(session, curso_id, contacto_id, status)

    def update_attendee_observaciones(self, curso_id: str, contacto_id: str, observaciones: str) -> Asistente:
        with Session(self.engine) as session:
            return self.course_vm.update_attendee_observaciones(session, curso_id, contacto_id, observaciones)

    def import_attendees(self, file_path: Path) -> tuple[int, list[str]]:
        schema = [
            {"name": "curso_id", "label": "Curso_ID"},
            {"name": "contacto_id", "label": "Contacto_ID"},
            {"name": "cliente_id", "label": "Cliente_ID"},
            {"name": "observaciones", "label": "Observaciones"},
            {"name": "status_confirmacion", "label": "Status_Confirmacion", "type": "bool", "default": False},
        ]

        def create_payload(payload: dict) -> None:
            self.add_attendee(
                str(payload.get("curso_id") or "").strip(),
                str(payload.get("contacto_id") or "").strip(),
                str(payload.get("cliente_id") or "").strip(),
                str(payload.get("observaciones") or "").strip(),
                bool(payload.get("status_confirmacion") or False),
            )

        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=create_payload,
            required_fields=["curso_id", "contacto_id", "cliente_id"],
        )
