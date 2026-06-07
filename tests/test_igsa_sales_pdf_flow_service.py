from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

import app.services.igsa_sales_pdf_flow_service as igsa_pdf_service_module
from app.models import Cliente, Distribuidor, IngredienteIreks, VentaImportLote, VentaMensualRaw
from app.services.igsa_sales_pdf_flow_service import IgsaSalesPdfFlowService
from app.services.sales_reconciliation_service import IgsaPdfParsedLine


@pytest.fixture()
def isolated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'igsa-pdf.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(igsa_pdf_service_module, "engine", engine)
    return engine


def _seed_import_data(session: Session) -> str:
    distributor_id = "dist-1"
    client_id = "cli-1"
    article_id = "art-1"
    session.add(
        Distribuidor(
            distribuidor_id=distributor_id,
            distribuidor_codigo=1,
            distribuidor_razon_social="IGSA Canarias",
            distribuidor_nombre_comercial="IGSA",
        )
    )
    session.add(Cliente(cliente_id=client_id, cliente_codigo=1, cliente_nombre_comercial="Cliente", distribuidor_id=distributor_id))
    session.add(
        IngredienteIreks(
            articulo_id=article_id,
            almacen_id="alm-1",
            distribuidor_id=distributor_id,
            articulo_referencia="D123",
            articulo_referencia_corta="D123",
            articulo_descripcion="Producto IREKS",
            articulo_envase_cantidad=4.0,
            articulo_envase_peso=2.5,
            articulo_envase_peso_total=2.5,
        )
    )
    session.commit()
    return client_id


def test_parse_pdf_files_and_extract_lines_normalize_text(tmp_path: Path) -> None:
    service = IgsaSalesPdfFlowService()
    pdf_path = tmp_path / "venta.pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")

    raw_text = (
        "Cabecera\n"
        "Ref. pedido: RP123 12/05/26\n"
        "Fecha entrega:\n"
        "D123456 Producto   IREKS 2,5 4 1,0 0 10,0 0,21 21,0Lote:L01Cons.Pref:12/05/26Carga:Camion 1\n"
    )

    service._read_pdf_text = lambda _path: raw_text  # type: ignore[method-assign]
    rows, errors = service.parse_igsa_pdf_files([pdf_path])
    assert errors == []
    assert len(rows) == 1
    assert rows[0].doc_type == "venta"
    assert rows[0].fecha == "12/05/26"
    assert rows[0].descripcion == "Producto IREKS"
    assert rows[0].codigo == "D123456"
    assert rows[0].kilos == pytest.approx(2.5)
    assert rows[0].envases == pytest.approx(4.0)
    assert rows[0].emb == pytest.approx(0.21)
    assert rows[0].iva == pytest.approx(21.0)


def test_parse_pdf_files_reports_blank_documents(tmp_path: Path) -> None:
    service = IgsaSalesPdfFlowService()
    pdf_path = tmp_path / "muestra.pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")
    service._read_pdf_text = lambda _path: "Solo texto sin líneas"  # type: ignore[method-assign]

    rows, errors = service.parse_igsa_pdf_files([pdf_path])
    assert rows == []
    assert errors and "Sin lineas detectadas" in errors[0]


def test_import_pdf_lines_with_fakes_and_empty_invalid_case(isolated_engine) -> None:
    service = IgsaSalesPdfFlowService()
    with Session(isolated_engine) as session:
        client_id = _seed_import_data(session)

    valid_line = IgsaPdfParsedLine(
        source_file="venta.pdf",
        doc_type="venta",
        fecha="12/05/26",
        ref_pedido="RP123",
        codigo="D123",
        descripcion="Producto IREKS",
        kilos=10.0,
        envases=4.0,
        emb=2.5,
        precio=1.0,
        descuento_pct=0.0,
        total=20.0,
        iva=0.21,
        lote="L01",
        carga="Camion 1",
        cons_pref="12/05/26",
    )
    callback_calls: list[int] = []
    result = service.import_igsa_pdf_lines(
        [valid_line],
        client_id,
        sync_warehouse_callback=lambda _session, inserted_rows: callback_calls.append(len(inserted_rows)),
    )
    assert result.ok is True
    assert result.imported == 1
    assert result.incidencias == 0
    assert "Importacion PDF IGSA completada." in result.message
    assert callback_calls == [1]

    with Session(isolated_engine) as session:
        assert session.exec(select(VentaImportLote).where(VentaImportLote.fuente == "igsa_pdf")).first() is not None
        raw_rows = list(session.exec(select(VentaMensualRaw).where(VentaMensualRaw.fuente == "igsa_pdf")))
        assert len(raw_rows) == 1

    invalid_line = IgsaPdfParsedLine(
        source_file="venta.pdf",
        doc_type="venta",
        fecha="xx",
        ref_pedido="RP123",
        codigo="BAD",
        descripcion="Producto IREKS",
        kilos=10.0,
        envases=4.0,
        emb=2.5,
        precio=1.0,
        descuento_pct=0.0,
        total=20.0,
        iva=0.21,
        lote="L01",
        carga="Camion 1",
        cons_pref="12/05/26",
    )
    empty_result = service.import_igsa_pdf_lines([invalid_line], client_id)
    assert empty_result.ok is False
    assert empty_result.imported == 0
    assert empty_result.incidencias == 0
    assert "No se detecto ninguna fecha valida (dd/mm/aa) en los PDFs." in empty_result.message
