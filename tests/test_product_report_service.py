from __future__ import annotations

from sqlmodel import SQLModel, Session, create_engine

from app.models import IngredienteIreks, ReferenciaDistribuidor, TarifaPrecioIreks
from app.services import product_report_service as product_reports
from app.services.product_report_service import (
    ProductReportIntent,
    ProductReportIntentService,
    ProductReportService,
)


def _isolated_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'product-report.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_product_report_includes_distributor_references_and_latest_tariff(tmp_path, monkeypatch) -> None:
    engine = _isolated_engine(tmp_path)
    monkeypatch.setattr(product_reports, "engine", engine)
    with Session(engine) as session:
        session.add(
            IngredienteIreks(
                articulo_id="art-1",
                articulo_referencia="D123456",
                articulo_referencia_corta="D123",
                articulo_descripcion="Producto IREKS",
                articulo_envase_peso_total=12.5,
                articulo_status_activo=True,
            )
        )
        session.add(
            ReferenciaDistribuidor(
                articulo_id="art-1",
                distribuidor_id="dist-1",
                articulo_referencia_distribuidor="IGSA-001",
                articulo_descripcion_distribuidor="Producto IGSA",
            )
        )
        session.add(
            ReferenciaDistribuidor(
                articulo_id="art-1",
                distribuidor_id="dist-2",
                articulo_referencia_distribuidor="CAD-002",
                articulo_descripcion_distribuidor="Producto Cadesa",
            )
        )
        session.add(
            TarifaPrecioIreks(
                articulo_id="art-1",
                tarifa_ano=2025,
                precio_fabricante=10.0,
                precio_distribuidor=11.0,
                descuento_pct=1.0,
            )
        )
        session.add(
            TarifaPrecioIreks(
                articulo_id="art-1",
                tarifa_ano=2026,
                precio_fabricante=12.5,
                precio_distribuidor=13.75,
                descuento_pct=2.5,
            )
        )
        session.commit()

    report = ProductReportService().run(
        ProductReportIntent(
            columns=[
                "referencia_corta",
                "descripcion",
                "referencia_distribuidor",
                "descripcion_distribuidor",
                "tarifa_ano",
                "precio_fabricante",
                "precio_distribuidor",
                "descuento",
            ],
            order_by=["referencia_corta"],
            limit=20,
        )
    )

    assert report.headers == [
        "Ref. corta",
        "Descripcion",
        "Ref. distribuidor",
        "Desc. distribuidor",
        "Ano tarifa",
        "Precio fabricante",
        "Precio distribuidor",
        "Descuento %",
    ]
    assert report.rows == [
        [
            "D123",
            "Producto IREKS",
            "IGSA-001 | CAD-002",
            "Producto IGSA | Producto Cadesa",
            "2026",
            "12.5",
            "13.75",
            "2.5",
        ]
    ]


def test_product_report_local_parser_adds_distributor_reference_columns() -> None:
    intent = ProductReportIntentService(api_key="")._fallback_parse(
        "Listado de productos con referencias de distribuidor y tarifa"
    )

    assert "referencia_distribuidor" in intent.columns
    assert "descripcion_distribuidor" in intent.columns
    assert "tarifa_ano" in intent.columns
    assert "precio_fabricante" in intent.columns
    assert "precio_distribuidor" in intent.columns
    assert "descuento" in intent.columns


def test_product_report_includes_article_uuid_when_requested(tmp_path, monkeypatch) -> None:
    engine = _isolated_engine(tmp_path)
    monkeypatch.setattr(product_reports, "engine", engine)
    with Session(engine) as session:
        session.add(
            IngredienteIreks(
                articulo_id="uuid-art-1",
                articulo_referencia_corta="D999",
                articulo_descripcion="Producto con UUID",
            )
        )
        session.commit()

    report = ProductReportService().run(
        ProductReportIntent(
            columns=["articulo_id", "referencia_corta", "descripcion"],
            order_by=["referencia_corta"],
        )
    )

    assert report.headers == ["UUID articulo", "Ref. corta", "Descripcion"]
    assert report.rows == [["uuid-art-1", "D999", "Producto con UUID"]]


def test_product_report_local_parser_adds_article_uuid_column() -> None:
    intent = ProductReportIntentService(api_key="")._fallback_parse(
        "Listado de productos con UUID, referencia corta y descripcion"
    )

    assert "articulo_id" in intent.columns
