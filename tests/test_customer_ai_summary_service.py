from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.services.customer_ai_summary_service import CustomerAISummaryService


class _FakeCustomerService:
    def related_sales_years(self):
        return [2025, 2026]

    def related_sales(self, _customer_id: str, year: int):
        assert year == 2026
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

    def generate_process(self, prompt: str):
        self.prompt = prompt
        return SimpleNamespace(ok=True, text="Resumen redactado con datos reales.", message="IA local")


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
    result = CustomerAISummaryService(
        customer_service=_FakeCustomerService(),
        local_ai_service=_DisabledLocalAI(),
    ).summarize(_customer())

    assert result.ok is True
    assert result.used_ai is False
    assert result.snapshot is not None
    assert result.snapshot.kg_current == pytest.approx(80.0)
    assert result.snapshot.kg_previous == pytest.approx(130.0)
    assert result.snapshot.delta_kg == pytest.approx(-50.0)
    assert result.snapshot.delta_kg_pct == pytest.approx(-38.461538)
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
    assert result.text == "Resumen redactado con datos reales."
    assert "No inventes" in local_ai.prompt
    assert "Producto perdido" in local_ai.prompt
    assert "80,00" in local_ai.prompt


def test_customer_summary_requires_a_selected_customer() -> None:
    result = CustomerAISummaryService(
        customer_service=_FakeCustomerService(),
        local_ai_service=_DisabledLocalAI(),
    ).summarize(SimpleNamespace(cliente_id=""))

    assert result.ok is False
    assert "Selecciona" in result.message
