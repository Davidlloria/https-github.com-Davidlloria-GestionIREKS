from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import app.services.contact_service as contact_service_module  # noqa: E402
import app.services.customer_service as customer_service_module  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.models import Asistente, Curso  # noqa: E402


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
    assert [row["cliente_id"] for row in listed.json()["items"]] == ["customer-1"]
    assert listed.json()["total"] == 1
    assert listed.json()["offset"] == 0

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


def test_customer_create_duplicate_id_returns_conflict(api_client: TestClient) -> None:
    first = api_client.post(
        "/customers",
        json={
            "cliente_id": "customer-dup",
            "cliente_nombre_comercial": "Cliente Duplicado",
            "cliente_nombre_fiscal": "Cliente Duplicado SL",
        },
    )
    assert first.status_code == 201

    second = api_client.post(
        "/customers",
        json={
            "cliente_id": "customer-dup",
            "cliente_nombre_comercial": "Cliente Duplicado 2",
            "cliente_nombre_fiscal": "Cliente Duplicado 2 SL",
        },
    )
    assert second.status_code == 409


def test_customers_list_supports_limit_and_offset(api_client: TestClient) -> None:
    for idx, name in enumerate(["Cliente A", "Cliente B", "Cliente C"], start=1):
        created = api_client.post(
            "/customers",
            json={
                "cliente_id": f"customer-{idx}",
                "cliente_nombre_comercial": name,
                "cliente_nombre_fiscal": f"{name} SL",
            },
        )
        assert created.status_code == 201

    response = api_client.get("/customers", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert [row["cliente_id"] for row in response.json()["items"]] == ["customer-2"]
    assert response.json()["total"] == 3
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1


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
    assert listed.json()["items"][0]["contacto_id"] == "contact-1"
    assert listed.json()["items"][0]["cliente_nombre"] == "Cliente Demo"
    assert listed.json()["total"] == 1

    updated = api_client.patch("/contacts/contact-1", json={"cargo": "Compras"})
    assert updated.status_code == 200
    assert updated.json()["cargo"] == "Compras"
    assert updated.json()["email"] == "ana@example.com"

    deleted = api_client.delete("/contacts/contact-1")
    assert deleted.status_code == 204
    assert api_client.get("/contacts/contact-1").status_code == 404


def test_contacts_list_supports_company_limit_and_offset(api_client: TestClient) -> None:
    for idx in (1, 2):
        created_customer = api_client.post(
            "/customers",
            json={
                "cliente_id": f"customer-{idx}",
                "cliente_nombre_comercial": f"Cliente {idx}",
                "cliente_nombre_fiscal": f"Cliente {idx} SL",
            },
        )
        assert created_customer.status_code == 201

    for idx, customer_id in enumerate(("customer-1", "customer-1", "customer-2"), start=1):
        created_contact = api_client.post(
            "/contacts",
            json={
                "contacto_id": f"contact-{idx}",
                "contacto_codigo": idx,
                "cliente_id": customer_id,
                "nombre": f"Nombre {idx}",
            },
        )
        assert created_contact.status_code == 201

    response = api_client.get("/contacts", params={"cliente_id": "customer-1", "limit": 1, "offset": 1})

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 1
    assert [row["contacto_id"] for row in response.json()["items"]] == ["contact-2"]


def test_contact_create_duplicate_id_returns_conflict(api_client: TestClient) -> None:
    customer = api_client.post(
        "/customers",
        json={
            "cliente_id": "customer-dup-contact",
            "cliente_nombre_comercial": "Cliente Contacto",
            "cliente_nombre_fiscal": "Cliente Contacto SL",
        },
    )
    assert customer.status_code == 201

    first = api_client.post(
        "/contacts",
        json={
            "contacto_id": "contact-dup",
            "cliente_id": "customer-dup-contact",
            "nombre": "Ana",
        },
    )
    assert first.status_code == 201

    second = api_client.post(
        "/contacts",
        json={
            "contacto_id": "contact-dup",
            "cliente_id": "customer-dup-contact",
            "nombre": "Luis",
        },
    )
    assert second.status_code == 409


def test_contact_create_with_unknown_customer_returns_bad_request(api_client: TestClient) -> None:
    created = api_client.post(
        "/contacts",
        json={
            "contacto_id": "contact-invalid-customer",
            "cliente_id": "missing-customer",
            "nombre": "Ana",
        },
    )
    assert created.status_code == 400
    assert "cliente" in created.json()["detail"].lower()


def test_contact_update_with_unknown_customer_returns_bad_request(api_client: TestClient) -> None:
    api_client.post(
        "/customers",
        json={
            "cliente_id": "customer-1",
            "cliente_nombre_comercial": "Cliente Demo",
            "cliente_nombre_fiscal": "Cliente Demo SL",
        },
    )
    api_client.post(
        "/contacts",
        json={
            "contacto_id": "contact-1",
            "cliente_id": "customer-1",
            "nombre": "Ana",
        },
    )

    updated = api_client.patch("/contacts/contact-1", json={"cliente_id": "missing-customer"})
    assert updated.status_code == 400
    assert "cliente" in updated.json()["detail"].lower()


def test_customer_delete_with_contact_returns_conflict(api_client: TestClient) -> None:
    api_client.post(
        "/customers",
        json={
            "cliente_id": "customer-1",
            "cliente_nombre_comercial": "Cliente Demo",
            "cliente_nombre_fiscal": "Cliente Demo SL",
        },
    )
    api_client.post(
        "/contacts",
        json={
            "contacto_id": "contact-1",
            "cliente_id": "customer-1",
            "nombre": "Ana",
        },
    )

    response = api_client.delete("/customers/customer-1")

    assert response.status_code == 409
    assert "contacto" in response.json()["detail"]


def test_contact_delete_with_course_attendance_returns_conflict(api_client: TestClient) -> None:
    api_client.post(
        "/customers",
        json={
            "cliente_id": "customer-1",
            "cliente_nombre_comercial": "Cliente Demo",
            "cliente_nombre_fiscal": "Cliente Demo SL",
        },
    )
    api_client.post(
        "/contacts",
        json={
            "contacto_id": "contact-1",
            "cliente_id": "customer-1",
            "nombre": "Ana",
        },
    )
    with Session(contact_service_module.engine) as session:
        session.add(Curso(curso_id="course-1", curso_nombre="Curso API"))
        session.add(Asistente(curso_id="course-1", contacto_id="contact-1", cliente_id="customer-1"))
        session.commit()

    response = api_client.delete("/contacts/contact-1")

    assert response.status_code == 409
    assert "asistente" in response.json()["detail"]
