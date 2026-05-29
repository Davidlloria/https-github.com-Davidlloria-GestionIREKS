from pathlib import Path

import pytest
from sqlmodel import SQLModel, create_engine

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import app.services.contact_service as contact_service_module  # noqa: E402
import app.services.customer_service as customer_service_module  # noqa: E402
from app.api.main import create_app  # noqa: E402


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(customer_service_module, "engine", engine)
    monkeypatch.setattr(contact_service_module, "engine", engine)
    return TestClient(create_app())


def test_customers_crud_endpoints(api_client: TestClient) -> None:
    created = api_client.post(
        "/customers",
        json={
            "cliente_id": "customer-1",
            "cliente_nombre_comercial": "Panaderia Norte",
            "cliente_nombre_fiscal": "Panaderia Norte SL",
            "cliente_email": "info@example.com",
        },
    )
    assert created.status_code == 201
    assert created.json()["cliente_id"] == "customer-1"
    assert created.json()["cliente_codigo"] == 1

    listed = api_client.get("/customers", params={"q": "Norte"})
    assert listed.status_code == 200
    assert [row["cliente_id"] for row in listed.json()] == ["customer-1"]

    updated = api_client.patch(
        "/customers/customer-1",
        json={"cliente_nombre_comercial": "Panaderia Norte Centro", "activo": False},
    )
    assert updated.status_code == 200
    assert updated.json()["cliente_nombre_comercial"] == "Panaderia Norte Centro"
    assert updated.json()["activo"] is False

    detail = api_client.get("/customers/customer-1")
    assert detail.status_code == 200
    assert detail.json()["cliente_nombre_fiscal"] == "Panaderia Norte SL"

    deleted = api_client.delete("/customers/customer-1")
    assert deleted.status_code == 204
    assert api_client.get("/customers/customer-1").status_code == 404


def test_contacts_crud_endpoints_include_company_payload(api_client: TestClient) -> None:
    api_client.post(
        "/customers",
        json={
            "cliente_id": "customer-1",
            "cliente_nombre_comercial": "Cliente Demo",
            "cliente_nombre_fiscal": "Cliente Demo SL",
        },
    )

    created = api_client.post(
        "/contacts",
        json={
            "contacto_id": "contact-1",
            "cliente_id": "customer-1",
            "nombre": "Ana",
            "apellidos": "Lopez",
            "email": "ana@example.com",
        },
    )
    assert created.status_code == 201
    assert created.json()["contacto_id"] == "contact-1"
    assert created.json()["cliente_nombre"] == "Cliente Demo"
    assert isinstance(created.json()["created_at"], str)

    companies = api_client.get("/contacts/companies")
    assert companies.status_code == 200
    assert companies.json() == [{"cliente_id": "customer-1", "nombre": "Cliente Demo"}]

    listed = api_client.get("/contacts", params={"q": "Cliente"})
    assert listed.status_code == 200
    assert listed.json()[0]["contacto_id"] == "contact-1"
    assert listed.json()[0]["cliente_nombre"] == "Cliente Demo"

    updated = api_client.patch("/contacts/contact-1", json={"cargo": "Compras"})
    assert updated.status_code == 200
    assert updated.json()["cargo"] == "Compras"
    assert updated.json()["email"] == "ana@example.com"

    deleted = api_client.delete("/contacts/contact-1")
    assert deleted.status_code == 204
    assert api_client.get("/contacts/contact-1").status_code == 404
