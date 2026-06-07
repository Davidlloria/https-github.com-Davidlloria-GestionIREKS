from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from sqlmodel import create_engine

from app.services.course_attendee_flow_service import CourseAttendeeFlowService


@dataclass
class _FakeCourseVM:
    list_result: list[object] = field(default_factory=list)
    add_result: object = field(default_factory=object)
    remove_result: bool = True
    set_result: object = field(default_factory=object)
    update_result: object = field(default_factory=object)
    raise_on_add: Exception | None = None
    raise_on_set: Exception | None = None
    raise_on_update: Exception | None = None
    calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def list_attendees(self, session, curso_id: str):
        self.calls.append(("list_attendees", (session, curso_id)))
        return self.list_result

    def add_attendee(
        self,
        session,
        curso_id: str,
        contacto_id: str,
        cliente_id: str,
        observaciones: str = "",
        status_confirmacion: bool = False,
    ):
        self.calls.append(
            (
                "add_attendee",
                (session, curso_id, contacto_id, cliente_id, observaciones, status_confirmacion),
            )
        )
        if self.raise_on_add is not None:
            raise self.raise_on_add
        return self.add_result

    def remove_attendee(self, session, curso_id: str, contacto_id: str) -> bool:
        self.calls.append(("remove_attendee", (session, curso_id, contacto_id)))
        return self.remove_result

    def set_attendee_confirmation(self, session, curso_id: str, contacto_id: str, status: bool):
        self.calls.append(("set_attendee_confirmation", (session, curso_id, contacto_id, status)))
        if self.raise_on_set is not None:
            raise self.raise_on_set
        return self.set_result

    def update_attendee_observaciones(self, session, curso_id: str, contacto_id: str, observaciones: str):
        self.calls.append(("update_attendee_observaciones", (session, curso_id, contacto_id, observaciones)))
        if self.raise_on_update is not None:
            raise self.raise_on_update
        return self.update_result


@dataclass
class _FakeImportService:
    rows: list[dict[str, object]] = field(default_factory=list)
    calls: list[dict[str, object]] = field(default_factory=list)

    def import_with_schema(self, *, file_path, schema, create_fn, required_fields, aliases=None):
        self.calls.append(
            {
                "file_path": file_path,
                "schema": schema,
                "required_fields": required_fields,
                "aliases": aliases,
            }
        )
        errors: list[str] = []
        imported = 0
        for row in self.rows:
            try:
                create_fn(row)
                imported += 1
            except Exception as exc:  # pragma: no cover - defensive mirror of ImportService
                errors.append(str(exc))
        return imported, errors


def _service(
    *,
    vm: _FakeCourseVM | None = None,
    import_service: _FakeImportService | None = None,
) -> CourseAttendeeFlowService:
    engine = create_engine("sqlite://")
    return CourseAttendeeFlowService(
        engine=engine,
        course_vm=vm or _FakeCourseVM(),
        import_service=import_service or _FakeImportService(),
    )


def test_list_attendees_delegates_to_viewmodel() -> None:
    vm = _FakeCourseVM(list_result=["row-1", "row-2"])
    service = _service(vm=vm)

    result = service.list_attendees("course-1")

    assert result == ["row-1", "row-2"]
    assert vm.calls[0][0] == "list_attendees"
    assert vm.calls[0][1][1] == "course-1"


def test_add_attendee_delegates_to_viewmodel() -> None:
    vm = _FakeCourseVM(add_result="added")
    service = _service(vm=vm)

    result = service.add_attendee("course-1", "contact-1", "customer-1", " notes ", True)

    assert result == "added"
    assert vm.calls[0][0] == "add_attendee"
    assert vm.calls[0][1][1:] == ("course-1", "contact-1", "customer-1", " notes ", True)


def test_remove_attendee_delegates_to_viewmodel() -> None:
    vm = _FakeCourseVM(remove_result=False)
    service = _service(vm=vm)

    result = service.remove_attendee("course-1", "contact-1")

    assert result is False
    assert vm.calls[0][0] == "remove_attendee"


def test_set_attendee_confirmation_delegates_to_viewmodel() -> None:
    vm = _FakeCourseVM(set_result="confirmed")
    service = _service(vm=vm)

    result = service.set_attendee_confirmation("course-1", "contact-1", True)

    assert result == "confirmed"
    assert vm.calls[0][0] == "set_attendee_confirmation"
    assert vm.calls[0][1][1:] == ("course-1", "contact-1", True)


def test_update_attendee_observaciones_delegates_to_viewmodel() -> None:
    vm = _FakeCourseVM(update_result="updated")
    service = _service(vm=vm)

    result = service.update_attendee_observaciones("course-1", "contact-1", "  nota  ")

    assert result == "updated"
    assert vm.calls[0][0] == "update_attendee_observaciones"
    assert vm.calls[0][1][1:] == ("course-1", "contact-1", "  nota  ")


def test_import_attendees_builds_schema_and_delegates_each_row(tmp_path: Path) -> None:
    vm = _FakeCourseVM(add_result="added")
    import_service = _FakeImportService(
        rows=[
            {
                "curso_id": " course-1 ",
                "contacto_id": " contact-1 ",
                "cliente_id": " customer-1 ",
                "observaciones": "  nota  ",
                "status_confirmacion": True,
            },
            {
                "curso_id": "course-2",
                "contacto_id": "contact-2",
                "cliente_id": "customer-2",
            },
        ]
    )
    service = _service(vm=vm, import_service=import_service)

    imported, errors = service.import_attendees(tmp_path / "attendees.xlsx")

    assert imported == 2
    assert errors == []
    assert import_service.calls[0]["required_fields"] == ["curso_id", "contacto_id", "cliente_id"]
    assert vm.calls[0][0] == "add_attendee"
    assert vm.calls[0][1][1:] == ("course-1", "contact-1", "customer-1", "nota", True)
    assert vm.calls[1][1][1:] == ("course-2", "contact-2", "customer-2", "", False)


def test_add_attendee_invalid_data_propagates_viewmodel_error() -> None:
    vm = _FakeCourseVM(raise_on_add=ValueError("Curso no encontrado"))
    service = _service(vm=vm)

    with pytest.raises(ValueError, match="Curso no encontrado"):
        service.add_attendee("missing-course", "contact-1", "customer-1")
