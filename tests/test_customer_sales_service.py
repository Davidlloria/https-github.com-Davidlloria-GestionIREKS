from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from app.services.customer_service import CustomerService
from app.ui.widgets.customers_page import _NumericTableWidgetItem, _has_current_sales_activity


@dataclass
class _SalesRow:
    codigo: str = "D123"
    kg_curr: float = 0.0


class _FakeSalesSummaryService:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, int, int]] = []
        self.annual_series_calls: list[tuple[str, int]] = []

    def list_years_clientes(self) -> list[int]:
        return [2026, 2025]

    def listar_resumen_anual_clientes(self, *, year: int, cliente_id: str, month_from: int = 1, month_to: int = 12):
        self.calls.append((year, cliente_id, month_from, month_to))
        return [_SalesRow()]

    def annual_kg_series_clientes(self, cliente_id: str, end_year: int) -> list[tuple[int, float]]:
        self.annual_series_calls.append((cliente_id, end_year))
        return [(year, float(year - 2020) + 0.5) for year in range(end_year - 3, end_year + 1)]

    def listar_ventas_mensuales_cliente_producto(self, **kwargs):
        self.monthly_call = kwargs
        return ["monthly-row"]


def _service_with_fake_sales() -> tuple[CustomerService, _FakeSalesSummaryService]:
    service = CustomerService.__new__(CustomerService)
    fake = _FakeSalesSummaryService()
    service.sales_summary_service = fake
    return service, fake


def test_related_sales_years_delegates_to_sales_summary() -> None:
    service, _fake = _service_with_fake_sales()

    assert service.related_sales_years() == [2026, 2025]


def test_related_sales_filters_by_selected_customer_and_year() -> None:
    service, fake = _service_with_fake_sales()

    rows = service.related_sales(" cliente-1 ", 2026, month_from=2, month_to=8)

    assert [row.codigo for row in rows] == ["D123"]
    assert fake.calls == [(2026, "cliente-1", 2, 8)]


def test_related_sales_rejects_empty_customer_or_invalid_year() -> None:
    service, fake = _service_with_fake_sales()

    assert service.related_sales("", 2026) == []
    assert service.related_sales("cliente-1", 0) == []
    assert fake.calls == []


def test_related_sales_annual_kg_series_returns_four_ascending_years() -> None:
    service, fake = _service_with_fake_sales()

    points = service.related_sales_annual_kg_series(" cliente-1 ", 2026)

    assert [(point.year, point.kg) for point in points] == [
        (2023, 3.5),
        (2024, 4.5),
        (2025, 5.5),
        (2026, 6.5),
    ]
    assert fake.annual_series_calls == [("cliente-1", 2026)]


def test_related_sales_annual_kg_series_rejects_missing_context() -> None:
    service, fake = _service_with_fake_sales()

    assert service.related_sales_annual_kg_series("", 2026) == []
    assert service.related_sales_annual_kg_series("cliente-1", 0) == []
    assert fake.calls == []


def test_current_sales_activity_excludes_previous_period_only_articles() -> None:
    previous_period_only = SimpleNamespace(unidades_curr=0, kg_curr=0, euros_curr=0, unidades_prev=4)
    current_amount_without_units = SimpleNamespace(unidades_curr=0, kg_curr=3.5, euros_curr=12.0)

    assert not _has_current_sales_activity(previous_period_only)
    assert _has_current_sales_activity(current_amount_without_units)


def test_related_sales_monthly_product_delegates_with_customer_and_product_ids() -> None:
    service, fake = _service_with_fake_sales()

    rows = service.related_sales_monthly_product(" cliente-1 ", 2026, articulo_id="art-1", articulo_codigo="D123")

    assert rows == ["monthly-row"]
    assert fake.monthly_call == {
        "year": 2026,
        "cliente_id": "cliente-1",
        "articulo_id": "art-1",
        "articulo_codigo": "D123",
    }


def test_numeric_table_items_sort_by_their_numeric_value() -> None:
    twelve = _NumericTableWidgetItem("12,00 kg", 12.0)
    three = _NumericTableWidgetItem("3,00 kg", 3.0)

    assert not (twelve < three)
    assert three < twelve
