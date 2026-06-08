from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import app.services.course_service as course_service_module  # noqa: E402
from app.api.main import create_app  # noqa: E402
from app.models import Curso  # noqa: E402


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'courses-api.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(course_service_module, "engine", engine)
    return TestClient(create_app())


def test_courses_list_supports_data_and_query_filters(api_client: TestClient) -> None:
    with Session(course_service_module.engine) as session:
        session.add(Curso(curso_id="course-1", curso_nombre="Curso Primavera", curso_fecha=date(2026, 4, 15)))
        session.add(Curso(curso_id="course-2", curso_nombre="Curso Verano", curso_fecha=date(2026, 5, 20)))
        session.add(Curso(curso_id="course-3", curso_nombre="Curso Invierno", curso_fecha=date(2025, 1, 10)))
        session.commit()

    listed = api_client.get("/courses")
    assert listed.status_code == 200
    assert listed.json()["total"] == 3
    assert [row["curso_id"] for row in listed.json()["items"]] == ["course-2", "course-1", "course-3"]

    filtered = api_client.get("/courses", params={"q": "Verano"})
    assert filtered.status_code == 200
    assert [row["curso_id"] for row in filtered.json()["items"]] == ["course-2"]

    by_year = api_client.get("/courses", params={"year": 2026})
    assert by_year.status_code == 200
    assert [row["curso_id"] for row in by_year.json()["items"]] == ["course-2", "course-1"]

    detail = api_client.get("/courses/course-2")
    assert detail.status_code == 200
    assert detail.json()["curso_id"] == "course-2"
    assert detail.json()["curso_nombre"] == "Curso Verano"
    assert detail.json()["curso_fecha"] == "2026-05-20"


def test_courses_list_empty_and_detail_not_found(api_client: TestClient) -> None:
    listed = api_client.get("/courses")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["total"] == 0
    assert listed.json()["limit"] == 0
    assert listed.json()["offset"] == 0

    missing = api_client.get("/courses/missing-course")
    assert missing.status_code == 404
