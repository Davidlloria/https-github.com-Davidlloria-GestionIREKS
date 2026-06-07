from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from app.services.course_document_generation_flow_service import CourseDocumentGenerationFlowService


@dataclass
class _FakeSignatureService:
    DEFAULT_OUTPUT_DIR: Path = Path("sig_out")

    def __post_init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, *, attendees, output_path, template_key):
        self.calls.append(
            {"attendees": list(attendees), "output_path": output_path, "template_key": template_key}
        )
        return output_path


@dataclass
class _FakeCertificateService:
    DEFAULT_OUTPUT_DIR: Path = Path("cert_out")

    def __post_init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, *, certificates, output_path):
        self.calls.append({"certificates": list(certificates), "output_path": output_path})
        return output_path


def _course() -> dict[str, object]:
    return {"curso_nombre": "Curso & Especial", "curso_fecha": date(2026, 4, 15)}


def _attendees() -> list[dict[str, object]]:
    return [
        {"asistente": "Ana &", "nif": "123", "empresa": "Pan <1>", "status_confirmacion": True},
        {"asistente": "Luis", "nif": "456", "empresa": "Empresa >", "status_confirmacion": False},
    ]


def test_format_course_date_and_long_format() -> None:
    service = CourseDocumentGenerationFlowService(_FakeSignatureService(), _FakeCertificateService())

    assert service.format_course_date(date(2026, 4, 15)) == "15/04/2026"
    assert service.format_course_date_long(date(2026, 4, 15)) == "15 de abril de 2026"


def test_build_signature_payload_all_and_output_path() -> None:
    signature = _FakeSignatureService()
    service = CourseDocumentGenerationFlowService(signature, _FakeCertificateService())

    payload = service.build_signature_payload(_course(), _attendees(), scope="all")
    path = service.build_signature_output_path(_course(), scope="all", template_key="imagenes")

    assert payload == [
        {"fecha": "15/04/2026", "nombre": "Ana &", "nif": "123", "empresa": "Pan <1>"},
        {"fecha": "15/04/2026", "nombre": "Luis", "nif": "456", "empresa": "Empresa >"},
    ]
    assert path == Path("sig_out") / "consent_imagenes_Curso___Especial_todos.pdf"


def test_build_signature_payload_confirmed_filters_rows() -> None:
    service = CourseDocumentGenerationFlowService(_FakeSignatureService(), _FakeCertificateService())

    payload = service.build_signature_payload(_course(), _attendees(), scope="confirmed")

    assert payload == [{"fecha": "15/04/2026", "nombre": "Ana &", "nif": "123", "empresa": "Pan <1>"}]


def test_build_signature_payload_confirmed_without_rows_raises() -> None:
    service = CourseDocumentGenerationFlowService(_FakeSignatureService(), _FakeCertificateService())

    with pytest.raises(ValueError, match="No hay asistentes confirmados"):
        service.build_signature_payload(
            _course(),
            [{"asistente": "Luis", "nif": "456", "empresa": "Empresa >", "status_confirmacion": False}],
            scope="confirmed",
        )


def test_build_signature_payload_selected_uses_selected_row() -> None:
    service = CourseDocumentGenerationFlowService(_FakeSignatureService(), _FakeCertificateService())
    selected = {"asistente": "Luis", "nif": "456", "empresa": "Empresa >", "status_confirmacion": False}

    payload = service.build_signature_payload(_course(), _attendees(), scope="selected", selected_attendee=selected)

    assert payload == [{"fecha": "15/04/2026", "nombre": "Luis", "nif": "456", "empresa": "Empresa >"}]


def test_build_signature_payload_selected_without_row_raises() -> None:
    service = CourseDocumentGenerationFlowService(_FakeSignatureService(), _FakeCertificateService())

    with pytest.raises(ValueError, match="Selecciona un asistente"):
        service.build_signature_payload(_course(), _attendees(), scope="selected")


def test_build_signature_payload_all_without_rows_raises() -> None:
    service = CourseDocumentGenerationFlowService(_FakeSignatureService(), _FakeCertificateService())

    with pytest.raises(ValueError, match="No hay asistentes para generar hojas de firma"):
        service.build_signature_payload(_course(), [], scope="all")


def test_build_certificate_payload_and_output_path() -> None:
    service = CourseDocumentGenerationFlowService(_FakeSignatureService(), _FakeCertificateService())

    payload = service.build_certificate_payload(_course(), _attendees(), scope="all")
    path = service.build_certificate_output_path(_course(), scope="all")

    assert payload == [
        {"asistente": "Ana &", "curso": "Curso & Especial", "fecha": "Arinaga, 15 de abril de 2026"},
        {"asistente": "Luis", "curso": "Curso & Especial", "fecha": "Arinaga, 15 de abril de 2026"},
    ]
    assert path == Path("cert_out") / "certificado_Curso___Especial_todos.pdf"


def test_generate_signature_pdf_calls_signature_service() -> None:
    signature = _FakeSignatureService()
    service = CourseDocumentGenerationFlowService(signature, _FakeCertificateService())

    out = service.generate_signature_pdf(_course(), _attendees(), scope="confirmed", template_key="datos")

    assert out == Path("sig_out") / "consent_datos_Curso___Especial_confirmados.pdf"
    assert signature.calls[0]["template_key"] == "datos"
    assert signature.calls[0]["attendees"] == [{"fecha": "15/04/2026", "nombre": "Ana &", "nif": "123", "empresa": "Pan <1>"}]


def test_generate_certificates_pdf_calls_certificate_service() -> None:
    certificate = _FakeCertificateService()
    service = CourseDocumentGenerationFlowService(_FakeSignatureService(), certificate)

    out = service.generate_certificates_pdf(_course(), _attendees(), scope="selected", selected_attendee=_attendees()[1])

    assert out == Path("cert_out") / "certificado_Curso___Especial_seleccionado.pdf"
    assert certificate.calls[0]["certificates"] == [
        {"asistente": "Luis", "curso": "Curso & Especial", "fecha": "Arinaga, 15 de abril de 2026"}
    ]
