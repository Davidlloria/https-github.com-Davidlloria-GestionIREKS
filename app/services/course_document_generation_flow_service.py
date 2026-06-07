from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.services.certificate_service import CertificateService
from app.services.signature_sheet_service import SignatureSheetService


class CourseDocumentGenerationFlowService:
    def __init__(
        self,
        signature_service: SignatureSheetService | None = None,
        certificate_service: CertificateService | None = None,
    ) -> None:
        self.signature_service = signature_service or SignatureSheetService()
        self.certificate_service = certificate_service or CertificateService()

    def generate_signature_pdf(
        self,
        course: object | Mapping[str, Any],
        attendees: Iterable[object | Mapping[str, Any]],
        *,
        scope: str,
        template_key: str,
        selected_attendee: object | Mapping[str, Any] | None = None,
    ) -> Path:
        payload = self.build_signature_payload(
            course=course,
            attendees=attendees,
            scope=scope,
            selected_attendee=selected_attendee,
        )
        output_path = self.build_signature_output_path(course, scope=scope, template_key=template_key)
        return self.signature_service.generate(attendees=payload, output_path=output_path, template_key=template_key)

    def generate_certificates_pdf(
        self,
        course: object | Mapping[str, Any],
        attendees: Iterable[object | Mapping[str, Any]],
        *,
        scope: str,
        selected_attendee: object | Mapping[str, Any] | None = None,
    ) -> Path:
        payload = self.build_certificate_payload(
            course=course,
            attendees=attendees,
            scope=scope,
            selected_attendee=selected_attendee,
        )
        output_path = self.build_certificate_output_path(course, scope=scope)
        return self.certificate_service.generate(certificates=payload, output_path=output_path)

    def build_signature_payload(
        self,
        course: object | Mapping[str, Any],
        attendees: Iterable[object | Mapping[str, Any]],
        *,
        scope: str,
        selected_attendee: object | Mapping[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        fecha = self.format_course_date(self._get(course, "curso_fecha"))
        selected_rows = self._scope_attendees(attendees, scope=scope, selected_attendee=selected_attendee)
        payload = [
            {
                "fecha": fecha,
                "nombre": str(self._get(item, "asistente") or ""),
                "nif": str(self._get(item, "nif") or ""),
                "empresa": str(self._get(item, "empresa") or ""),
            }
            for item in selected_rows
        ]
        if not payload:
            if scope == "confirmed":
                raise ValueError("No hay asistentes confirmados.")
            if scope == "selected":
                raise ValueError("Selecciona un asistente para generar una hoja individual.")
            raise ValueError("No hay asistentes para generar hojas de firma.")
        return payload

    def build_certificate_payload(
        self,
        course: object | Mapping[str, Any],
        attendees: Iterable[object | Mapping[str, Any]],
        *,
        scope: str,
        selected_attendee: object | Mapping[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        course_name = str(self._get(course, "curso_nombre") or "").strip()
        fecha_larga = self.format_course_date_long(self._get(course, "curso_fecha"))
        selected_rows = self._scope_attendees(attendees, scope=scope, selected_attendee=selected_attendee)
        payload = [
            {
                "asistente": str(self._get(item, "asistente") or ""),
                "curso": course_name,
                "fecha": f"Arinaga, {fecha_larga}" if fecha_larga else "",
            }
            for item in selected_rows
        ]
        if not payload:
            if scope == "confirmed":
                raise ValueError("No hay asistentes confirmados.")
            if scope == "selected":
                raise ValueError("Selecciona un asistente para generar un certificado individual.")
            raise ValueError("No hay asistentes para generar certificados.")
        return payload

    def build_signature_output_path(self, course: object | Mapping[str, Any], *, scope: str, template_key: str) -> Path:
        safe_name = self._safe_name(self._get(course, "curso_nombre"))
        suffix = self._scope_suffix(scope)
        return self.signature_service.DEFAULT_OUTPUT_DIR / f"consent_{template_key}_{safe_name}_{suffix}.pdf"

    def build_certificate_output_path(self, course: object | Mapping[str, Any], *, scope: str) -> Path:
        safe_name = self._safe_name(self._get(course, "curso_nombre"))
        suffix = self._scope_suffix(scope)
        return self.certificate_service.DEFAULT_OUTPUT_DIR / f"certificado_{safe_name}_{suffix}.pdf"

    def format_course_date(self, course_date: object) -> str:
        try:
            if isinstance(course_date, datetime):
                value = course_date.date()
            elif isinstance(course_date, date):
                value = course_date
            else:
                value = None
            if value is None:
                raise TypeError
            return value.strftime("%d/%m/%Y")
        except Exception:
            return str(course_date or "").strip()

    def format_course_date_long(self, course_date: object) -> str:
        try:
            if isinstance(course_date, datetime):
                value = course_date.date()
            elif isinstance(course_date, date):
                value = course_date
            else:
                value = None
            if value is None:
                raise TypeError
            day = int(value.day)
            month = int(value.month)
            year = int(value.year)
        except Exception:
            return str(course_date or "").strip()
        month_names = {
            1: "enero",
            2: "febrero",
            3: "marzo",
            4: "abril",
            5: "mayo",
            6: "junio",
            7: "julio",
            8: "agosto",
            9: "septiembre",
            10: "octubre",
            11: "noviembre",
            12: "diciembre",
        }
        month_name = month_names.get(month, "")
        if not month_name:
            return f"{day:02d}/{month:02d}/{year:04d}"
        return f"{day} de {month_name} de {year}"

    def _scope_attendees(
        self,
        attendees: Iterable[object | Mapping[str, Any]],
        *,
        scope: str,
        selected_attendee: object | Mapping[str, Any] | None,
    ) -> list[object | Mapping[str, Any]]:
        rows = list(attendees or [])
        if scope == "selected":
            if selected_attendee is None:
                raise ValueError("Selecciona un asistente para generar una hoja individual.")
            return [selected_attendee]
        if scope == "confirmed":
            rows = [row for row in rows if bool(self._get(row, "status_confirmacion", False))]
        return rows

    def _scope_suffix(self, scope: str) -> str:
        return {"all": "todos", "confirmed": "confirmados", "selected": "seleccionado"}.get(scope, "todos")

    def _safe_name(self, value: object) -> str:
        text = str(value or "curso").strip() or "curso"
        return "".join(ch if ch.isalnum() else "_" for ch in text)[:42]

    def _get(self, value: object | Mapping[str, Any], key: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(key, default)
        return getattr(value, key, default)
