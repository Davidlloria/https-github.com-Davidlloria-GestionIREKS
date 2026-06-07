from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class _CourseDocumentsSaver(Protocol):
    def save_documents(self, curso_id: str, payload: dict) -> None: ...


def _empty_paths() -> dict[str, str]:
    return {"portada": "", "invitacion": "", "recetario": ""}


@dataclass(slots=True)
class CourseDocumentFilesFlowService:
    course_service: _CourseDocumentsSaver | None = None
    selected_course_id: str = ""
    doc_paths: dict[str, str] = field(default_factory=_empty_paths)

    def select_course(self, course_id: str | None) -> None:
        self.selected_course_id = str(course_id or "").strip()

    def load_documents(self, course_id: str | None, portada: str, invitacion: str, recetario: str) -> dict[str, str]:
        self.select_course(course_id)
        return self.set_documents_fields(portada, invitacion, recetario)

    def set_documents_fields(self, portada: str, invitacion: str, recetario: str) -> dict[str, str]:
        self.doc_paths["portada"] = str(portada or "")
        self.doc_paths["invitacion"] = str(invitacion or "")
        self.doc_paths["recetario"] = str(recetario or "")
        return self.build_payload()

    def attach_document(self, field_name: str, file_path: str) -> dict[str, str]:
        self._set_document_path(field_name, file_path)
        return self.build_payload()

    def delete_document(self, field_name: str) -> dict[str, str]:
        self._set_document_path(field_name, "")
        return self.build_payload()

    def clear_documents_fields(self) -> dict[str, str]:
        return self.set_documents_fields("", "", "")

    def build_payload(self) -> dict[str, str]:
        return dict(self.doc_paths)

    def save_documents(self, course_id: str | None = None) -> dict[str, str]:
        clean_id = str(course_id or self.selected_course_id or "").strip()
        if not clean_id:
            raise ValueError("Selecciona un curso.")
        if self.course_service is None:
            raise ValueError("No hay servicio de cursos.")
        payload = self.build_payload()
        self.course_service.save_documents(clean_id, payload)
        self.selected_course_id = clean_id
        return payload

    def _set_document_path(self, field_name: str, file_path: str) -> None:
        if field_name not in self.doc_paths:
            raise ValueError(f"Campo de documento no valido: {field_name}")
        self.doc_paths[field_name] = str(file_path or "")
