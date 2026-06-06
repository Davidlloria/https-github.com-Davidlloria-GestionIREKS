from __future__ import annotations

from app.services.product_report_flow_service import ProductReportFlowService
from app.services.product_report_service import (
    ProductReportIntent,
    ProductReportIntentResult,
    ProductReportResult,
)


class _FakeIntentService:
    def __init__(self, result: ProductReportIntentResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def parse(self, prompt: str) -> ProductReportIntentResult:
        self.calls.append(prompt)
        return self.result


class _FakeReportService:
    def __init__(self, *, result: ProductReportResult | None = None, exc: Exception | None = None) -> None:
        self.result = result
        self.exc = exc
        self.calls: list[ProductReportIntent] = []

    def run(self, intent: ProductReportIntent) -> ProductReportResult:
        self.calls.append(intent)
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result


def _intent_result(*, ok: bool, message: str = "", used_ai: bool = False) -> ProductReportIntentResult:
    return ProductReportIntentResult(ok, ProductReportIntent(), message, used_ai)


def _report(selected_ids: list[int] | None = None) -> ProductReportResult:
    intent = ProductReportIntent(selected_ids=list(selected_ids or []))
    return ProductReportResult(
        title="Listado de productos IREKS",
        headers=["Referencia", "Descripcion"],
        rows=[["A1", "Harina"]],
        intent=intent,
    )


def test_generate_report_returns_empty_prompt_without_services() -> None:
    fake_intent = _FakeIntentService(_intent_result(ok=True))
    fake_report = _FakeReportService(result=_report())
    service = ProductReportFlowService(intent_service=fake_intent, report_service=fake_report)

    result = service.generate_report("   ")

    assert result.status == "empty_prompt"
    assert result.message == "Escribe que listado necesitas."
    assert result.report is None
    assert fake_intent.calls == []
    assert fake_report.calls == []


def test_generate_report_returns_parse_error_without_running_report() -> None:
    fake_intent = _FakeIntentService(_intent_result(ok=False, message="No se pudo interpretar."))
    fake_report = _FakeReportService(result=_report())
    service = ProductReportFlowService(intent_service=fake_intent, report_service=fake_report)

    result = service.generate_report("listado raro")

    assert result.status == "parse_error"
    assert result.message == "No se pudo interpretar."
    assert result.report is None
    assert fake_intent.calls == ["listado raro"]
    assert fake_report.calls == []


def test_generate_report_returns_no_selection_for_selected_prompt_without_ids() -> None:
    fake_intent = _FakeIntentService(_intent_result(ok=True, message="Interpretado localmente.", used_ai=False))
    fake_report = _FakeReportService(result=_report())
    service = ProductReportFlowService(intent_service=fake_intent, report_service=fake_report)

    result = service.generate_report("Listado de productos seleccionados", selected_product_ids=[])

    assert result.status == "no_selection"
    assert result.message == "No hay productos seleccionados en la lista."
    assert result.report is None
    assert fake_intent.calls == ["Listado de productos seleccionados"]
    assert fake_report.calls == []


def test_generate_report_returns_ready_with_selected_ids_and_pure_fakes() -> None:
    fake_intent = _FakeIntentService(_intent_result(ok=True, message="Generado con ChatGPT.", used_ai=True))
    fake_report = _FakeReportService(result=_report([2, 3]))
    service = ProductReportFlowService(intent_service=fake_intent, report_service=fake_report)

    result = service.generate_report(
        "Listado de productos seleccionados",
        selected_product_ids=[3, 2, 3, "2", 0, -1, "x"],
    )

    assert result.status == "ready"
    assert result.message == "Generado con ChatGPT."
    assert result.used_ai is True
    assert result.report is not None
    assert result.report.intent.selected_ids == [2, 3]
    assert fake_intent.calls == ["Listado de productos seleccionados"]
    assert fake_report.calls
    assert fake_report.calls[0].selected_ids == [2, 3]


def test_generate_report_returns_error_when_report_service_raises() -> None:
    fake_intent = _FakeIntentService(_intent_result(ok=True, message="Interpretado localmente.", used_ai=False))
    fake_report = _FakeReportService(exc=RuntimeError("fallo db"))
    service = ProductReportFlowService(intent_service=fake_intent, report_service=fake_report)

    result = service.generate_report("Listado de productos")

    assert result.status == "error"
    assert result.message == "No se pudo generar el listado.\nfallo db"
    assert result.report is None
    assert fake_intent.calls == ["Listado de productos"]
    assert len(fake_report.calls) == 1
