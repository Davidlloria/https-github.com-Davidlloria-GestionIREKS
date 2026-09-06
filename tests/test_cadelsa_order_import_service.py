from datetime import date

import fitz
import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Cliente, Distribuidor, IngredienteIreks, Pedido, PedidoItem, ReferenciaDistribuidor
from app.services import cadelsa_order_import_service as module
from app.services import order_service, order_document_import_service
from app.services.cadelsa_order_import_service import CadelsaOrderImportService


TEXT = """CADELSA - Lanzarote
Fecha pedido: 04.09.26 servicio 25.09.26
Nº Pedido: LZ 38.840
Artículo-Descripción Cantidad FMT Cantidad U.B.
------------------------------------------------
00000505
PRODUCTO PRUEBA 12,5K
60,00 UNI
60,00
00005778
AROMA PRUEBA 500G
2,00 UNI
2,00
PIE PEDIDO
OBSERVACIONES
"""


@pytest.fixture
def catalog(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    for target in (module, order_service, order_document_import_service):
        monkeypatch.setattr(target, "engine", engine)
    with Session(engine) as session:
        session.add(Cliente(cliente_id="cad", cliente_codigo=1, cliente_nombre_comercial="CADELSA LZA", cliente_tipo="directo"))
        session.add(Distribuidor(distribuidor_id="igsa", distribuidor_nombre_comercial="IGSA"))
        session.add(Distribuidor(distribuidor_id="other", distribuidor_nombre_comercial="Otro"))
        for code, kg in [("505", 12.5), ("5778", 0.5)]:
            session.add(IngredienteIreks(articulo_id=code, articulo_referencia="I" + code, articulo_descripcion="Producto " + code, articulo_envase_peso_total=kg))
            session.add(ReferenciaDistribuidor(articulo_id=code, distribuidor_id="igsa", articulo_referencia_distribuidor=code))
        session.add(ReferenciaDistribuidor(articulo_id="5778", distribuidor_id="other", articulo_referencia_distribuidor="505"))
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "pedido.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((40, 40), TEXT)
        doc.save(path)
    return path


def test_preview_and_save_use_igsa_user_date_and_internal_number(catalog, pdf):
    service = CadelsaOrderImportService()
    preview = service.preview(pdf, "cad")
    assert [r.article_id for r in preview.lines] == ["505", "5778"]
    assert not any(r.issue for r in preview.lines)
    assert preview.lines[0].source.units == 60
    assert preview.lines[1].source.weight_kg == 0.5
    with Session(catalog) as session:
        assert not session.exec(select(Pedido)).all()
    order_id = service.save(preview, date(2026, 10, 7))
    with Session(catalog) as session:
        order = session.get(Pedido, order_id)
        assert order.pedido_fecha == date(2026, 10, 7)
        assert order.pedido_numero.startswith("CAD-")
        assert order.almacen_id == "cad"
        assert order.pedido_ref == preview.source_ref
        items = session.exec(select(PedidoItem)).all()
        assert sorted(i.articulo_cantidad for i in items) == [2, 60]
        assert all(i.pedido_numero == order.pedido_numero for i in items)
    with pytest.raises(ValueError, match="ya se ha importado"):
        service.save(preview, date.today())
    with pytest.raises(ValueError, match="ya se ha importado"):
        service.preview(pdf, "cad")


@pytest.mark.parametrize("change", ["missing", "ambiguous", "weight", "inactive"])
def test_mapping_issues_block_entire_order(catalog, pdf, change):
    with Session(catalog) as session:
        if change == "missing":
            session.delete(session.get(ReferenciaDistribuidor, ("505", "igsa")))
        elif change == "ambiguous":
            ref = session.get(ReferenciaDistribuidor, ("5778", "igsa"))
            ref.articulo_referencia_distribuidor = "00000505"
            session.add(ref)
        else:
            product = session.exec(select(IngredienteIreks).where(IngredienteIreks.articulo_id == "505")).one()
            if change == "weight":
                product.articulo_envase_peso_total = 25
            else:
                product.articulo_status_activo = False
            session.add(product)
        session.commit()
    service = CadelsaOrderImportService()
    preview = service.preview(pdf, "cad")
    assert preview.lines[0].issue
    with pytest.raises(ValueError, match="incidencias"):
        service.save(preview, date.today())
    with Session(catalog) as session:
        assert not session.exec(select(Pedido)).all()
        assert not session.exec(select(PedidoItem)).all()


@pytest.mark.parametrize("text", ["", TEXT.replace("60,00 UNI", "59,00 UNI"), TEXT.replace("500G", "SIN PESO"), TEXT.replace("00005778", "INVALIDO"), TEXT.replace("UNI", "KG")])
def test_parser_rejects_incomplete_or_inconsistent_input(text):
    with pytest.raises(ValueError):
        CadelsaOrderImportService.parse_text(text)


def test_wrong_client_and_changed_catalog_are_rejected(catalog, pdf):
    service = CadelsaOrderImportService()
    with pytest.raises(ValueError, match="cliente directo"):
        service.preview(pdf, "igsa")
    preview = service.preview(pdf, "cad")
    with Session(catalog) as session:
        product = session.exec(select(IngredienteIreks).where(IngredienteIreks.articulo_id == "505")).one()
        product.articulo_envase_peso_total = 20
        session.add(product)
        session.commit()
    with pytest.raises(ValueError, match="incidencias"):
        service.save(preview, date.today())


def test_albaran_replaces_internal_number_and_duplicate_protection_remains(catalog, pdf):
    service = CadelsaOrderImportService()
    preview = service.preview(pdf, "cad")
    order_id = service.save(preview, date(2026, 9, 7))
    result = order_document_import_service.OrderDocumentImportService().import_albaran(
        order_id,
        {"albaran_numero": "AL-1", "albaran_fecha": "2026-09-25"},
        [{"articulo_codigo": "I505", "albaran_numero": "AL-1", "albaran_fecha": "2026-09-25", "pedido_numero": "12345", "articulo_cantidad": 60}],
    )
    assert result.imported == 1
    with Session(catalog) as session:
        assert session.get(Pedido, order_id).pedido_numero == "12345"
        assert all(i.pedido_numero == "12345" for i in session.exec(select(PedidoItem)).all())
    with pytest.raises(ValueError, match="ya se ha importado"):
        service.preview(pdf, "cad")


def test_failed_item_write_rolls_back_header_and_all_lines(catalog, pdf):
    service = CadelsaOrderImportService()
    preview = service.preview(pdf, "cad")

    def fail_second_line(mapper, connection, target):
        if target.articulo_id == "5778":
            raise RuntimeError("simulated write failure")

    event.listen(PedidoItem, "before_insert", fail_second_line)
    try:
        with pytest.raises(RuntimeError, match="simulated"):
            service.save(preview, date.today())
    finally:
        event.remove(PedidoItem, "before_insert", fail_second_line)
    with Session(catalog) as session:
        assert session.exec(select(Pedido)).all() == []
        assert session.exec(select(PedidoItem)).all() == []
