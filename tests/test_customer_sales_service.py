from __future__ import annotations

from dataclasses import dataclass

from app.services.customer_service import CustomerService


@dataclass
class _SalesRow:
    codigo: str = "D123"


class _FakeSalesSummaryService:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, int, int]] = []

    def list_years_clientes(self) -> list[int]:
        return [2026, 2025]

    def listar_resumen_anual_clientes(self, *, year: int, cliente_id: str, month_from: int = 1, month_to: int = 12):
        self.calls.append((year, cliente_id, month_from, month_to))
        return [_SalesRow()]


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
