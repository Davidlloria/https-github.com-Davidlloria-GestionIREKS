from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from app.core.database import engine
from app.models import Curso, CursoDocumento
from app.services.import_service import ImportService
from app.viewmodels.course_viewmodel import (
    AsistenteListadoItem,
    ContactPickerItem,
    CourseViewModel,
    CursoTecnicoListadoItem,
    TechnicianPickerItem,
)


class CourseService:
    def __init__(self) -> None:
        self.vm = CourseViewModel()
        self.import_service = ImportService()

    def list_courses(
        self,
        *,
        term: str = "",
        year: int | None = None,
        month_start: int | None = None,
        month_end: int | None = None,
    ) -> list[Curso]:
        with Session(engine) as session:
            return self.vm.list_courses(
                session,
                term=term,
                year=year,
                month_start=month_start,
                month_end=month_end,
            )

    def create_course(self, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.create_course(session, payload)

    def update_course(self, curso_id: str, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.update_course(session, curso_id, payload)

    def delete_course(self, curso_id: str) -> bool:
        with Session(engine) as session:
            return self.vm.delete_course(session, curso_id)

    def get_documents(self, curso_id: str) -> CursoDocumento:
        with Session(engine) as session:
            return self.vm.get_documents(session, curso_id)

    def save_documents(self, curso_id: str, payload: dict) -> None:
        with Session(engine) as session:
            self.vm.save_documents(session, curso_id, payload)

    def list_contacts_for_picker(self, term: str = "") -> list[ContactPickerItem]:
        with Session(engine) as session:
            return self.vm.list_contacts_for_picker(session, term)

    def list_technicians_for_picker(self, term: str = "") -> list[TechnicianPickerItem]:
        with Session(engine) as session:
            return self.vm.list_technicians_for_picker(session, term)

    def list_attendees(self, curso_id: str) -> list[AsistenteListadoItem]:
        with Session(engine) as session:
            return self.vm.list_attendees(session, curso_id)

    def list_course_technicians(self, curso_id: str) -> list[CursoTecnicoListadoItem]:
        with Session(engine) as session:
            return self.vm.list_course_technicians(session, curso_id)

    def add_attendee(
        self,
        curso_id: str,
        contacto_id: str,
        cliente_id: str,
        observaciones: str = "",
        status_confirmacion: bool = False,
    ) -> None:
        with Session(engine) as session:
            self.vm.add_attendee(session, curso_id, contacto_id, cliente_id, observaciones, status_confirmacion)

    def remove_attendee(self, curso_id: str, contacto_id: str) -> bool:
        with Session(engine) as session:
            return self.vm.remove_attendee(session, curso_id, contacto_id)

    def set_attendee_confirmation(self, curso_id: str, contacto_id: str, status: bool) -> None:
        with Session(engine) as session:
            self.vm.set_attendee_confirmation(session, curso_id, contacto_id, status)

    def update_attendee_observaciones(self, curso_id: str, contacto_id: str, observaciones: str) -> None:
        with Session(engine) as session:
            self.vm.update_attendee_observaciones(session, curso_id, contacto_id, observaciones)

    def add_course_technician(self, curso_id: str, tecnico_id: str) -> None:
        with Session(engine) as session:
            self.vm.add_course_technician(session, curso_id, tecnico_id)

    def remove_course_technician(self, curso_id: str, tecnico_id: str) -> bool:
        with Session(engine) as session:
            return self.vm.remove_course_technician(session, curso_id, tecnico_id)

    def import_courses(self, file_path: Path) -> tuple[int, list[str]]:
        schema = [
            {"name": "curso_id", "label": "Curso_ID"},
            {"name": "curso_nombre", "label": "Curso_Nombre"},
            {"name": "curso_fecha", "label": "Curso_Fecha"},
            {"name": "invitacion", "label": "Invitacion"},
            {"name": "portada", "label": "Portada"},
            {"name": "recetario", "label": "Recetario"},
        ]
        return self.import_service.import_with_schema(
            file_path=file_path,
            schema=schema,
            create_fn=self.create_course,
            required_fields=["curso_id", "curso_nombre", "curso_fecha"],
        )

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
