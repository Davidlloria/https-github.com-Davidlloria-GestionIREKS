from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.services.course_document_files_flow_service import CourseDocumentFilesFlowService


@dataclass
class _FakeCourseService:
    calls: list[tuple[str, dict]] = field(default_factory=list)

    def save_documents(self, curso_id: str, payload: dict) -> None:
        self.calls.append((curso_id, dict(payload)))


def test_load_documents_sets_selected_course_and_paths() -> None:
    service = CourseDocumentFilesFlowService(course_service=_FakeCourseService())

    payload = service.load_documents("course-1", "portada.pdf", "", None)

    assert service.selected_course_id == "course-1"
    assert payload == {"portada": "portada.pdf", "invitacion": "", "recetario": ""}
    assert service.doc_paths == payload


def test_attach_delete_and_clear_update_state() -> None:
    service = CourseDocumentFilesFlowService(course_service=_FakeCourseService())
    service.select_course("course-1")

    service.attach_document("portada", "portada.pdf")
    assert service.doc_paths["portada"] == "portada.pdf"

    service.delete_document("portada")
    assert service.doc_paths["portada"] == ""

    service.set_documents_fields("a.pdf", "b.pdf", "c.pdf")
    service.clear_documents_fields()
    assert service.doc_paths == {"portada": "", "invitacion": "", "recetario": ""}


def test_build_payload_returns_copy() -> None:
    service = CourseDocumentFilesFlowService(course_service=_FakeCourseService())
    service.set_documents_fields("a.pdf", "b.pdf", "c.pdf")

    payload = service.build_payload()
    payload["portada"] = "changed.pdf"

    assert service.doc_paths["portada"] == "a.pdf"


def test_save_documents_requires_selected_course() -> None:
    service = CourseDocumentFilesFlowService(course_service=_FakeCourseService())

    with pytest.raises(ValueError, match="Selecciona un curso"):
        service.save_documents()


def test_save_documents_calls_course_service() -> None:
    fake = _FakeCourseService()
    service = CourseDocumentFilesFlowService(course_service=fake)
    service.load_documents("course-1", "portada.pdf", "invitacion.pdf", "")

    payload = service.save_documents()

    assert payload == {"portada": "portada.pdf", "invitacion": "invitacion.pdf", "recetario": ""}
    assert fake.calls == [("course-1", payload)]


def test_invalid_document_field_raises() -> None:
    service = CourseDocumentFilesFlowService(course_service=_FakeCourseService())

    with pytest.raises(ValueError, match="Campo de documento no valido"):
        service.attach_document("unknown", "path.pdf")
