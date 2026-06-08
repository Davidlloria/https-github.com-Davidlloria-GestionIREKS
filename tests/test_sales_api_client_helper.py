from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

import app.services.sales_annual_comparison_service as sales_annual_service_module
from app.api.main import create_app
from app.models import Cliente, Fabricante, Familia, IngredienteIreks, Subfamilia, VentaMensualRaw
from app.schemas.sales import SalesAnnualSummaryResponse, SalesFilterOptionsResponse, SalesYearOptionsResponse
from tests.support.sales_api_client import SalesApiClient


@dataclass
class _FakeResponse:
    status_code: int
    payload: dict
    text: str = ""

    def json(self) -> dict:
        return self.payload


class _RecordingClient:
    def __init__(self, payload_by_path: dict[str, dict] | None = None) -> None:
        self.payload_by_path = payload_by_path or {}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, path: str, params: dict[str, object]) -> _FakeResponse:
        self.calls.append((path, dict(params)))
        payload = self.payload_by_path.get(path, {"items": []})
        return _FakeResponse(status_code=200, payload=payload)


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sales-api-client.db'}",
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
    session.add(
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
        )
    )
    session.add(
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
        )
    )
    session.add(
        VentaMensualRaw(
            raw_id="raw-3",
            lote_id="lote-3",
            fuente="igsa",
            cliente_id="cli-1",
            periodo="2025-01",
            articulo_codigo_origen="D123",
            articulo_id="art-1",
            articulo_descripcion_origen="Alpha Producto",
            venta_kilos=5.0,
            venta_kilos_sc=1.0,
            venta_euros=0.0,
        )
    )
    session.add(
        VentaMensualRaw(
            raw_id="raw-4",
            lote_id="lote-4",
            fuente="igsa",
            cliente_id="cli-1",
            periodo="2026-01",
            articulo_codigo_origen="D123",
            articulo_id="art-1",
            articulo_descripcion_origen="Alpha Producto",
            venta_kilos=6.0,
            venta_kilos_sc=2.0,
            venta_euros=0.0,
        )
    )
    session.commit()


def test_sales_api_client_parses_real_responses(api_client: TestClient) -> None:
    with Session(sales_annual_service_module.engine) as session:
        _seed_sales_summary_data(session)

    helper = SalesApiClient(api_client)

    summary = helper.annual_summary(year=2026, cliente_id="cli-1", articulo_id="art-1", producto_texto="alpha")
    assert isinstance(summary, SalesAnnualSummaryResponse)
    assert summary.source == "ireks"
    assert summary.total == 1
    assert summary.items[0].articulo_id == "art-1"
    assert summary.items[0].__class__.__module__ == "app.schemas.sales"

    igsa_summary = helper.annual_summary_igsa(year=2026, producto_texto="alpha")
    assert isinstance(igsa_summary, SalesAnnualSummaryResponse)
    assert igsa_summary.source == "igsa"
    assert igsa_summary.total == 1

    years = helper.years()
    years_igsa = helper.years_igsa()
    assert isinstance(years, SalesYearOptionsResponse)
    assert isinstance(years_igsa, SalesYearOptionsResponse)
    assert [item.year for item in years.items] == [2026, 2025]
    assert [item.year for item in years_igsa.items] == [2026, 2025]

    clients = helper.clients()
    products = helper.products()
    manufacturers = helper.manufacturers()
    families = helper.families("fab-1")
    subfamilies = helper.subfamilies("fam-1")
    assert isinstance(clients, SalesFilterOptionsResponse)
    assert isinstance(products, SalesFilterOptionsResponse)
    assert isinstance(manufacturers, SalesFilterOptionsResponse)
    assert isinstance(families, SalesFilterOptionsResponse)
    assert isinstance(subfamilies, SalesFilterOptionsResponse)
    assert clients.items[0].id == "cli-1"
    assert products.items[0].id == "art-1"
    assert manufacturers.items[0].id == "fab-1"
    assert families.items[0].parent_id == "fab-1"
    assert subfamilies.items[0].parent_id == "fam-1"


def test_sales_api_client_builds_expected_query_params() -> None:
    recorder = _RecordingClient(
        {
            "/sales/annual-summary": {"source": "ireks", "year": 2026, "month": 0, "acumulado": False, "total": 0, "items": []},
            "/sales/annual-summary/igsa": {"source": "igsa", "year": 2026, "month": 0, "acumulado": False, "total": 0, "items": []},
        }
    )
    helper = SalesApiClient(recorder)  # type: ignore[arg-type]

    helper.annual_summary(
        year=2026,
        month=2,
        acumulado=True,
        cliente_id="cli-1",
        articulo_id="art-1",
        producto_texto="alpha",
        fabricante_id="fab-1",
        familia_id="fam-1",
        subfamilia_id="sub-1",
    )
    helper.annual_summary_igsa(
        year=2026,
        month=1,
        acumulado=False,
        producto_texto="beta",
        fabricante_id="fab-2",
        familia_id="fam-2",
        subfamilia_id="sub-2",
    )
    helper.families("fab-1")
    helper.subfamilies("fam-1")

    assert recorder.calls == [
        (
            "/sales/annual-summary",
            {
                "year": 2026,
                "month": 2,
                "acumulado": True,
                "cliente_id": "cli-1",
                "articulo_id": "art-1",
                "producto_texto": "alpha",
                "fabricante_id": "fab-1",
                "familia_id": "fam-1",
                "subfamilia_id": "sub-1",
            },
        ),
        (
            "/sales/annual-summary/igsa",
            {
                "year": 2026,
                "month": 1,
                "acumulado": False,
                "producto_texto": "beta",
                "fabricante_id": "fab-2",
                "familia_id": "fam-2",
                "subfamilia_id": "sub-2",
            },
        ),
        ("/sales/annual-summary/filters/families", {"fabricante_id": "fab-1"}),
        ("/sales/annual-summary/filters/subfamilies", {"familia_id": "fam-1"}),
    ]


def test_sales_api_client_fails_explicitly_on_http_errors() -> None:
    client = TestClient(create_app())
    helper = SalesApiClient(client)

    with pytest.raises(RuntimeError, match="Sales API request failed"):
        helper.annual_summary(year=0)


