from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

import app.services.customer_agenda_service as customer_agenda_service_module
import app.services.customer_service as customer_service_module
from app.models import Cliente, ClienteAgenda
from app.services.customer_agenda_service import CustomerAgendaService
from app.services.customer_service import CustomerService


@pytest.fixture()
def isolated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'customer-agenda.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(customer_service_module, "engine", engine)
    return engine


def test_customer_agenda_service_crud_and_order(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        session.add(Cliente(cliente_id="cli-1", cliente_codigo=1, cliente_nombre_comercial="Cliente Demo"))
        session.commit()

    service = CustomerAgendaService(engine=isolated_engine)
    created_old = service.create_activity(
        {
            "cliente_id": "cli-1",
            "fecha_actividad": "2025-06-01",
            "tipo": "visita_prevista",
            "estado": "pendiente",
            "resumen": "Preparar visita comercial",
            "detalle": "Llamar antes de la visita.",
            "fecha_seguimiento": "2025-06-05",
            "prioridad": "alta",
        }
    )
    created_new = service.create_activity(
        {
            "cliente_id": "cli-1",
            "fecha_actividad": "2025-06-10",
            "tipo": "visita_realizada",
            "estado": "hecho",
            "resumen": "Visita realizada",
            "detalle": "Se revisaron próximos desarrollos.",
        }
    )

    rows = service.related_agenda("cli-1")
    assert [row.agenda_id for row in rows] == [created_new.agenda_id, created_old.agenda_id]
    assert rows[0].resumen == "Visita realizada"

    updated = service.update_activity(
        created_old.agenda_id,
        {
            "fecha_actividad": "2025-06-03",
            "tipo": "seguimiento",
            "estado": "aplazado",
            "resumen": "Seguimiento cambiado",
            "detalle": "Revisar propuesta.",
            "fecha_seguimiento": "",
            "prioridad": "normal",
        },
    )
    assert updated.estado == "aplazado"
    assert updated.fecha_seguimiento is None

    assert service.delete_activity(created_new.agenda_id) is True
    rows_after_delete = service.related_agenda("cli-1")
    assert len(rows_after_delete) == 1


def test_customer_delete_blockers_include_agenda_rows(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        session.add(Cliente(cliente_id="cli-1", cliente_codigo=1, cliente_nombre_comercial="Cliente Demo"))
        session.add(
            ClienteAgenda(
                agenda_id="ag-1",
                cliente_id="cli-1",
                fecha_actividad=date(2025, 6, 1),
                tipo="nota",
                estado="pendiente",
                resumen="Nota de seguimiento",
            )
        )
        session.commit()

    service = CustomerService()
    blockers = service.delete_blockers("cli-1")

    assert "1 actividad(es) de agenda" in blockers
