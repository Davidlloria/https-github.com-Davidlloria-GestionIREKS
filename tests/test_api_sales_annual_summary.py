from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

import app.services.sales_annual_comparison_service as sales_annual_service_module
from app.api.main import create_app
from app.models import Cliente, Fabricante, Familia, IngredienteIreks, Subfamilia, VentaMensualRaw


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sales-annual-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(sales_annual_service_module, "engine", engine)
    return TestClient(create_app())


def _seed_sales_summary_data(session: Session) -> None:
    session.add(Cliente(cliente_id="cli-1", cliente_codigo=1, cliente_nombre_comercial="Cliente Uno", cliente_tipo="distribuidor"))

    session.add(Fabricante(fabricante_id="fab-1", fabricante_codigo=1, fabricante_nombre="Fabricante A"))
    session.add(Fabricante(fabricante_id="fab-2", fabricante_codigo=2, fabricante_nombre="Fabricante B"))

    session.add(
        Familia(
            articulo_familia_id="fam-1",
            fabricante_id="fab-1",
            articulo_familia_nombre="Familia A",
            articulo_familia_codigo="FA",
        )
    )
    session.add(
        Familia(
            articulo_familia_id="fam-2",
            fabricante_id="fab-2",
            articulo_familia_nombre="Familia B",
            articulo_familia_codigo="FB",
        )
    )

    session.add(
        Subfamilia(
            articulo_familia_id="fam-1",
            articulo_subfamilia_id="sub-1",
            articulo_subfamilia_nombre="Subfamilia A",
            articulo_subfamilia_codigo="SA",
        )
    )
    session.add(
        Subfamilia(
            articulo_familia_id="fam-2",
            articulo_subfamilia_id="sub-2",
            articulo_subfamilia_nombre="Subfamilia B",
            articulo_subfamilia_codigo="SB",
        )
    )

    session.add(
        IngredienteIreks(
            articulo_id="art-1",
            almacen_id="alm-1",
            fabricante_id="fab-1",
            articulo_referencia="D123",
            articulo_referencia_corta="D123",
            articulo_descripcion="Alpha Producto",
            articulo_familia_id="fam-1",
            articulo_subfamilia_id="sub-1",
        )
    )
    session.add(
        IngredienteIreks(
            articulo_id="art-2",
            almacen_id="alm-1",
            fabricante_id="fab-2",
            articulo_referencia="D456",
            articulo_referencia_corta="D456",
            articulo_descripcion="Beta Producto",
            articulo_familia_id="fam-2",
            articulo_subfamilia_id="sub-2",
        )
    )

    rows = [
        VentaMensualRaw(
            raw_id="raw-1",
            lote_id="lote-1",
            fuente="ireks",
            cliente_id="cli-1",
            periodo="2025-01",
            articulo_codigo_origen="D123",
            articulo_id="art-1",
            articulo_descripcion_origen="Alpha Producto",
            venta_kilos=10.0,
            venta_kilos_sc=2.0,
            venta_euros=12.0,
        ),
        VentaMensualRaw(
            raw_id="raw-2",
            lote_id="lote-2",
            fuente="ireks",
            cliente_id="cli-1",
            periodo="2026-01",
            articulo_codigo_origen="D123",
            articulo_id="art-1",
            articulo_descripcion_origen="Alpha Producto",
            venta_kilos=15.0,
            venta_kilos_sc=1.0,
            venta_euros=20.0,
        ),
        VentaMensualRaw(
            raw_id="raw-3",
            lote_id="lote-3",
            fuente="ireks",
            cliente_id="cli-1",
            periodo="2025-02",
            articulo_codigo_origen="D123",
            articulo_id="art-1",
            articulo_descripcion_origen="Alpha Producto",
            venta_kilos=1.0,
            venta_kilos_sc=0.0,
            venta_euros=1.0,
        ),
        VentaMensualRaw(
            raw_id="raw-4",
            lote_id="lote-4",
            fuente="ireks",
            cliente_id="cli-1",
            periodo="2026-02",
            articulo_codigo_origen="D123",
            articulo_id="art-1",
            articulo_descripcion_origen="Alpha Producto",
            venta_kilos=2.0,
            venta_kilos_sc=0.0,
            venta_euros=2.0,
        ),
        VentaMensualRaw(
            raw_id="raw-5",
            lote_id="lote-5",
            fuente="ireks",
            cliente_id="cli-1",
            periodo="2025-01",
            articulo_codigo_origen="D456",
            articulo_id="art-2",
            articulo_descripcion_origen="Beta Producto",
            venta_kilos=8.0,
            venta_kilos_sc=0.0,
            venta_euros=9.0,
        ),
        VentaMensualRaw(
            raw_id="raw-6",
            lote_id="lote-6",
            fuente="ireks",
            cliente_id="cli-1",
            periodo="2026-01",
            articulo_codigo_origen="D456",
            articulo_id="art-2",
            articulo_descripcion_origen="Beta Producto",
            venta_kilos=4.0,
            venta_kilos_sc=1.0,
            venta_euros=7.0,
        ),
        VentaMensualRaw(
            raw_id="raw-7",
            lote_id="lote-7",
            fuente="igsa",
            cliente_id="cli-1",
            periodo="2025-01",
            articulo_codigo_origen="D123",
            articulo_id="art-1",
            articulo_descripcion_origen="Alpha Producto",
            venta_kilos=5.0,
            venta_kilos_sc=1.0,
            venta_euros=0.0,
        ),
        VentaMensualRaw(
            raw_id="raw-8",
            lote_id="lote-8",
            fuente="igsa_pdf",
            cliente_id="cli-1",
            periodo="2026-01",
            articulo_codigo_origen="D123",
            articulo_id="art-1",
            articulo_descripcion_origen="Alpha Producto",
            venta_kilos=6.0,
            venta_kilos_sc=2.0,
            venta_euros=0.0,
        ),
        VentaMensualRaw(
            raw_id="raw-9",
            lote_id="lote-9",
            fuente="igsa_book",
            cliente_id="cli-1",
            periodo="2025-02",
            articulo_codigo_origen="D456",
            articulo_id="art-2",
            articulo_descripcion_origen="Beta Producto",
            venta_kilos=3.0,
            venta_kilos_sc=0.0,
            venta_euros=0.0,
        ),
        VentaMensualRaw(
            raw_id="raw-10",
            lote_id="lote-10",
            fuente="igsa",
            cliente_id="cli-1",
            periodo="2026-02",
            articulo_codigo_origen="D456",
            articulo_id="art-2",
            articulo_descripcion_origen="Beta Producto",
            venta_kilos=4.0,
            venta_kilos_sc=1.0,
            venta_euros=0.0,
        ),
    ]
    for row in rows:
        session.add(row)
    session.commit()


def test_sales_annual_summary_returns_rows_for_year(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    response = api_client.get("/sales/annual-summary", params={"year": 2026})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "ireks"
    assert payload["year"] == 2026
    assert payload["month"] == 0
    assert payload["acumulado"] is False
    assert payload["total"] == 2
    assert [row["nombre"] for row in payload["items"]] == ["Alpha Producto", "Beta Producto"]


def test_sales_annual_summary_filters_by_month_and_accumulated(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    month_response = api_client.get("/sales/annual-summary", params={"year": 2026, "month": 1})
    assert month_response.status_code == 200
    month_row = month_response.json()["items"][0]
    assert month_row["kilos_prev"] == 10.0
    assert month_row["kilos_curr"] == 15.0
    assert month_row["ventas_prev"] == 12.0
    assert month_row["ventas_curr"] == 20.0

    accumulated_response = api_client.get("/sales/annual-summary", params={"year": 2026, "month": 2, "acumulado": True})
    assert accumulated_response.status_code == 200
    accumulated_row = accumulated_response.json()["items"][0]
    assert accumulated_row["kilos_prev"] == 11.0
    assert accumulated_row["kilos_curr"] == 17.0
    assert accumulated_row["ventas_prev"] == 13.0
    assert accumulated_row["ventas_curr"] == 22.0


def test_sales_annual_summary_filters_by_client_and_product(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    client_response = api_client.get("/sales/annual-summary", params={"year": 2026, "cliente_id": "cli-1"})
    assert client_response.status_code == 200
    assert client_response.json()["total"] == 2

    product_response = api_client.get("/sales/annual-summary", params={"year": 2026, "articulo_id": "art-2"})
    assert product_response.status_code == 200
    product_payload = product_response.json()
    assert product_payload["total"] == 1
    assert product_payload["items"][0]["articulo_id"] == "art-2"

    text_response = api_client.get("/sales/annual-summary", params={"year": 2026, "producto_texto": "beta"})
    assert text_response.status_code == 200
    assert text_response.json()["items"][0]["articulo_id"] == "art-2"


def test_sales_annual_summary_filters_by_hierarchy(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    manufacturer_response = api_client.get("/sales/annual-summary", params={"year": 2026, "fabricante_id": "fab-2"})
    assert manufacturer_response.status_code == 200
    assert manufacturer_response.json()["total"] == 1
    assert manufacturer_response.json()["items"][0]["fabricante_id"] == "fab-2"

    family_response = api_client.get("/sales/annual-summary", params={"year": 2026, "familia_id": "fam-1"})
    assert family_response.status_code == 200
    assert family_response.json()["total"] == 1
    assert family_response.json()["items"][0]["familia_id"] == "fam-1"

    subfamily_response = api_client.get("/sales/annual-summary", params={"year": 2026, "subfamilia_id": "sub-2"})
    assert subfamily_response.status_code == 200
    assert subfamily_response.json()["total"] == 1
    assert subfamily_response.json()["items"][0]["subfamilia_id"] == "sub-2"


def test_sales_annual_summary_returns_empty_response_for_missing_year(api_client: TestClient) -> None:
    response = api_client.get("/sales/annual-summary", params={"year": 2030})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["items"] == []


def test_sales_annual_summary_order_is_stable(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    response = api_client.get("/sales/annual-summary", params={"year": 2026})
    assert response.status_code == 200
    assert [row["nombre"] for row in response.json()["items"]] == ["Alpha Producto", "Beta Producto"]


def test_sales_annual_summary_validates_query_params(api_client: TestClient) -> None:
    assert api_client.get("/sales/annual-summary", params={"year": 0}).status_code == 422
    assert api_client.get("/sales/annual-summary", params={"year": 2026, "month": 13}).status_code == 422


def test_sales_annual_summary_igsa_returns_rows_for_year(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    response = api_client.get("/sales/annual-summary/igsa", params={"year": 2026})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "igsa"
    assert payload["year"] == 2026
    assert payload["month"] == 0
    assert payload["acumulado"] is False
    assert payload["total"] == 2
    assert [row["nombre"] for row in payload["items"]] == ["Alpha Producto", "Beta Producto"]


def test_sales_annual_summary_igsa_filters_by_month_and_accumulated(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    month_response = api_client.get("/sales/annual-summary/igsa", params={"year": 2026, "month": 1})
    assert month_response.status_code == 200
    month_row = month_response.json()["items"][0]
    assert month_row["kilos_prev"] == 5.0
    assert month_row["kilos_curr"] == 6.0

    accumulated_response = api_client.get("/sales/annual-summary/igsa", params={"year": 2026, "month": 2, "acumulado": True})
    assert accumulated_response.status_code == 200
    accumulated_row = accumulated_response.json()["items"][0]
    assert accumulated_row["kilos_prev"] == 5.0
    assert accumulated_row["kilos_curr"] == 6.0


def test_sales_annual_summary_igsa_filters_by_product_and_hierarchy(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    text_response = api_client.get("/sales/annual-summary/igsa", params={"year": 2026, "producto_texto": "beta"})
    assert text_response.status_code == 200
    assert text_response.json()["items"][0]["articulo_id"] == "art-2"

    manufacturer_response = api_client.get("/sales/annual-summary/igsa", params={"year": 2026, "fabricante_id": "fab-2"})
    assert manufacturer_response.status_code == 200
    assert manufacturer_response.json()["total"] == 1
    assert manufacturer_response.json()["items"][0]["fabricante_id"] == "fab-2"

    family_response = api_client.get("/sales/annual-summary/igsa", params={"year": 2026, "familia_id": "fam-1"})
    assert family_response.status_code == 200
    assert family_response.json()["total"] == 1
    assert family_response.json()["items"][0]["familia_id"] == "fam-1"

    subfamily_response = api_client.get("/sales/annual-summary/igsa", params={"year": 2026, "subfamilia_id": "sub-2"})
    assert subfamily_response.status_code == 200
    assert subfamily_response.json()["total"] == 1
    assert subfamily_response.json()["items"][0]["subfamilia_id"] == "sub-2"


def test_sales_annual_summary_igsa_returns_empty_response_for_missing_year(api_client: TestClient) -> None:
    response = api_client.get("/sales/annual-summary/igsa", params={"year": 2030})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["items"] == []


def test_sales_annual_summary_igsa_order_is_stable(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    response = api_client.get("/sales/annual-summary/igsa", params={"year": 2026})
    assert response.status_code == 200
    assert [row["nombre"] for row in response.json()["items"]] == ["Alpha Producto", "Beta Producto"]


def test_sales_annual_summary_igsa_validates_query_params(api_client: TestClient) -> None:
    assert api_client.get("/sales/annual-summary/igsa", params={"year": 0}).status_code == 422
    assert api_client.get("/sales/annual-summary/igsa", params={"year": 2026, "month": 13}).status_code == 422


def test_sales_filter_year_endpoints_return_available_years(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    ireks_years = api_client.get("/sales/annual-summary/years")
    assert ireks_years.status_code == 200
    assert ireks_years.json() == {
        "items": [
            {"year": 2026, "label": "2026"},
            {"year": 2025, "label": "2025"},
        ]
    }

    igsa_years = api_client.get("/sales/annual-summary/igsa/years")
    assert igsa_years.status_code == 200
    assert igsa_years.json() == {
        "items": [
            {"year": 2026, "label": "2026"},
            {"year": 2025, "label": "2025"},
        ]
    }


def test_sales_filter_catalog_endpoints_return_ireks_options(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    clients = api_client.get("/sales/annual-summary/filters/clients")
    assert clients.status_code == 200
    assert clients.json() == {
        "items": [
            {"id": "cli-1", "name": "Cliente Uno", "code": "1", "parent_id": ""}
        ]
    }

    products = api_client.get("/sales/annual-summary/filters/products")
    assert products.status_code == 200
    assert [row["id"] for row in products.json()["items"]] == ["art-1", "art-2"]
    assert products.json()["items"][0] == {"id": "art-1", "name": "Alpha Producto", "code": "D123", "parent_id": ""}

    manufacturers = api_client.get("/sales/annual-summary/filters/manufacturers")
    assert manufacturers.status_code == 200
    assert [row["id"] for row in manufacturers.json()["items"]] == ["fab-1", "fab-2"]
    assert manufacturers.json()["items"][0] == {"id": "fab-1", "name": "Fabricante A", "code": "1", "parent_id": ""}

    families = api_client.get("/sales/annual-summary/filters/families")
    assert families.status_code == 200
    assert [row["id"] for row in families.json()["items"]] == ["fam-1", "fam-2"]
    assert families.json()["items"][0] == {"id": "fam-1", "name": "Familia A", "code": "FA", "parent_id": "fab-1"}

    families_by_manufacturer = api_client.get("/sales/annual-summary/filters/families", params={"fabricante_id": "fab-1"})
    assert families_by_manufacturer.status_code == 200
    assert families_by_manufacturer.json()["items"] == [
        {"id": "fam-1", "name": "Familia A", "code": "FA", "parent_id": "fab-1"}
    ]

    subfamilies = api_client.get("/sales/annual-summary/filters/subfamilies")
    assert subfamilies.status_code == 200
    assert [row["id"] for row in subfamilies.json()["items"]] == ["sub-1", "sub-2"]
    assert subfamilies.json()["items"][0] == {"id": "sub-1", "name": "Subfamilia A", "code": "SA", "parent_id": "fam-1"}

    subfamilies_by_family = api_client.get("/sales/annual-summary/filters/subfamilies", params={"familia_id": "fam-2"})
    assert subfamilies_by_family.status_code == 200
    assert subfamilies_by_family.json()["items"] == [
        {"id": "sub-2", "name": "Subfamilia B", "code": "SB", "parent_id": "fam-2"}
    ]


def test_sales_filter_catalog_endpoints_return_igsa_options(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    manufacturers = api_client.get("/sales/annual-summary/igsa/filters/manufacturers")
    assert manufacturers.status_code == 200
    assert [row["id"] for row in manufacturers.json()["items"]] == ["fab-1", "fab-2"]

    families = api_client.get("/sales/annual-summary/igsa/filters/families")
    assert families.status_code == 200
    assert [row["id"] for row in families.json()["items"]] == ["fam-1", "fam-2"]
    assert families.json()["items"][0]["parent_id"] == "fab-1"

    families_by_manufacturer = api_client.get("/sales/annual-summary/igsa/filters/families", params={"fabricante_id": "fab-2"})
    assert families_by_manufacturer.status_code == 200
    assert families_by_manufacturer.json()["items"] == [
        {"id": "fam-2", "name": "Familia B", "code": "FB", "parent_id": "fab-2"}
    ]

    subfamilies = api_client.get("/sales/annual-summary/igsa/filters/subfamilies")
    assert subfamilies.status_code == 200
    assert [row["id"] for row in subfamilies.json()["items"]] == ["sub-1", "sub-2"]

    subfamilies_by_family = api_client.get("/sales/annual-summary/igsa/filters/subfamilies", params={"familia_id": "fam-1"})
    assert subfamilies_by_family.status_code == 200
    assert subfamilies_by_family.json()["items"] == [
        {"id": "sub-1", "name": "Subfamilia A", "code": "SA", "parent_id": "fam-1"}
    ]


def test_sales_filter_endpoints_return_empty_lists_and_stable_shape(api_client: TestClient) -> None:
    ireks_years = api_client.get("/sales/annual-summary/years")
    assert ireks_years.status_code == 200
    assert ireks_years.json() == {"items": []}

    igsa_years = api_client.get("/sales/annual-summary/igsa/years")
    assert igsa_years.status_code == 200
    assert igsa_years.json() == {"items": []}

    clients = api_client.get("/sales/annual-summary/filters/clients")
    assert clients.status_code == 200
    assert clients.json() == {"items": []}

    products = api_client.get("/sales/annual-summary/filters/products")
    assert products.status_code == 200
    assert products.json() == {"items": []}

    manufacturers = api_client.get("/sales/annual-summary/filters/manufacturers")
    assert manufacturers.status_code == 200
    assert manufacturers.json() == {"items": []}

    igsa_manufacturers = api_client.get("/sales/annual-summary/igsa/filters/manufacturers")
    assert igsa_manufacturers.status_code == 200
    assert igsa_manufacturers.json() == {"items": []}

    families = api_client.get("/sales/annual-summary/filters/families")
    assert families.status_code == 200
    assert families.json() == {"items": []}

    igsa_families = api_client.get("/sales/annual-summary/igsa/filters/families")
    assert igsa_families.status_code == 200
    assert igsa_families.json() == {"items": []}

    subfamilies = api_client.get("/sales/annual-summary/filters/subfamilies")
    assert subfamilies.status_code == 200
    assert subfamilies.json() == {"items": []}

    igsa_subfamilies = api_client.get("/sales/annual-summary/igsa/filters/subfamilies")
    assert igsa_subfamilies.status_code == 200
    assert igsa_subfamilies.json() == {"items": []}
