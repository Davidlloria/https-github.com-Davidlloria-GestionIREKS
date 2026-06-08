from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import app.services.recipe_service as recipe_service_module  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.models import Receta  # noqa: E402


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'recipes-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(recipe_service_module, "engine", engine)
    return TestClient(create_app())


def test_recipes_list_supports_data_and_query_filters(api_client: TestClient) -> None:
    with Session(recipe_service_module.engine) as session:
        session.add(
            Receta(
                id=1,
                cliente_id="customer-1",
                nombre="Receta Dulce",
                codigo_receta="R-001",
                version="1.0",
                es_base=False,
                estado="borrador",
                observaciones="Primera receta",
                proceso="mezcla",
                masa_final_deseada_g=1000.0,
                peso_pieza_g=250.0,
                numero_piezas=4,
            )
        )
        session.add(
            Receta(
                id=2,
                cliente_id="customer-2",
                nombre="Receta Base",
                codigo_receta="R-002",
                version="2.0",
                es_base=True,
                estado="publicada",
                observaciones="Receta base",
                proceso="amasado",
                masa_final_deseada_g=500.0,
                peso_pieza_g=125.0,
                numero_piezas=2,
            )
        )
        session.commit()

    listed = api_client.get("/recipes")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert [row["id"] for row in listed.json()["items"]] == [1, 2]

    filtered = api_client.get("/recipes", params={"q": "Dulce"})
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()["items"]] == [1]

    by_customer = api_client.get("/recipes", params={"cliente_id": "customer-2"})
    assert by_customer.status_code == 200
    assert [row["id"] for row in by_customer.json()["items"]] == [2]

    by_base = api_client.get("/recipes", params={"es_base": True})
    assert by_base.status_code == 200
    assert [row["id"] for row in by_base.json()["items"]] == [2]

    detail = api_client.get("/recipes/1")
    assert detail.status_code == 200
    assert detail.json()["id"] == 1
    assert detail.json()["nombre"] == "Receta Dulce"
    assert detail.json()["estado"] == "borrador"
    assert "lineas" not in detail.json()


def test_recipes_list_empty_and_detail_not_found(api_client: TestClient) -> None:
    listed = api_client.get("/recipes")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["total"] == 0
    assert listed.json()["limit"] == 1000
    assert listed.json()["offset"] == 0

    missing = api_client.get("/recipes/999")
    assert missing.status_code == 404
