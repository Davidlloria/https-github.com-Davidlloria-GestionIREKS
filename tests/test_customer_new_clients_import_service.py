from __future__ import annotations

from openpyxl import Workbook
from sqlmodel import SQLModel, Session, create_engine

from app.models import Cliente
from app.services import customer_new_clients_import_service as import_service
from app.services.customer_new_clients_import_service import CustomerNewClientsImportPreviewService


def _isolated_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'customers-import-preview.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _write_workbook(path, rows: list[list[object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["UUID", "Codigo", "Codigo distribuidor", "Nombre comercial"])
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_preview_classifies_existing_updates_and_new_customers(tmp_path, monkeypatch) -> None:
    engine = _isolated_engine(tmp_path)
    monkeypatch.setattr(import_service, "engine", engine)
    with Session(engine) as session:
        session.add(
            Cliente(
                cliente_id="existing-id",
                cliente_codigo=18,
                cliente_codigo_distribuidor=None,
                cliente_nombre_comercial="Nombre antiguo",
            )
        )
        session.add(
            Cliente(
                cliente_id="other-id",
                cliente_codigo=22,
                cliente_nombre_comercial="Otro cliente",
            )
        )
        session.commit()

    workbook_path = tmp_path / "clientes.xlsx"
    _write_workbook(
        workbook_path,
        [
            ["existing-id", 18, "9001", "Nombre nuevo"],
            ["", "", "9002 003", "Cliente nuevo"],
        ],
    )

    result = CustomerNewClientsImportPreviewService().preview(workbook_path)

    assert result.total_rows == 2
    assert result.updates == 1
    assert result.creates == 1
    assert result.errors == 0
    update = result.items[0]
    assert update.action == "update"
    assert update.cliente_id == "existing-id"
    assert update.cliente_codigo_actual == 18
    assert update.cliente_codigo_propuesto == 18
    assert update.cliente_codigo_distribuidor == "9001"
    assert update.nombre_comercial_actual == "Nombre antiguo"
    assert update.nombre_comercial_propuesto == "Nombre nuevo"
    create = result.items[1]
    assert create.action == "create"
    assert create.cliente_codigo_propuesto == 23
    assert create.cliente_codigo_distribuidor == "9002-003"
    assert create.nombre_comercial_propuesto == "Cliente nuevo"


def test_preview_reports_blocking_incidents(tmp_path, monkeypatch) -> None:
    engine = _isolated_engine(tmp_path)
    monkeypatch.setattr(import_service, "engine", engine)
    with Session(engine) as session:
        session.add(
            Cliente(
                cliente_id="existing-id",
                cliente_codigo=18,
                cliente_nombre_comercial="Nombre antiguo",
            )
        )
        session.commit()

    workbook_path = tmp_path / "clientes.xlsx"
    _write_workbook(
        workbook_path,
        [
            ["missing-id", 99, "9001", "No existe"],
            ["existing-id", 19, "9002", "Codigo no coincide"],
            ["", 55, "9003", "Nuevo con codigo"],
            ["", "", "", ""],
            ["", "", "abc", "Codigo invalido"],
            ["", "", "9004", ""],
        ],
    )

    result = CustomerNewClientsImportPreviewService().preview(workbook_path)

    assert result.total_rows == 5
    assert result.errors == 5
    assert result.creates == 0
    messages = [" ".join(item.messages) for item in result.items]
    assert any("UUID no encontrado" in message for message in messages)
    assert any("Codigo interno no coincide" in message for message in messages)
    assert any("Cliente nuevo con columna B informada" in message for message in messages)
    assert any("Codigo de cliente de distribuidor no valido" in message for message in messages)
    assert any("Falta nombre comercial" in message for message in messages)


def test_apply_updates_existing_and_creates_new_customers(tmp_path, monkeypatch) -> None:
    engine = _isolated_engine(tmp_path)
    monkeypatch.setattr(import_service, "engine", engine)
    with Session(engine) as session:
        session.add(
            Cliente(
                cliente_id="existing-id",
                cliente_codigo=18,
                cliente_nombre_comercial="Nombre antiguo",
            )
        )
        session.commit()

    workbook_path = tmp_path / "clientes.xlsx"
    _write_workbook(
        workbook_path,
        [
            ["existing-id", 18, "9001 002", "Nombre nuevo"],
            ["", "", "9002", "Cliente nuevo"],
        ],
    )

    result = CustomerNewClientsImportPreviewService().apply(workbook_path)

    assert result.updated == 1
    assert result.created == 1
    with Session(engine) as session:
        customers = {
            customer.cliente_codigo: customer
            for customer in session.query(Cliente).order_by(Cliente.cliente_codigo).all()
        }
    assert customers[18].cliente_codigo_distribuidor == "9001-002"
    assert customers[18].cliente_nombre_comercial == "Nombre nuevo"
    assert customers[19].cliente_codigo_distribuidor == "9002"
    assert customers[19].cliente_nombre_comercial == "Cliente nuevo"
