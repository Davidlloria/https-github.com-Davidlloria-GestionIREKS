from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

import app.services.sales_annual_comparison_service as sales_annual_service_module
from app.models import Cliente, Fabricante, Familia, IngredienteIreks, Subfamilia, VentaMensualRaw
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService


@pytest.fixture()
def isolated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sales-annual.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(sales_annual_service_module, "engine", engine)
    return engine


def _seed_products(session: Session) -> tuple[str, str, str, str]:
    cliente_id = "cli-1"
    fabricante_id = "fab-1"
    familia_id = "fam-1"
    subfamilia_id = "sub-1"
    articulo_id = "art-1"
    session.add(Cliente(cliente_id=cliente_id, cliente_codigo=1, cliente_nombre_comercial="Cliente", cliente_tipo="distribuidor"))
    session.add(Fabricante(fabricante_id=fabricante_id, fabricante_codigo=1, fabricante_nombre="Fabricante"))
    session.add(
        Familia(
            articulo_familia_id=familia_id,
            fabricante_id=fabricante_id,
            articulo_familia_nombre="Familia",
            articulo_familia_codigo="F1",
        )
    )
    session.add(
        Subfamilia(
            articulo_familia_id=familia_id,
            articulo_subfamilia_id=subfamilia_id,
            articulo_subfamilia_nombre="Subfamilia",
            articulo_subfamilia_codigo="S1",
        )
    )
    session.add(
        IngredienteIreks(
            articulo_id=articulo_id,
            almacen_id="alm-1",
            fabricante_id=fabricante_id,
            articulo_referencia="D123",
            articulo_referencia_corta="D123",
            articulo_descripcion="Producto IREKS",
            articulo_envase_peso=2.5,
            articulo_envase_peso_total=2.5,
            articulo_familia_id=familia_id,
            articulo_subfamilia_id=subfamilia_id,
        )
    )
    session.commit()
    return cliente_id, fabricante_id, familia_id, subfamilia_id


def test_ireks_summary_uses_previous_and_current_years(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        cliente_id, fabricante_id, familia_id, subfamilia_id = _seed_products(session)
        session.add(
            VentaMensualRaw(
                raw_id="raw-1",
                lote_id="lote-1",
                fuente="ireks",
                cliente_id=cliente_id,
                periodo="2025-01",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=10.0,
                venta_kilos_sc=2.0,
                venta_euros=12.0,
            )
        )
        session.add(
            VentaMensualRaw(
                raw_id="raw-2",
                lote_id="lote-2",
                fuente="ireks",
                cliente_id=cliente_id,
                periodo="2026-01",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=15.0,
                venta_kilos_sc=1.0,
                venta_euros=20.0,
            )
        )
        session.commit()

    service = SalesAnnualComparisonService()
    years = service.list_years()
    rows = service.listar_resumen_anual(
        year=2026,
        month=1,
        acumulado=False,
        cliente_id=cliente_id,
        producto_texto="producto",
        fabricante_id=fabricante_id,
        familia_id=familia_id,
        subfamilia_id=subfamilia_id,
    )

    assert years == [2026, 2025]
    assert len(rows) == 1
    row = rows[0]
    assert row.codigo == "D123"
    assert row.articulo_id == "art-1"
    assert row.kilos_prev == pytest.approx(10.0)
    assert row.kilos_curr == pytest.approx(15.0)
    assert row.delta_kg == pytest.approx(4.0)
    assert row.ventas_prev == pytest.approx(12.0)
    assert row.ventas_curr == pytest.approx(20.0)
    assert row.delta_ventas == pytest.approx(8.0)


def test_igsa_filters_and_summary_use_related_family_tree(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        _cliente_id, fabricante_id, familia_id, subfamilia_id = _seed_products(session)
        session.add(
            VentaMensualRaw(
                raw_id="raw-3",
                lote_id="lote-3",
                fuente="igsa_pdf",
                cliente_id="cli-1",
                periodo="2025-02",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=4.0,
                venta_kilos_sc=1.0,
                venta_euros=6.0,
            )
        )
        session.add(
            VentaMensualRaw(
                raw_id="raw-4",
                lote_id="lote-4",
                fuente="igsa",
                cliente_id="cli-1",
                periodo="2026-02",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=7.0,
                venta_kilos_sc=2.0,
                venta_euros=11.0,
            )
        )
        session.commit()

    service = SalesAnnualComparisonService()
    assert service.list_years_igsa() == [2026, 2025]
    assert [row.fabricante_id for row in service.list_filter_manufacturers_igsa()] == [fabricante_id]
    assert [row.articulo_familia_id for row in service.list_filter_families_igsa(fabricante_id)] == [familia_id]
    assert [row.articulo_subfamilia_id for row in service.list_filter_subfamilies_igsa(familia_id)] == [subfamilia_id]

    rows = service.listar_resumen_anual_igsa(
        year=2026,
        month=2,
        acumulado=True,
        producto_texto="ireks",
        fabricante_id=fabricante_id,
        familia_id=familia_id,
        subfamilia_id=subfamilia_id,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.kilos_prev == pytest.approx(4.0)
    assert row.kilos_curr == pytest.approx(7.0)
    assert row.sc_prev == pytest.approx(1.0)
    assert row.sc_curr == pytest.approx(2.0)
    assert row.ventas_prev == pytest.approx(0.0)
    assert row.ventas_curr == pytest.approx(0.0)
