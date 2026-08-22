from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

import app.services.sales_annual_comparison_service as sales_annual_service_module
from app.models import (
    Cliente,
    Fabricante,
    Familia,
    IngredienteIreks,
    ReferenciaDistribuidor,
    Subfamilia,
    VentaClientesRaw,
    VentaMensualRaw,
)
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


def test_listar_ventas_mensuales_ireks_returns_12_month_series(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        _cliente_id, _fabricante_id, _familia_id, _subfamilia_id = _seed_products(session)
        session.add(
            VentaMensualRaw(
                raw_id="raw-5",
                lote_id="lote-5",
                fuente="ireks",
                cliente_id="cli-1",
                periodo="2026-01",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=10.0,
                venta_kilos_sc=2.0,
                venta_euros=0.0,
            )
        )
        session.add(
            VentaMensualRaw(
                raw_id="raw-6",
                lote_id="lote-6",
                fuente="ireks",
                cliente_id="cli-1",
                periodo="2026-01",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=3.5,
                venta_kilos_sc=0.5,
                venta_euros=0.0,
            )
        )
        session.add(
            VentaMensualRaw(
                raw_id="raw-7",
                lote_id="lote-7",
                fuente="ireks",
                cliente_id="cli-1",
                periodo="2026-02",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=8.0,
                venta_kilos_sc=0.0,
                venta_euros=0.0,
            )
        )
        session.commit()

    service = SalesAnnualComparisonService()
    series = service.listar_ventas_mensuales_ireks(2026, "art-1", "cli-1")

    assert len(series) == 12
    assert [point.month for point in series] == list(range(1, 13))
    assert series[0].kilos == pytest.approx(16.0)
    assert series[1].kilos == pytest.approx(8.0)
    assert all(point.kilos == pytest.approx(0.0) for point in series[2:])


def test_listar_ventas_mensuales_ireks_comparativa_returns_prev_and_curr_years(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        _cliente_id, _fabricante_id, _familia_id, _subfamilia_id = _seed_products(session)
        session.add(
            VentaMensualRaw(
                raw_id="raw-8",
                lote_id="lote-8",
                fuente="ireks",
                cliente_id="cli-1",
                periodo="2025-03",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=5.0,
                venta_kilos_sc=1.0,
                venta_euros=0.0,
            )
        )
        session.add(
            VentaMensualRaw(
                raw_id="raw-9",
                lote_id="lote-9",
                fuente="ireks",
                cliente_id="cli-1",
                periodo="2026-03",
                articulo_codigo_origen="D123",
                articulo_id="art-1",
                articulo_descripcion_origen="Producto IREKS",
                venta_kilos=7.0,
                venta_kilos_sc=2.0,
                venta_euros=0.0,
            )
        )
        session.commit()

    service = SalesAnnualComparisonService()
    series = service.listar_ventas_mensuales_ireks_comparativa(2026, "art-1", "cli-1")

    assert len(series) == 12
    assert series[2].kilos_prev == pytest.approx(6.0)
    assert series[2].kilos_curr == pytest.approx(9.0)
    assert all(point.kilos_prev == pytest.approx(0.0) for idx, point in enumerate(series) if idx != 2)
    assert all(point.kilos_curr == pytest.approx(0.0) for idx, point in enumerate(series) if idx != 2)


def test_listar_clientes_consumidores_producto_aggregates_clients(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        cliente_id, _fabricante_id, _familia_id, _subfamilia_id = _seed_products(session)
        session.add(
            Cliente(
                cliente_id="cli-2",
                cliente_codigo=2,
                cliente_nombre_comercial="Cliente Dos",
                cliente_tipo="distribuidor",
            )
        )
        session.add(
            ReferenciaDistribuidor(
                articulo_id="art-1",
                distribuidor_id="dist-1",
                articulo_referencia_distribuidor="DX-001",
                articulo_descripcion_distribuidor="Producto IREKS",
            )
        )
        session.add(
            VentaClientesRaw(
                raw_id="raw-10",
                lote_id="lote-10",
                cliente_id=cliente_id,
                anio=2025,
                articulo_codigo_origen="DX-001",
                articulo_id="",
                articulo_descripcion_origen="Producto IREKS",
                envase=1.0,
                unidades=2.0,
                kg=4.0,
                precio_kg=2.5,
                euros=10.0,
            )
        )
        session.add(
            VentaClientesRaw(
                raw_id="raw-11",
                lote_id="lote-11",
                cliente_id=cliente_id,
                anio=2026,
                articulo_codigo_origen="DX-001",
                articulo_id="",
                articulo_descripcion_origen="Producto IREKS",
                envase=1.0,
                unidades=4.0,
                kg=10.0,
                precio_kg=3.0,
                euros=30.0,
            )
        )
        session.add(
            VentaClientesRaw(
                raw_id="raw-12",
                lote_id="lote-12",
                cliente_id=cliente_id,
                anio=2026,
                articulo_codigo_origen="DX-001",
                articulo_id="",
                articulo_descripcion_origen="Producto IREKS",
                envase=1.0,
                unidades=1.0,
                kg=2.5,
                precio_kg=4.8,
                euros=12.0,
            )
        )
        session.add(
            VentaClientesRaw(
                raw_id="raw-13",
                lote_id="lote-13",
                cliente_id="cli-2",
                anio=2025,
                articulo_codigo_origen="DX-001",
                articulo_id="",
                articulo_descripcion_origen="Producto IREKS",
                envase=1.0,
                unidades=1.0,
                kg=1.0,
                precio_kg=3.0,
                euros=3.0,
            )
        )
        session.add(
            VentaClientesRaw(
                raw_id="raw-14",
                lote_id="lote-14",
                cliente_id="cli-2",
                anio=2026,
                articulo_codigo_origen="DX-001",
                articulo_id="",
                articulo_descripcion_origen="Producto IREKS",
                envase=1.0,
                unidades=2.0,
                kg=5.0,
                precio_kg=3.36,
                euros=16.8,
            )
        )
        session.commit()

    service = SalesAnnualComparisonService()
    rows = service.listar_clientes_consumidores_producto(2026, "art-1", "DX-001")
    all_year_rows = service.listar_clientes_consumidores_producto(0, "art-1", "DX-001")
    rows_by_code_only = service.listar_clientes_consumidores_producto(2026, "wrong-id", "DX-001")
    rows_by_name_only = service.listar_clientes_consumidores_producto(2026, "wrong-id", "wrong-code", "Producto IREKS")

    assert len(rows) == 2
    assert rows[0].cliente_codigo == "1"
    assert rows[0].cliente_nombre == "Cliente"
    assert rows[0].kg_prev == pytest.approx(4.0)
    assert rows[0].euros_prev == pytest.approx(10.0)
    assert rows[0].kg_curr == pytest.approx(12.5)
    assert rows[0].euros_curr == pytest.approx(42.0)
    assert rows[0].delta_kg == pytest.approx(8.5)
    assert rows[0].delta_euros == pytest.approx(32.0)
    assert rows[0].unidades_curr == pytest.approx(5.0)
    assert rows[0].ultimo_periodo == "2026-12"
    assert rows[1].cliente_codigo == "2"
    assert rows[1].cliente_nombre == "Cliente Dos"
    assert rows[1].kg_prev == pytest.approx(1.0)
    assert rows[1].euros_prev == pytest.approx(3.0)
    assert rows[1].kg_curr == pytest.approx(5.0)
    assert rows[1].euros_curr == pytest.approx(16.8)
    assert rows[1].delta_kg == pytest.approx(4.0)
    assert rows[1].delta_euros == pytest.approx(13.8)
    assert all_year_rows[0].kg_curr == pytest.approx(16.5)
    assert all_year_rows[0].unidades_curr == pytest.approx(7.0)
    assert all_year_rows[0].ultimo_periodo == "2026-12"
    assert len(rows_by_code_only) == 2
    assert len(rows_by_name_only) == 2


def test_listar_ventas_mensuales_cliente_producto_groups_selected_year_by_month(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        cliente_id, _fabricante_id, _familia_id, _subfamilia_id = _seed_products(session)
        session.add_all(
            [
                VentaClientesRaw(
                    raw_id="monthly-1", lote_id="monthly-lote", cliente_id=cliente_id, anio=2026, mes=1,
                    articulo_codigo_origen="D123", articulo_id="art-1", unidades=2, kg=5, euros=15,
                ),
                VentaClientesRaw(
                    raw_id="monthly-2", lote_id="monthly-lote", cliente_id=cliente_id, anio=2026, mes=1,
                    articulo_codigo_origen="D123", articulo_id="art-1", unidades=1, kg=2.5, euros=8,
                ),
                VentaClientesRaw(
                    raw_id="monthly-3", lote_id="monthly-lote", cliente_id=cliente_id, anio=2026, mes=3,
                    articulo_codigo_origen="D123", articulo_id="art-1", unidades=4, kg=10, euros=30,
                ),
                VentaClientesRaw(
                    raw_id="monthly-4", lote_id="monthly-lote", cliente_id=cliente_id, anio=2026, mes=3,
                    articulo_codigo_origen="OTHER", articulo_id="other-art", unidades=9, kg=99, euros=99,
                ),
            ]
        )
        session.commit()

    rows = SalesAnnualComparisonService().listar_ventas_mensuales_cliente_producto(
        year=2026,
        cliente_id=cliente_id,
        articulo_id="art-1",
        articulo_codigo="D123",
    )

    assert len(rows) == 12
    assert rows[0].unidades == pytest.approx(3.0)
    assert rows[0].kg == pytest.approx(7.5)
    assert rows[0].euros == pytest.approx(23.0)
    assert rows[2].unidades == pytest.approx(4.0)
    assert rows[2].kg == pytest.approx(10.0)
    assert rows[2].euros == pytest.approx(30.0)
    assert rows[1].kg == pytest.approx(0.0)


def test_latest_sales_month_clientes_uses_global_imported_period(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        session.add_all(
            [
                VentaClientesRaw(raw_id="latest-1", lote_id="latest", anio=2026, mes=2, kg=1),
                VentaClientesRaw(raw_id="latest-2", lote_id="latest", anio=2026, mes=7, kg=1),
                VentaClientesRaw(raw_id="latest-3", lote_id="latest", anio=2025, mes=12, kg=1),
            ]
        )
        session.commit()

    service = SalesAnnualComparisonService(db_engine=isolated_engine)

    assert service.latest_sales_month_clientes(2026) == 7
    assert service.latest_sales_month_clientes(2024) == 0
    assert service.sales_months_clientes(2026) == (2, 7)
    assert service.sales_months_clientes(2025) == (12,)
