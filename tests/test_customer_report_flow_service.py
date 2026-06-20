from __future__ import annotations

from dataclasses import dataclass
import json

import pytest

import app.services.customer_report_service as customer_report_service_module
from app.services.customer_report_flow_service import CustomerReportFlowService
from app.services.customer_report_service import CustomerReportIntent, CustomerReportResult, ReportIntentResult


@dataclass
class _FakeIntentService:
    result: ReportIntentResult

    def parse(self, prompt: str) -> ReportIntentResult:
        self.prompt = prompt
        return self.result


@dataclass
class _FakeReportService:
    result: CustomerReportResult

    def run(self, intent: CustomerReportIntent) -> CustomerReportResult:
        self.intent = intent
        return self.result


def _report() -> CustomerReportResult:
    return CustomerReportResult(
        title="Listado de clientes",
        headers=["Cod.", "Nombre"],
        rows=[["1", "Cliente"]],
        intent=CustomerReportIntent(),
    )


def _empty_report() -> CustomerReportResult:
    return CustomerReportResult(
        title="Listado de clientes",
        headers=["Cod.", "Nombre"],
        rows=[],
        intent=CustomerReportIntent(),
    )


def test_generate_report_empty_prompt_returns_empty_status() -> None:
    service = CustomerReportFlowService(_FakeIntentService(ReportIntentResult(True, CustomerReportIntent(), "x")), _FakeReportService(_report()))

    result = service.generate_report("")

    assert result.status == "empty"
    assert result.message == "Escribe que listado necesitas."
    assert service.last_report is None


def test_generate_report_valid_prompt_uses_intent_and_report_services() -> None:
    intent = CustomerReportIntent(title="Listado", columns=["codigo"])
    intent_result = ReportIntentResult(True, intent, "Generado con interpretacion local.", False)
    report = _report()
    service = CustomerReportFlowService(_FakeIntentService(intent_result), _FakeReportService(report))

    result = service.generate_report("clientes activos")

    assert result.status == "ready"
    assert result.report == report
    assert result.source == "interprete local"
    assert service.last_report == report


def test_generate_report_empty_results_returns_empty_status_with_report() -> None:
    intent = CustomerReportIntent(title="Listado", columns=["codigo"])
    intent_result = ReportIntentResult(True, intent, "Generado con interpretacion local.", False)
    report = _empty_report()
    service = CustomerReportFlowService(_FakeIntentService(intent_result), _FakeReportService(report))

    result = service.generate_report("clientes")

    assert result.status == "empty"
    assert result.report == report
    assert result.message == "No se encontraron resultados."
    assert service.last_report == report


def test_generate_report_propagates_parse_error_status() -> None:
    intent_result = ReportIntentResult(False, CustomerReportIntent(), "Escribe que listado necesitas.")
    service = CustomerReportFlowService(_FakeIntentService(intent_result), _FakeReportService(_report()))

    result = service.generate_report("algo")

    assert result.status == "error"
    assert result.message == "Escribe que listado necesitas."
    assert service.last_report is None


def test_generate_report_propagates_run_error_status() -> None:
    class _BrokenReportService:
        def run(self, intent: CustomerReportIntent) -> CustomerReportResult:
            raise RuntimeError("boom")

    service = CustomerReportFlowService(_FakeIntentService(ReportIntentResult(True, CustomerReportIntent(), "ok", True)), _BrokenReportService())

    result = service.generate_report("clientes")

    assert result.status == "error"
    assert "boom" in result.message
    assert service.last_report is None


def test_has_last_report_reflects_state() -> None:
    intent = CustomerReportIntent(title="Listado", columns=["codigo"])
    intent_result = ReportIntentResult(True, intent, "Generado con interpretacion local.", False)
    report = _report()
    service = CustomerReportFlowService(_FakeIntentService(intent_result), _FakeReportService(report))

    assert service.has_last_report() is False
    service.generate_report("clientes")
    assert service.has_last_report() is True


def test_intent_service_ignores_inherited_proxy_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_handlers: list[object] = []

    class _FakeResponse:
        def __init__(self, body: str) -> None:
            self._body = body.encode("utf-8")

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return self._body

    class _FakeOpener:
        def open(self, req, timeout=None) -> _FakeResponse:
            body = json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "title": "Listado de clientes",
                            "columns": ["codigo", "nombre_comercial"],
                            "filters": [],
                            "order_by": ["codigo"],
                            "limit": 50,
                        }
                    )
                }
            )
            return _FakeResponse(body)

    def _fake_build_opener(handler):
        captured_handlers.append(handler)
        return _FakeOpener()

    monkeypatch.setattr(customer_report_service_module, "build_opener", _fake_build_opener)
    monkeypatch.setattr(customer_report_service_module.OpenAISettingsService, "load", lambda self: {"api_key": "test-key", "use_ai_translation": False})

    service = customer_report_service_module.CustomerReportIntentService()
    result = service.parse("clientes activos")

    assert result.used_ai is True
    assert captured_handlers
    assert captured_handlers[0].proxies == {}
