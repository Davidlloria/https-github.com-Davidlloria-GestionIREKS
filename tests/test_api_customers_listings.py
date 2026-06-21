from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

import app.services.customer_report_service as customer_report_service_module
from app.api.main import create_app
from app.models import Cliente, CodigoPostal, Isla, Localidad, Municipio, Provincia


TEST_ENGINE = None


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    global TEST_ENGINE
    TEST_ENGINE = create_engine(
        f"sqlite:///{tmp_path / 'customers-listings-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(TEST_ENGINE)
    monkeypatch.setattr(customer_report_service_module, "engine", TEST_ENGINE)
    monkeypatch.setattr(
        customer_report_service_module.OpenAISettingsService,
        "load",
        lambda self: {"api_key": "", "use_ai_translation": False},
    )
    return TestClient(create_app())


def _seed_customer_data(session: Session) -> None:
    session.add(Provincia(provincia_id="prov-1", provincia_nombre="Provincia Uno", provincia_codigo="P1"))
    session.add(Isla(isla_id="isla-1", provincia_id="prov-1", isla_nombre="Isla Uno", isla_codigo="I1", isla_iniciales="IU"))
    session.add(
        Municipio(
            municipio_id="mun-1",
            isla_id="isla-1",
            provincia_id="prov-1",
            municipio_nombre="Municipio Uno",
            municipio_codigo="M1",
        )
    )
    session.add(CodigoPostal(municipio_id="mun-1", codigo_postal="35001"))
    session.add(
        Localidad(
            localidad_id="loc-1",
            municipio_id="mun-1",
            localidad_nombre="Localidad Uno",
            codigo_postal="35001",
        )
    )
    session.add(
        Cliente(
            cliente_id="cli-1",
            cliente_codigo=101,
            cliente_nombre_comercial="Cliente Uno",
            cliente_tipo="directo",
            cliente_actividad="PANADERIA",
            cliente_direccion_isla_id="isla-1",
            cliente_direccion_municipio_id="mun-1",
            cliente_direccion_provincia_id="prov-1",
            cliente_direccion_localidad_id="loc-1",
            activo=True,
        )
    )
    session.commit()


def test_customer_listings_endpoint_returns_report_data(api_client: TestClient) -> None:
    assert TEST_ENGINE is not None
    with Session(TEST_ENGINE) as session:
        _seed_customer_data(session)

    response = api_client.post("/customers/listings", json={"prompt": "clientes activos"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["used_ai"] is False
    assert payload["source"] == "interprete local"
    assert payload["title"].startswith("Listado:")
    assert payload["headers"] == ["Cod.", "Nombre comercial", "Telefono", "Isla", "Tipo", "Activo"]
    assert payload["rows"] == [[101, "Cliente Uno", "", "Isla Uno", "directo", "Si"]]

    response_blank_island = api_client.post("/customers/listings", json={"prompt": 'clientes con isla = ""'})
    assert response_blank_island.status_code == 200
    payload_blank_island = response_blank_island.json()
    assert payload_blank_island["status"] == "ready"
    assert payload_blank_island["rows"]


def test_customer_listings_pdf_export_returns_pdf_file(api_client: TestClient) -> None:
    assert TEST_ENGINE is not None
    with Session(TEST_ENGINE) as session:
        _seed_customer_data(session)

    listing_response = api_client.post("/customers/listings", json={"prompt": "clientes activos"})
    assert listing_response.status_code == 200
    listing_payload = listing_response.json()

    pdf_response = api_client.post("/customers/listings/pdf", json=listing_payload)
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert pdf_response.content.startswith(b"%PDF")
    assert len(pdf_response.content) > 100
