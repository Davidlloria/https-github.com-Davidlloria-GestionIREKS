from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine
from app.models import IngredienteIreks, Pedido, PedidoItem
from app.services.order_document_import_service import OrderDocumentImportService


def test_duplicate_code_prefers_order_then_active_and_rejects_ambiguity():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    service = OrderDocumentImportService()
    with Session(engine) as session:
        old = IngredienteIreks(articulo_id="old", articulo_referencia="D1265049",
                              articulo_descripcion="IRISH CREAM", articulo_status_activo=False)
        current = IngredienteIreks(articulo_id="current", articulo_referencia="D1265049",
                                  articulo_descripcion="CREAM LIQUER", articulo_status_activo=True)
        session.add_all([old, current, Pedido(pedido_id="order", pedido_fecha=date.today())])
        session.flush()
        assert service.find_article_by_code(session, "D1265049").articulo_id == "current"
        session.add(PedidoItem(pedido_id="order", articulo_id="old", articulo_cantidad=6))
        session.flush()
        assert service.find_article_by_code(session, "D1265049", pedido_id="order").articulo_id == "old"
        old.articulo_status_activo = True
        session.add(old)
        session.flush()
        with pytest.raises(ValueError, match="varios productos"):
            service.find_article_by_code(session, "D1265049")
        session.add(PedidoItem(pedido_id="order", articulo_id="current", articulo_cantidad=6))
        session.flush()
        with pytest.raises(ValueError, match="varios productos del pedido"):
            service.find_article_by_code(session, "D1265049", pedido_id="order")
        assert service.find_article_by_code(session, "UNKNOWN") is None
