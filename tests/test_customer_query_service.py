from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import Cliente, Isla, VentaClientesRaw
from app.services.customer_query_service import CustomerQueryService
from app.services.customer_report_schema import CUSTOMER_REPORT_RESPONSE_FORMAT
from app.services.customer_report_service import CustomerReportIntentService
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService


def _sales_engine(tmp_path):
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'customer-queries.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(db_engine)
    return db_engine


def _add_sale(session: Session, raw_id: str, cliente_id: str, year: int, kg: float) -> None:
    session.add(
        VentaClientesRaw(
            raw_id=raw_id,
            lote_id="batch",
            cliente_id=cliente_id,
            anio=year,
            kg=kg,
        )
    )


def test_annual_customer_ranking_uses_kg_and_orders_largest_drops(tmp_path) -> None:
    db_engine = _sales_engine(tmp_path)
    with Session(db_engine) as session:
        session.add_all(
            [
                Cliente(cliente_id="c1", cliente_codigo=1, cliente_nombre_comercial="Cliente Uno"),
                Cliente(cliente_id="c2", cliente_codigo=2, cliente_nombre_comercial="Cliente Dos"),
                Cliente(cliente_id="c3", cliente_codigo=3, cliente_nombre_comercial="Cliente Tres"),
            ]
        )
        _add_sale(session, "r1", "c1", 2025, 100.0)
        _add_sale(session, "r2", "c1", 2026, 40.0)
        _add_sale(session, "r3", "c2", 2025, 50.0)
        _add_sale(session, "r4", "c2", 2026, 25.0)
        _add_sale(session, "r5", "c3", 2025, 10.0)
        _add_sale(session, "r6", "c3", 2026, 50.0)
        session.commit()

    rows = SalesAnnualComparisonService(db_engine=db_engine).listar_ranking_anual_clientes(
        2026, limit=2, direction="asc"
    )

    assert [row.cliente_id for row in rows] == ["c1", "c2"]
    assert rows[0].kg_prev == pytest.approx(100.0)
    assert rows[0].kg_curr == pytest.approx(40.0)
    assert rows[0].delta_kg == pytest.approx(-60.0)


def test_customer_query_interprets_current_year_and_kg_as_primary_metric() -> None:
    service = CustomerQueryService()

    intent = service.interpret(
        "Dame un listado de los cinco clientes con mayores bajadas en las compras en el año actual"
    )

    assert intent.query_type == "sales_drop_ranking"
    assert intent.year == date.today().year
    assert intent.limit == 5
    assert intent.direction == "asc"
    assert intent.metric == "kg"


def test_local_customer_parser_recognizes_activity_and_island() -> None:
    result = CustomerReportIntentService(api_key="").parse("Dame las panaderías de Lanzarote")

    filters = {(item.field, item.op, str(item.value).lower()) for item in result.intent.filters}
    assert ("actividad", "contiene", "panaderia") in filters
    assert ("isla", "contiene", "lanzarote") in filters


def test_sales_customer_list_query_uses_year_type_and_kg() -> None:
    service = CustomerQueryService()
    intent = service.interpret(
        'dame el listado de las ventas del 2025 de los clientes indirectos, '
        'solo los campos isla, cod. nombre, kg, ordenada por islas, y kg de menor a mayor'
    )

    assert intent.query_type == 'sales_customer_list'
    assert intent.year == 2025
    assert intent.customer_type == 'indirecto'
    assert intent.metric == 'kg'
    assert intent.direction == 'asc'


def test_sales_customer_list_returns_codes_as_text_and_orders_by_island_and_kg(tmp_path) -> None:
    db_engine = _sales_engine(tmp_path)
    with Session(db_engine) as session:
        session.add_all([
            Isla(isla_id='fue', provincia_id='p1', isla_nombre='Fuerteventura', isla_codigo='FUE'),
            Isla(isla_id='tfe', provincia_id='p1', isla_nombre='Tenerife', isla_codigo='TFE'),
            Cliente(cliente_id='c1', cliente_codigo=35, cliente_nombre_comercial='Pan Hierro', cliente_tipo='indirecto', cliente_direccion_isla_id='fue'),
            Cliente(cliente_id='c2', cliente_codigo=36, cliente_nombre_comercial='Bar Café', cliente_tipo='indirecto', cliente_direccion_isla_id='fue'),
            Cliente(cliente_id='c3', cliente_codigo=50, cliente_nombre_comercial='Pan Teide', cliente_tipo='indirecto', cliente_direccion_isla_id='tfe'),
            Cliente(cliente_id='c4', cliente_codigo=60, cliente_nombre_comercial='Directo', cliente_tipo='directo', cliente_direccion_isla_id='fue'),
        ])
        _add_sale(session, 's1', 'c1', 2025, 10.0)
        _add_sale(session, 's2', 'c2', 2025, 5.0)
        _add_sale(session, 's3', 'c3', 2025, 2.0)
        _add_sale(session, 's4', 'c4', 2025, 1.0)
        session.commit()

    service = CustomerQueryService(
        sales_service=SalesAnnualComparisonService(db_engine=db_engine)
    )
    result = service.run(
        'ventas del 2025 de clientes indirectos, isla, cod, nombre y kg, '
        'ordenadas por isla y kg de menor a mayor'
    )

    assert result.headers == ['Isla', 'Cod.', 'Nombre comercial', 'Kg']
    assert [row[1] for row in result.rows] == ['36', '35', '50']
    assert [row[3] for row in result.rows] == [5.0, 10.0, 2.0]
    assert all(isinstance(row[1], str) for row in result.rows)


def test_customer_report_ai_format_is_strict_and_allowlisted() -> None:
    assert CUSTOMER_REPORT_RESPONSE_FORMAT["type"] == "json_schema"
    assert CUSTOMER_REPORT_RESPONSE_FORMAT["strict"] is True
    schema = CUSTOMER_REPORT_RESPONSE_FORMAT["schema"]
    assert schema["additionalProperties"] is False
    assert "actividad" in schema["properties"]["columns"]["items"]["enum"]
