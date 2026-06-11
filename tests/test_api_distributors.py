from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import app.services.distributor_service as distributor_service_module  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.models import Distribuidor  # noqa: E402


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'distributors-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(distributor_service_module, "engine", engine)
    return TestClient(create_app())


def test_distributors_list_supports_search_and_paging(api_client: TestClient) -> None:
    with Session(distributor_service_module.engine) as session:
        session.add(
            Distribuidor(
                distribuidor_id="dist-1",
                distribuidor_codigo=20,
                distribuidor_razon_social="Distribuciones Norte SL",
                distribuidor_nombre_comercial="Norte",
                distribuidor_cif="B123",
                distribuidor_telefono="928000001",
                distribuidor_contacto="Ana",
            )
        )
        session.add(
            Distribuidor(
                distribuidor_id="dist-2",
                distribuidor_codigo=10,
                distribuidor_razon_social="Distribuciones Sur SL",
                distribuidor_nombre_comercial="Sur",
                distribuidor_cif="B456",
                distribuidor_telefono="928000002",
                distribuidor_contacto="Bruno",
            )
        )
        session.commit()

    listed = api_client.get("/distributors")
    assert listed.status_code == 200
    assert [row["distribuidor_id"] for row in listed.json()["items"]] == ["dist-2", "dist-1"]
    assert listed.json()["total"] == 2

    filtered = api_client.get("/distributors", params={"q": "Norte"})
    assert filtered.status_code == 200
    assert [row["distribuidor_id"] for row in filtered.json()["items"]] == ["dist-1"]

    paged = api_client.get("/distributors", params={"limit": 1, "offset": 1})
    assert paged.status_code == 200
    assert paged.json()["items"][0]["distribuidor_id"] == "dist-1"
    assert paged.json()["limit"] == 1
    assert paged.json()["offset"] == 1


def test_distributor_detail_and_missing_state(api_client: TestClient) -> None:
    with Session(distributor_service_module.engine) as session:
        session.add(
            Distribuidor(
                distribuidor_id="dist-1",
                distribuidor_codigo=10,
                distribuidor_razon_social="Distribuciones Norte SL",
                distribuidor_nombre_comercial="Norte",
                distribuidor_cif="B123",
                distribuidor_telefono="928000001",
                distribuidor_contacto="Ana",
            )
        )
        session.commit()

    detail = api_client.get("/distributors/dist-1")
    assert detail.status_code == 200
    assert detail.json()["distribuidor_nombre_comercial"] == "Norte"
    assert detail.json()["distribuidor_codigo"] == 10

    missing = api_client.get("/distributors/missing-dist")
    assert missing.status_code == 404
