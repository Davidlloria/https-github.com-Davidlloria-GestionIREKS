from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services.customer_ai_summary_service import CUSTOMER_AI_SUMMARY_SCHEMA, CustomerAISummaryService


class _FakeCustomerService:
    def __init__(self) -> None:
        self.periods = []

    def related_sales_years(self):
        return [2025, 2026]

    def related_sales_latest_month(self, year: int):
        assert year == 2026
        return 7

    def related_sales_months(self, _customer_id: str, year: int):
        assert year == 2025
        return (1, 2, 3, 4, 5, 6, 7)

    def related_sales(self, _customer_id: str, year: int, *, month_from: int, month_to: int):
        assert year == 2026
        self.periods.append((month_from, month_to))
        return [
            SimpleNamespace(codigo="A", nombre="Producto principal", kg_prev=100.0, kg_curr=60.0, euros_curr=300.0),
            SimpleNamespace(codigo="B", nombre="Producto perdido", kg_prev=30.0, kg_curr=0.0, euros_curr=0.0),
            SimpleNamespace(codigo="C", nombre="Producto nuevo", kg_prev=0.0, kg_curr=20.0, euros_curr=80.0),
        ]

    def related_contacts(self, _customer_id: str):
        return []

    def related_recipes(self, _customer_id: str):
        return [SimpleNamespace(nombre="Receta")]

    def related_agenda(self, _customer_id: str):
        return [SimpleNamespace(fecha_actividad=date.today() - timedelta(days=120))]


class _DisabledLocalAI:
    enabled = False


class _EnabledLocalAI:
    enabled = True

    def generate_json(self, prompt: str, *, schema: dict, max_tokens: int):
        self.prompt = prompt
        self.schema = schema
        self.max_tokens = max_tokens
        return SimpleNamespace(
            ok=True,
            text=(
                '{"situation":"Cliente activo.","sales":"El volumen desciende.",'
                '"products":["Producto perdido requiere revisión."],'
                '"opportunities":["Contactar al cliente."],"conclusion":"Priorizar seguimiento."}'
            ),
            message="IA local",
        )


class _InvalidLocalAI:
    enabled = True

    def generate_json(self, _prompt: str, *, schema: dict, max_tokens: int):
        assert schema == CUSTOMER_AI_SUMMARY_SCHEMA
        assert max_tokens == 700
        return SimpleNamespace(ok=True, text="respuesta sin JSON", message="IA local")


class _AnnualPreviousCustomerService(_FakeCustomerService):
    def related_sales_months(self, _customer_id: str, year: int):
        assert year == 2025
        return (12,)

    def related_sales(self, _customer_id: str, year: int, *, month_from: int, month_to: int):
        assert year == 2026
        self.periods.append((month_from, month_to))
        previous = 30307.0 if month_to == 12 else 0.0
        return [
            SimpleNamespace(
                codigo="A",
                nombre="Producto principal",
                kg_prev=previous,
                kg_curr=18456.0,
                euros_curr=85585.45,
            )
        ]


def _customer():
    return SimpleNamespace(
        cliente_id="customer-1",
        cliente_nombre_comercial="Panadería Ejemplo",
        cliente_nombre_fiscal="",
        cliente_tipo="indirecto",
        cliente_actividad="PANADERIA",
        activo=True,
    )


def test_customer_summary_calculates_real_sales_and_opportunities() -> None:
    customer_service = _FakeCustomerService()
    result = CustomerAISummaryService(
        customer_service=customer_service,
        local_ai_service=_DisabledLocalAI(),
    ).summarize(_customer())

    assert result.ok is True
    assert result.used_ai is False
    assert result.snapshot is not None
    assert result.snapshot.kg_current == pytest.approx(80.0)
    assert result.snapshot.kg_previous == pytest.approx(130.0)
    assert result.snapshot.delta_kg == pytest.approx(-50.0)
    assert result.snapshot.delta_kg_pct == pytest.approx(-38.461538)
    assert result.snapshot.month_to == 7
    assert result.snapshot.period_label == "enero–julio 2026 frente a enero–julio 2025"
    assert customer_service.periods == [(1, 7)]
    assert result.snapshot.comparison_available is True
    assert result.snapshot.contact_count == 0
    assert result.snapshot.recipe_count == 1
    assert result.snapshot.stopped_products == ("B · Producto perdido: 30,00 kg",)
    assert any("caída" in item for item in result.snapshot.opportunities)
    assert any("contacto" in item for item in result.snapshot.opportunities)
    assert any("90 días" in item for item in result.snapshot.opportunities)
    assert "80,00" in result.text
    assert "Producto perdido" in result.text


def test_customer_summary_asks_ai_only_to_explain_calculated_context() -> None:
    local_ai = _EnabledLocalAI()
    result = CustomerAISummaryService(
        customer_service=_FakeCustomerService(),
        local_ai_service=local_ai,
    ).summarize(_customer())

    assert result.ok is True
    assert result.used_ai is True
    assert result.sections is not None
    assert result.sections.situation == "Cliente activo."
    assert result.sections.opportunities == ("Contactar al cliente.",)
    assert "Situación" in result.text
    assert "**" not in result.text
    assert "No inventes" in local_ai.prompt
    assert "Producto perdido" in local_ai.prompt
    assert "80,00" in local_ai.prompt
    assert "enero–julio 2026" in local_ai.prompt
    assert local_ai.schema == CUSTOMER_AI_SUMMARY_SCHEMA
    assert local_ai.max_tokens == 700


def test_customer_summary_keeps_annual_reference_without_false_variation() -> None:
    customer_service = _AnnualPreviousCustomerService()
    result = CustomerAISummaryService(
        customer_service=customer_service,
        local_ai_service=_DisabledLocalAI(),
    ).summarize(_customer())

    assert result.ok is True
    assert result.snapshot is not None
    assert customer_service.periods == [(1, 7), (1, 12)]
    assert result.snapshot.kg_current == pytest.approx(18456.0)
    assert result.snapshot.kg_previous == pytest.approx(30307.0)
    assert result.snapshot.comparison_available is False
    assert result.snapshot.delta_kg is None
    assert result.snapshot.delta_kg_pct is None
    assert result.snapshot.stopped_products == ()
    assert result.snapshot.declining_products == ()
    assert "referencia anual 2025 no comparable" in result.snapshot.period_label
    assert "30.307,00" in result.text
    assert "no se calcula una variación comparable" in result.text
    assert "No se evalúan abandonos" in result.text


def test_customer_summary_falls_back_when_ai_json_is_invalid() -> None:
    result = CustomerAISummaryService(
        customer_service=_FakeCustomerService(),
        local_ai_service=_InvalidLocalAI(),
    ).summarize(_customer())

    assert result.ok is True
    assert result.used_ai is False
    assert result.sections is not None
    assert "formato esperado" in result.message
    assert "Producto perdido" in result.text


def test_customer_summary_requires_a_selected_customer() -> None:
    result = CustomerAISummaryService(
        customer_service=_FakeCustomerService(),
        local_ai_service=_DisabledLocalAI(),
    ).summarize(SimpleNamespace(cliente_id=""))

    assert result.ok is False
    assert "Selecciona" in result.message
