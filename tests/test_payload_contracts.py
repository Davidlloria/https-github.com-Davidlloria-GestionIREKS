from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

import app.services.contact_service as contact_service_module
import app.services.customer_service as customer_service_module
from app.models import Cliente
from app.schemas.contacts import ContactCreate, ContactDetail, ContactListItem, ContactListResponse, ContactUpdate
from app.schemas.customers import CustomerCreate, CustomerDetail, CustomerListItem, CustomerListResponse, CustomerUpdate
from app.services.contact_service import ContactService
from app.services.customer_service import CustomerService


@pytest.fixture()
def isolated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'contracts.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(customer_service_module, "engine", engine)
    monkeypatch.setattr(contact_service_module, "engine", engine)
    return engine


def test_customer_service_exposes_serializable_payloads(isolated_engine) -> None:
    service = CustomerService()

    created = service.create_from_payload(
        CustomerCreate(
            cliente_id="customer-1",
            cliente_nombre_comercial="Panaderia Norte",
            cliente_nombre_fiscal="Panaderia Norte SL",
            cliente_email="info@example.com",
        )
    )

    assert isinstance(created, CustomerDetail)
    assert created.cliente_id == "customer-1"
    assert created.cliente_codigo == 1
    assert created.to_payload()["cliente_nombre_comercial"] == "Panaderia Norte"

    rows = service.list_payload("Norte")
    assert isinstance(rows, CustomerListResponse)
    assert [type(row) for row in rows.items] == [CustomerListItem]
    assert rows.items[0].cliente_id == "customer-1"
    assert rows.total == 1

    updated = service.update_from_payload(
        "customer-1",
        CustomerUpdate(cliente_nombre_comercial="Panaderia Norte Centro", activo=False),
    )

    assert updated.cliente_nombre_comercial == "Panaderia Norte Centro"
    assert updated.cliente_nombre_fiscal == "Panaderia Norte SL"
    assert updated.activo is False


def test_contact_service_exposes_company_names_and_json_dates(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        session.add(
            Cliente(
                cliente_id="customer-1",
                cliente_codigo=10,
                cliente_nombre_comercial="Cliente Demo",
                cliente_nombre_fiscal="Cliente Demo SL",
            )
        )
        session.commit()

    service = ContactService()
    created = service.create_from_payload(
        ContactCreate(
            contacto_id="contact-1",
            cliente_id="customer-1",
            nombre="Ana",
            apellidos="Lopez",
            email="ana@example.com",
        )
    )

    assert isinstance(created, ContactDetail)
    assert created.cliente_nombre == "Cliente Demo"
    assert isinstance(created.to_payload()["created_at"], str)

    rows = service.list_payload("Cliente")
    assert isinstance(rows, ContactListResponse)
    assert [type(row) for row in rows.items] == [ContactListItem]
    assert rows.items[0].contacto_id == "contact-1"
    assert rows.items[0].cliente_nombre == "Cliente Demo"
    assert rows.total == 1

    updated = service.update_from_payload("contact-1", ContactUpdate(cargo="Compras"))
    assert updated.cargo == "Compras"
    assert updated.email == "ana@example.com"
