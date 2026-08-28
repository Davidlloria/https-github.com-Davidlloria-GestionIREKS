from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import AlbaranItem, IngredienteIreks, Pedido, PedidoIncidencia
from app.services.order_incident_service import OrderIncidentService
import app.services.order_incident_service as incident_module
import app.services.order_document_import_service as document_module
import app.services.order_service as order_module
from app.services.order_document_import_service import OrderDocumentImportService
from app.services.order_service import OrderService


@pytest.fixture
def incident_context(tmp_path: Path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'incidents.db'}")
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(incident_module, "engine", test_engine)
    with Session(test_engine) as session:
        session.add(Pedido(pedido_id="pedido-1", almacen_id="almacen-1", pedido_numero="P-1"))
        session.add(Pedido(pedido_id="pedido-2", almacen_id="almacen-1", pedido_numero="P-2"))
        session.add(
            IngredienteIreks(
                articulo_id="article-1",
                articulo_referencia_corta="5100",
                articulo_descripcion="MALTA TOSTADA X-70",
            )
        )
        session.add(
            AlbaranItem(
                item_id="received-1",
                pedido_id="pedido-1",
                albaran_id="delivery-1",
                albaran_numero="2026090116",
                albaran_fecha=date(2026, 8, 25),
                articulo_id="article-1",
                articulo_codigo="5100",
                articulo_cantidad=1,
                articulo_lote="A307695",
                articulo_caducidad=date(2027, 6, 18),
            )
        )
        session.commit()
    return OrderIncidentService(data_dir=tmp_path / "data"), test_engine


def test_incident_crud_and_received_article_filter(incident_context) -> None:
    service, _engine = incident_context

    options = service.list_received_articles("pedido-1")
    assert len(options) == 1
    assert options[0].codigo == "5100"
    assert options[0].lote == "A307695"

    first = service.create_incident(
        pedido_id="pedido-1",
        albaran_item_id="received-1",
        observaciones="Saco roto visible",
        fecha_incidencia=date(2026, 8, 26),
    )
    service.create_incident(
        pedido_id="pedido-1",
        albaran_item_id="received-1",
        observaciones="Segunda incidencia",
    )

    rows = service.list_incidents("pedido-1", "received-1")
    assert len(rows) == 2
    assert {row.incidencia.observaciones for row in rows} == {"Saco roto visible", "Segunda incidencia"}

    service.update_incident(first.incidencia_id, observaciones="Actualizada", fecha_incidencia=date(2026, 8, 27))
    updated = next(row for row in service.list_incidents("pedido-1") if row.incidencia.incidencia_id == first.incidencia_id)
    assert updated.incidencia.observaciones == "Actualizada"
    assert updated.incidencia.fecha_incidencia == date(2026, 8, 27)

    service.delete_incident(first.incidencia_id)
    assert len(service.list_incidents("pedido-1")) == 1


def test_incident_rejects_received_line_from_another_order(incident_context) -> None:
    service, _engine = incident_context

    with pytest.raises(ValueError, match="no pertenece"):
        service.create_incident(
            pedido_id="pedido-2",
            albaran_item_id="received-1",
            observaciones="No válida",
        )


def test_images_are_copied_with_relative_paths_and_removed(incident_context, tmp_path: Path) -> None:
    service, _engine = incident_context
    incident = service.create_incident(
        pedido_id="pedido-1",
        albaran_item_id="received-1",
        observaciones="Con imagen",
    )
    source = tmp_path / "foto original.jpg"
    source.write_bytes(b"fake-jpeg-content")

    image = service.add_image(incident.incidencia_id, source)
    saved_path = service.resolve_image_path(image.ruta_relativa)

    assert not Path(image.ruta_relativa).is_absolute()
    assert saved_path.read_bytes() == b"fake-jpeg-content"
    assert saved_path != source
    assert service.list_incidents("pedido-1")[0].image_count == 1

    source.unlink()
    assert saved_path.exists()
    service.delete_image(image.imagen_id)
    assert not saved_path.exists()


def test_delete_incident_cleans_managed_images(incident_context, tmp_path: Path) -> None:
    service, test_engine = incident_context
    incident = service.create_incident(
        pedido_id="pedido-1",
        albaran_item_id="received-1",
        observaciones="Con evidencia",
    )
    source = tmp_path / "evidencia.png"
    source.write_bytes(b"png")
    image = service.add_image(incident.incidencia_id, source)
    saved_path = service.resolve_image_path(image.ruta_relativa)

    service.delete_incident(incident.incidencia_id)

    assert not saved_path.exists()
    with Session(test_engine) as session:
        assert session.get(PedidoIncidencia, incident.incidencia_id) is None


def test_image_validation_rejects_unsupported_extension(incident_context, tmp_path: Path) -> None:
    service, _engine = incident_context
    incident = service.create_incident(
        pedido_id="pedido-1",
        albaran_item_id="received-1",
        observaciones="",
    )
    source = tmp_path / "documento.pdf"
    source.write_bytes(b"pdf")

    with pytest.raises(ValueError, match="Formato no admitido"):
        service.add_image(incident.incidencia_id, source)


def test_incidents_block_received_line_and_order_deletion(incident_context, monkeypatch) -> None:
    service, test_engine = incident_context
    service.create_incident(
        pedido_id="pedido-1",
        albaran_item_id="received-1",
        observaciones="Evidencia activa",
    )
    monkeypatch.setattr(document_module, "engine", test_engine)
    monkeypatch.setattr(order_module, "engine", test_engine)

    with pytest.raises(ValueError, match="incidencias registradas"):
        OrderDocumentImportService().delete_albaran_item("received-1")
    with pytest.raises(ValueError, match="incidencias registradas"):
        OrderService().delete_order("pedido-1")
