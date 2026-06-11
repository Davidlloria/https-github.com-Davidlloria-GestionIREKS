from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import app.services.technician_service as technician_service_module  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.models import Tecnico  # noqa: E402


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'technicians-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(technician_service_module, "engine", engine)
    return TestClient(create_app())


def test_technicians_list_supports_search_and_paging(api_client: TestClient) -> None:
    with Session(technician_service_module.engine) as session:
        session.add(
            Tecnico(
                tecnico_id="tech-1",
                tecnico_codigo=20,
                nombre="Ana",
                apellidos="Lopez",
                movil="600000001",
                interno="101",
                email="ana@example.com",
            )
        )
        session.add(
            Tecnico(
                tecnico_id="tech-2",
                tecnico_codigo=10,
                nombre="Bruno",
                apellidos="Perez",
                movil="600000002",
                interno="102",
                email="bruno@example.com",
            )
        )
        session.commit()

    listed = api_client.get("/technicians")
    assert listed.status_code == 200
    assert [row["tecnico_id"] for row in listed.json()["items"]] == ["tech-2", "tech-1"]
    assert listed.json()["total"] == 2

    filtered = api_client.get("/technicians", params={"q": "Ana"})
    assert filtered.status_code == 200
    assert [row["tecnico_id"] for row in filtered.json()["items"]] == ["tech-1"]

    paged = api_client.get("/technicians", params={"limit": 1, "offset": 1})
    assert paged.status_code == 200
    assert paged.json()["items"][0]["tecnico_id"] == "tech-1"
    assert paged.json()["limit"] == 1
    assert paged.json()["offset"] == 1


def test_technician_detail_and_missing_state(api_client: TestClient) -> None:
    with Session(technician_service_module.engine) as session:
        session.add(
            Tecnico(
                tecnico_id="tech-1",
                tecnico_codigo=10,
                nombre="Ana",
                apellidos="Lopez",
                movil="600000001",
                interno="101",
                email="ana@example.com",
            )
        )
        session.commit()

    detail = api_client.get("/technicians/tech-1")
    assert detail.status_code == 200
    assert detail.json()["nombre"] == "Ana"
    assert detail.json()["tecnico_codigo"] == 10

    missing = api_client.get("/technicians/missing-tech")
    assert missing.status_code == 404
