from __future__ import annotations

from datetime import date
import json

import pytest
from sqlmodel import SQLModel, Session, create_engine

import app.services.customer_query_service as customer_query_service_module
from app.models import Cliente, Isla, VentaClientesRaw
from app.services.customer_query_service import CUSTOMER_QUERY_INTENT_SCHEMA, CustomerQueryService
from app.services.customer_report_schema import CUSTOMER_REPORT_RESPONSE_FORMAT
from app.services.customer_report_service import CustomerReportIntentService
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService


class _DisabledLocalAI:
    enabled = False


class _DisabledOpenAI:
    def generate_process(self, prompt: str):
        return type("Result", (), {"ok": False, "text": ""})()


class _FakeLocalAI:
    enabled = True

    def __init__(self, response: dict) -> None:
        self.response = response
        self.prompts: list[str] = []
        self.schemas: list[dict | None] = []

    def generate_json(self, prompt: str, *, schema: dict | None = None):
        self.prompts.append(prompt)
        self.schemas.append(schema)
        return type("Result", (), {"ok": True, "text": json.dumps(self.response)})()


@pytest.fixture(autouse=True)
def _disable_default_local_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customer_query_service_module, "LocalAIService", lambda **_kwargs: _DisabledLocalAI())


def _sales_engine(tmp_path):
    db_engine = create_engine(
        f"sqlite:///{tmp_path / 'customer-queries.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(db_engine)
    return db_engine


def _add_sale(session: Session, raw_id: str, cliente_id: str, year: int, kg: float, euros: float = 0.0) -> None:
    session.add(
        VentaClientesRaw(
            raw_id=raw_id,
            lote_id="batch",
            cliente_id=cliente_id,
            anio=year,
            kg=kg,
            euros=euros,
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
    result = CustomerReportIntentService(
        local_ai_service=_DisabledLocalAI(),
        openai_service=_DisabledOpenAI(),
    ).parse("Dame las panaderías de Lanzarote")

    filters = {(item.field, item.op, str(item.value).lower()) for item in result.intent.filters}
    assert ("actividad", "contiene", "panaderia") in filters
    assert ("isla", "contiene", "lanzarote") in filters


def test_customer_query_returns_only_repeated_commercial_names(tmp_path, monkeypatch) -> None:
    db_engine = _sales_engine(tmp_path)
    with Session(db_engine) as session:
        session.add_all(
            [
                Cliente(cliente_id="c1", cliente_codigo=11, cliente_nombre_comercial="Pan Ávila"),
                Cliente(cliente_id="c2", cliente_codigo=12, cliente_nombre_comercial="  pan avila  "),
                Cliente(cliente_id="c3", cliente_codigo=13, cliente_nombre_comercial="Nombre único"),
                Cliente(cliente_id="c4", cliente_codigo=14, cliente_nombre_comercial=""),
            ]
        )
        session.commit()
    monkeypatch.setattr(customer_query_service_module, "engine", db_engine)

    result = CustomerQueryService().run("lista de clientes con nombres repetidos")

    assert result.status == "ready"
    assert result.intent.query_type == "duplicate_customer_names"
    assert result.headers == ["Nombre comercial", "Cod.", "Coincidencias"]
    assert result.rows == [["Pan Ávila", "11", 2], ["pan avila", "12", 2]]


def test_local_customer_parser_does_not_filter_type_when_requesting_distributor_code() -> None:
    result = CustomerReportIntentService(
        local_ai_service=_DisabledLocalAI(),
        openai_service=_DisabledOpenAI(),
    ).parse(
        "listado de todos los clientes, campos uuid, cod, codigo cliente distribuidor, nombre"
    )

    assert result.intent.filters == []
    assert result.intent.columns == ["cliente_id", "codigo", "codigo_distribuidor", "nombre_comercial"]
    assert result.intent.limit == 5000


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


def test_sales_customer_list_query_filters_gran_canaria_and_orders_descending() -> None:
    intent = CustomerQueryService().interpret(
        'dame el listado de las ventas del 2025 de los clientes indirectos de gran canaria, '
        'solo los campos isla, cod. nombre, kg, y ordenar por kg de mayor a menor'
    )

    assert intent.query_type == 'sales_customer_list'
    assert intent.island == 'Gran Canaria'
    assert intent.direction == 'desc'


def test_sales_customer_top_query_orders_descending_and_respects_fields() -> None:
    intent = CustomerQueryService().interpret(
        'listado 5 clientes top ventas en 2025, campos: nombre, kg'
    )

    assert intent.query_type == 'sales_customer_list'
    assert intent.year == 2025
    assert intent.limit == 5
    assert intent.direction == 'desc'
    assert intent.columns == ['nombre', 'kg']
    assert intent.sort_by_island is False


def test_sales_customer_comparison_query_uses_two_years_and_requested_fields() -> None:
    intent = CustomerQueryService().interpret(
        'listado 5 clientes top ventas en 2025 versus 2024, '
        'campos: nombre, kg 2025, kg 2024, diferencia kg'
    )

    assert intent.query_type == 'sales_customer_year_comparison'
    assert intent.year == 2025
    assert intent.compare_year == 2024
    assert intent.limit == 5
    assert intent.direction == 'desc'
    assert intent.sort_metric == 'kg_curr'
    assert intent.columns == ['nombre', 'kg_curr', 'kg_prev', 'delta_kg']


def test_zero_consumption_is_not_interpreted_as_a_one_row_limit() -> None:
    intent = CustomerQueryService().interpret(
        'dame el listado de los clientes de gran canaria con consumo 0 en el 2025, '
        'campos, isla, cod, nombre, kg'
    )

    assert intent.query_type == 'sales_customer_list'
    assert intent.year == 2025
    assert intent.island == 'Gran Canaria'
    assert intent.limit == 500
    assert intent.zero_consumption is True


def test_local_ai_translates_natural_sales_query_to_a_valid_deterministic_intent() -> None:
    local_ai = _FakeLocalAI(
        {
            "query_type": "sales_customer_list",
            "year": 2026,
            "limit": 500,
            "direction": "asc",
            "metric": "kg",
            "zero_consumption": True,
            "columns": ["codigo", "nombre", "kg", "€"],
            "sort_by_island": False,
        }
    )
    service = CustomerQueryService(local_ai_service=local_ai)

    intent = service.interpret("lista de clientes con ventas = 0 en 2026, campos cod y nombre comercial")

    assert intent.query_type == "sales_customer_list"
    assert intent.year == 2026
    assert intent.zero_consumption is True
    assert intent.columns == ["codigo", "nombre", "kg", "euros"]
    assert intent.ai_interpreted is True
    assert "No generes SQL" in local_ai.prompts[0]
    assert local_ai.schemas == [CUSTOMER_QUERY_INTENT_SCHEMA]


def test_invalid_local_ai_intent_falls_back_to_the_deterministic_interpreter() -> None:
    local_ai = _FakeLocalAI({"query_type": "drop_all_tables", "year": 2026})
    service = CustomerQueryService(local_ai_service=local_ai)

    intent = service.interpret("lista de clientes con ventas = 0 en 2026")

    assert intent.query_type == "sales_customer_list"
    assert intent.zero_consumption is True
    assert intent.ai_interpreted is False


def test_local_ai_cannot_reroute_the_sales_zero_query_from_the_screenshot() -> None:
    local_ai = _FakeLocalAI(
        {
            "query_type": "customer_filter",
            "year": 2026,
            "columns": ["codigo", "nombre"],
        }
    )
    service = CustomerQueryService(local_ai_service=local_ai)

    intent = service.interpret("lista de clientes con ventas = 0 en 2026, campos cod y nombre comercial")

    assert intent.query_type == "sales_customer_list"
    assert intent.year == 2026
    assert intent.zero_consumption is True
    assert intent.columns == ["codigo", "nombre"]
    assert intent.ai_interpreted is True


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
        _add_sale(session, 's1', 'c1', 2025, 10.0, 25.0)
        _add_sale(session, 's2', 'c2', 2025, 5.0, 10.0)
        _add_sale(session, 's3', 'c3', 2025, 2.0, 4.0)
        _add_sale(session, 's4', 'c4', 2025, 1.0, 2.0)
        session.commit()

    service = CustomerQueryService(
        sales_service=SalesAnnualComparisonService(db_engine=db_engine)
    )
    result = service.run(
        'ventas del 2025 de clientes indirectos, campos: isla, cod, nombre, kg y €, '
        'ordenadas por isla y kg de menor a mayor'
    )

    assert result.headers == ['Isla', 'Cod.', 'Nombre comercial', 'Kg', '€']
    assert [row[1] for row in result.rows] == ['36', '35', '50']
    assert [row[3] for row in result.rows] == [5.0, 10.0, 2.0]
    assert [row[4] for row in result.rows] == [10.0, 25.0, 4.0]
    assert all(isinstance(row[1], str) for row in result.rows)


def test_sales_customer_list_applies_island_filter_and_descending_kg(tmp_path) -> None:
    db_engine = _sales_engine(tmp_path)
    with Session(db_engine) as session:
        session.add_all([
            Isla(isla_id='gc', provincia_id='p1', isla_nombre='Gran Canaria', isla_codigo='GC'),
            Isla(isla_id='fue', provincia_id='p1', isla_nombre='Fuerteventura', isla_codigo='FUE2'),
            Cliente(cliente_id='gc1', cliente_codigo=101, cliente_nombre_comercial='GC Menor', cliente_tipo='indirecto', cliente_direccion_isla_id='gc'),
            Cliente(cliente_id='gc2', cliente_codigo=102, cliente_nombre_comercial='GC Mayor', cliente_tipo='indirecto', cliente_direccion_isla_id='gc'),
            Cliente(cliente_id='f1', cliente_codigo=103, cliente_nombre_comercial='Fuera', cliente_tipo='indirecto', cliente_direccion_isla_id='fue'),
        ])
        _add_sale(session, 'g1', 'gc1', 2025, 5.0)
        _add_sale(session, 'g2', 'gc2', 2025, 20.0)
        _add_sale(session, 'f1-sale', 'f1', 2025, 100.0)
        session.commit()

    result = CustomerQueryService(
        sales_service=SalesAnnualComparisonService(db_engine=db_engine)
    ).run(
        'ventas 2025 de clientes indirectos de Gran Canaria, kg de mayor a menor'
    )

    assert [row[0] for row in result.rows] == ['Gran Canaria', 'Gran Canaria']
    assert [row[1] for row in result.rows] == ['102', '101']
    assert [row[3] for row in result.rows] == [20.0, 5.0]


def test_sales_customer_top_query_returns_global_top_and_requested_columns(tmp_path) -> None:
    db_engine = _sales_engine(tmp_path)
    with Session(db_engine) as session:
        session.add_all([
            Isla(isla_id='gc', provincia_id='p1', isla_nombre='Gran Canaria', isla_codigo='GC-TOP'),
            Isla(isla_id='fue', provincia_id='p1', isla_nombre='Fuerteventura', isla_codigo='FUE-TOP'),
            Cliente(cliente_id='c1', cliente_codigo=101, cliente_nombre_comercial='Cliente Bajo', cliente_direccion_isla_id='gc'),
            Cliente(cliente_id='c2', cliente_codigo=102, cliente_nombre_comercial='Cliente Medio', cliente_direccion_isla_id='fue'),
            Cliente(cliente_id='c3', cliente_codigo=103, cliente_nombre_comercial='Cliente Alto', cliente_direccion_isla_id='gc'),
            Cliente(cliente_id='c4', cliente_codigo=104, cliente_nombre_comercial='Cliente Maximo', cliente_direccion_isla_id='fue'),
            Cliente(cliente_id='c5', cliente_codigo=105, cliente_nombre_comercial='Cliente Cero', cliente_direccion_isla_id='gc'),
            Cliente(cliente_id='c6', cliente_codigo=106, cliente_nombre_comercial='Cliente Extra', cliente_direccion_isla_id='fue'),
        ])
        _add_sale(session, 'top-1', 'c1', 2025, 1.0)
        _add_sale(session, 'top-2', 'c2', 2025, 20.0)
        _add_sale(session, 'top-3', 'c3', 2025, 100.0)
        _add_sale(session, 'top-4', 'c4', 2025, 200.0)
        _add_sale(session, 'top-5', 'c5', 2025, 0.5)
        _add_sale(session, 'top-6', 'c6', 2025, 50.0)
        session.commit()

    result = CustomerQueryService(
        sales_service=SalesAnnualComparisonService(db_engine=db_engine)
    ).run('listado 5 clientes top ventas en 2025, campos: nombre, kg')

    assert result.headers == ['Nombre comercial', 'Kg']
    assert result.rows == [
        ['Cliente Maximo', 200.0],
        ['Cliente Alto', 100.0],
        ['Cliente Extra', 50.0],
        ['Cliente Medio', 20.0],
        ['Cliente Bajo', 1.0],
    ]
    assert 'orden: kg de mayor a menor' in result.interpretation


def test_sales_customer_comparison_query_returns_top_year_with_requested_columns(tmp_path) -> None:
    db_engine = _sales_engine(tmp_path)
    with Session(db_engine) as session:
        session.add_all([
            Cliente(cliente_id='c1', cliente_codigo=101, cliente_nombre_comercial='Cliente Bajo'),
            Cliente(cliente_id='c2', cliente_codigo=102, cliente_nombre_comercial='Cliente Medio'),
            Cliente(cliente_id='c3', cliente_codigo=103, cliente_nombre_comercial='Cliente Alto'),
            Cliente(cliente_id='c4', cliente_codigo=104, cliente_nombre_comercial='Cliente Maximo'),
            Cliente(cliente_id='c5', cliente_codigo=105, cliente_nombre_comercial='Cliente Cero'),
            Cliente(cliente_id='c6', cliente_codigo=106, cliente_nombre_comercial='Cliente Extra'),
        ])
        _add_sale(session, 'cmp-1-current', 'c1', 2025, 1.0)
        _add_sale(session, 'cmp-1-prev', 'c1', 2024, 10.0)
        _add_sale(session, 'cmp-2-current', 'c2', 2025, 20.0)
        _add_sale(session, 'cmp-2-prev', 'c2', 2024, 5.0)
        _add_sale(session, 'cmp-3-current', 'c3', 2025, 100.0)
        _add_sale(session, 'cmp-3-prev', 'c3', 2024, 90.0)
        _add_sale(session, 'cmp-4-current', 'c4', 2025, 200.0)
        _add_sale(session, 'cmp-4-prev', 'c4', 2024, 150.0)
        _add_sale(session, 'cmp-5-current', 'c5', 2025, 0.5)
        _add_sale(session, 'cmp-5-prev', 'c5', 2024, 1.0)
        _add_sale(session, 'cmp-6-current', 'c6', 2025, 50.0)
        _add_sale(session, 'cmp-6-prev', 'c6', 2024, 80.0)
        session.commit()

    result = CustomerQueryService(
        sales_service=SalesAnnualComparisonService(db_engine=db_engine)
    ).run(
        'listado 5 clientes top ventas en 2025 versus 2024, '
        'campos: nombre, kg 2025, kg 2024, diferencia kg'
    )

    assert result.title == 'Comparativa ventas 2025 vs 2024'
    assert result.headers == ['Nombre comercial', 'Kg 2025', 'Kg 2024', 'Dif. Kg']
    assert result.rows == [
        ['Cliente Maximo', 200.0, 150.0, 50.0],
        ['Cliente Alto', 100.0, 90.0, 10.0],
        ['Cliente Extra', 50.0, 80.0, -30.0],
        ['Cliente Medio', 20.0, 5.0, 15.0],
        ['Cliente Bajo', 1.0, 10.0, -9.0],
    ]
    assert 'Comparativa 2025 vs 2024' in result.interpretation
    assert 'orden: kg 2025 de mayor a menor' in result.interpretation


def test_zero_consumption_includes_customers_without_sales_and_excludes_positive_sales(tmp_path) -> None:
    db_engine = _sales_engine(tmp_path)
    with Session(db_engine) as session:
        session.add_all([
            Isla(isla_id='gc', provincia_id='p1', isla_nombre='Gran Canaria', isla_codigo='GC0'),
            Isla(isla_id='fue', provincia_id='p1', isla_nombre='Fuerteventura', isla_codigo='FUE0'),
            Cliente(cliente_id='no-sales', cliente_codigo=201, cliente_nombre_comercial='Sin movimientos', cliente_direccion_isla_id='gc'),
            Cliente(cliente_id='zero-sum', cliente_codigo=202, cliente_nombre_comercial='Suma cero', cliente_direccion_isla_id='gc'),
            Cliente(cliente_id='positive', cliente_codigo=203, cliente_nombre_comercial='Medio kilo', cliente_direccion_isla_id='gc'),
            Cliente(cliente_id='other-island', cliente_codigo=204, cliente_nombre_comercial='Otra isla', cliente_direccion_isla_id='fue'),
        ])
        _add_sale(session, 'z1', 'zero-sum', 2025, 2.0)
        _add_sale(session, 'z2', 'zero-sum', 2025, -2.0)
        _add_sale(session, 'p1', 'positive', 2025, 0.5)
        session.commit()

    result = CustomerQueryService(
        sales_service=SalesAnnualComparisonService(db_engine=db_engine)
    ).run(
        'dame el listado de los clientes de gran canaria con consumo 0 en el 2025, '
        'campos, isla, cod, nombre, kg'
    )

    assert result.status == 'ready'
    assert [row[1] for row in result.rows] == ['201', '202']
    assert all(row[0] == 'Gran Canaria' for row in result.rows)
    assert all(row[3] == pytest.approx(0.0) for row in result.rows)


def test_customer_report_ai_format_is_strict_and_allowlisted() -> None:
    assert CUSTOMER_REPORT_RESPONSE_FORMAT["type"] == "json_schema"
    assert CUSTOMER_REPORT_RESPONSE_FORMAT["strict"] is True
    schema = CUSTOMER_REPORT_RESPONSE_FORMAT["schema"]
    assert schema["additionalProperties"] is False
    assert "actividad" in schema["properties"]["columns"]["items"]["enum"]
