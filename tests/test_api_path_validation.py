from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_order_json_import_rejects_missing_file(tmp_path: Path) -> None:
    response = _client().post(
        "/orders/import/json",
        json={"almacen_id": "alm-1", "source_path": str(tmp_path / "missing.json")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_path no existe."


def test_order_json_import_rejects_unexpected_extension(tmp_path: Path) -> None:
    source = tmp_path / "pedido.txt"
    source.write_text("{}", encoding="utf-8")

    response = _client().post(
        "/orders/import/json",
        json={"almacen_id": "alm-1", "source_path": str(source)},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_path debe usar extension: .json."


def test_order_pdf_import_rejects_unexpected_extension(tmp_path: Path) -> None:
    source = tmp_path / "albaran.json"
    source.write_text("{}", encoding="utf-8")

    response = _client().post(
        "/orders/order-1/import/albaran-pdf",
        json={"source_path": str(source)},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_path debe usar extension: .pdf."


def test_backup_rejects_directory_destination(tmp_path: Path) -> None:
    destination = tmp_path / "backup.db"
    destination.mkdir()

    response = _client().post(
        "/settings/maintenance/backup",
        json={"destination_path": str(destination)},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "destination_path no puede ser un directorio."
