from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import app.services.ingredient_read_service as ingredient_read_service_module  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.models import (  # noqa: E402
    Distribuidor,
    Envase,
    Fabricante,
    Familia,
    IngredienteIreks,
    IngredienteStd,
    MateriaPrimaPrecio,
    Proveedor,
    Subfamilia,
)


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ingredients-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(ingredient_read_service_module, "engine", engine)
    return TestClient(create_app())


def _seed_generic_ingredients() -> None:
    with Session(ingredient_read_service_module.engine) as session:
        session.add(Distribuidor(distribuidor_id="dist-1", distribuidor_codigo=1, distribuidor_nombre_comercial="IGSA"))
        session.add(Proveedor(proveedor_id="prov-1", proveedor_codigo=1, proveedor_nombre_comercial="Proveedor Demo"))
        session.add(Fabricante(fabricante_id="fab-1", fabricante_codigo=1, fabricante_nombre="IREKS"))
        session.add(
            Familia(
                articulo_familia_id="fam-1",
                fabricante_id="fab-1",
                articulo_familia_nombre="Panificacion",
                articulo_familia_codigo="PAN",
            )
        )
        session.add(
            Subfamilia(
                articulo_familia_id="fam-1",
                articulo_subfamilia_id="sub-1",
                articulo_subfamilia_nombre="Mejorantes",
                articulo_subfamilia_codigo="MEJ",
            )
        )
        session.add(Envase(envase_id="env-1", envase_codigo=1, envase_nombre="Saco"))
        session.add(
            IngredienteIreks(
                id=1,
                almacen_id="alm-1",
                fabricante_id="fab-1",
                distribuidor_id="dist-1",
                articulo_id="ireks-article-1",
                articulo_referencia="IR-001",
                articulo_referencia_corta="IR1",
                articulo_descripcion="Mejorante IREKS",
                articulo_envase_id="env-1",
                articulo_envase_unidad_medida="kg",
                articulo_familia_id="fam-1",
                articulo_subfamilia_id="sub-1",
                articulo_status_activo=True,
                articulo_status_en_lista=True,
            )
        )
        session.add(
            IngredienteStd(
                articulo_id="std-article-1",
                articulo_referencia_distribuidor="STD-001",
                proveedor_id="prov-1",
                distribuidor_id="prov-1",
                articulo_descripcion="Harina fuerza",
                formato="SACO",
                formato_cantidad=25,
                formato_unidad="kg",
                pvp_formato=30.0,
                activo=True,
            )
        )
        session.add(MateriaPrimaPrecio(articulo_id="std-article-1", fecha_precio=date(2026, 5, 1), costo_neto=30.0))
        session.commit()


def test_ingredients_list_supports_data_and_query_filters(api_client: TestClient) -> None:
    _seed_generic_ingredients()

    listed = api_client.get("/ingredients")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert [row["id"] for row in listed.json()["items"]] == ["std:std-article-1", "ireks:1"]

    filtered = api_client.get("/ingredients", params={"q": "Harina"})
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()["items"]] == ["std:std-article-1"]

    paged = api_client.get("/ingredients", params={"limit": 1, "offset": 1})
    assert paged.status_code == 200
    assert paged.json()["items"][0]["id"] == "ireks:1"

    detail_std = api_client.get("/ingredients/std:std-article-1")
    assert detail_std.status_code == 200
    assert detail_std.json()["nombre"] == "Harina fuerza"
    assert detail_std.json()["source"] == "std"

    detail_ireks = api_client.get("/ingredients/ireks:1")
    assert detail_ireks.status_code == 200
    assert detail_ireks.json()["nombre"] == "Mejorante IREKS"
    assert detail_ireks.json()["source"] == "ireks"


def test_ingredients_list_empty_and_detail_not_found(api_client: TestClient) -> None:
    listed = api_client.get("/ingredients")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["total"] == 0
    assert listed.json()["limit"] == 1000
    assert listed.json()["offset"] == 0

    missing = api_client.get("/ingredients/missing-ingredient")
    assert missing.status_code == 404
