from __future__ import annotations

from dataclasses import dataclass
import json

import app.services.customer_report_service as customer_report_service_module
from app.services.customer_report_schema import CUSTOMER_REPORT_RESPONSE_FORMAT
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


class _DisabledLocalAI:
    enabled = False


class _UnavailableLocalAI:
    enabled = True

    def generate_json(self, prompt: str, *, schema: dict | None = None):
        return type("Result", (), {"ok": False, "text": ""})()


class _FakeLocalAI:
    enabled = True

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.schemas: list[dict | None] = []

    def generate_json(self, prompt: str, *, schema: dict | None = None):
        self.prompts.append(prompt)
        self.schemas.append(schema)
        return type(
            "Result",
            (),
            {
                "ok": True,
                "text": json.dumps(
                    {
                        "title": "Clientes activos",
                        "columns": ["codigo", "nombre_comercial"],
                        "filters": [{"field": "activo", "op": "=", "value": True}],
                        "order_by": ["codigo"],
                        "limit": 50,
                    }
                ),
            },
        )()


class _DisabledOpenAI:
    def generate_process(self, prompt: str):
        return type("Result", (), {"ok": False, "text": ""})()


class _FakeOpenAI:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_process(self, prompt: str):
        self.prompts.append(prompt)
        return type(
            "Result",
            (),
            {
                "ok": True,
                "text": json.dumps(
                    {
                        "title": "Clientes activos",
                        "columns": ["codigo", "nombre_comercial"],
                        "filters": [{"field": "activo", "op": "=", "value": True}],
                        "order_by": ["codigo"],
                        "limit": 50,
                    }
                ),
            },
        )()


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
    assert result.message == "No se pudo generar el listado."
    assert service.last_report is None


def test_has_last_report_reflects_state() -> None:
    intent = CustomerReportIntent(title="Listado", columns=["codigo"])
    intent_result = ReportIntentResult(True, intent, "Generado con interpretacion local.", False)
    report = _report()
    service = CustomerReportFlowService(_FakeIntentService(intent_result), _FakeReportService(report))

    assert service.has_last_report() is False
    service.generate_report("clientes")
    assert service.has_last_report() is True


def test_intent_service_uses_deterministic_fallback_when_local_ai_is_disabled() -> None:
    service = customer_report_service_module.CustomerReportIntentService(
        local_ai_service=_DisabledLocalAI(),
        openai_service=_DisabledOpenAI(),
    )
    result = service.parse(
        "listado de todos los clientes, campos uuid, cod, codigo cliente distribuidor, nombre"
    )

    assert result.used_ai is False
    assert result.provider == "deterministic"
    assert result.intent.limit == 5000
    assert result.intent.filters == []


def test_intent_service_prefers_enabled_local_ai_and_keeps_reports_read_only() -> None:
    local_ai = _FakeLocalAI()
    openai = _FakeOpenAI()
    service = customer_report_service_module.CustomerReportIntentService(
        api_key="cloud-key",
        local_ai_service=local_ai,
        openai_service=openai,
    )

    result = service.parse("listado de clientes activos")

    assert result.ok is True
    assert result.used_ai is True
    assert result.provider == "local_ai"
    assert result.intent.filters[0] == customer_report_service_module.ReportFilter("activo", "=", True)
    assert local_ai.prompts
    assert "No generes SQL" in local_ai.prompts[0]
    assert local_ai.schemas == [CUSTOMER_REPORT_RESPONSE_FORMAT["schema"]]
    assert openai.prompts == []


def test_intent_service_uses_openai_when_local_ai_is_unavailable() -> None:
    openai = _FakeOpenAI()
    service = customer_report_service_module.CustomerReportIntentService(
        local_ai_service=_UnavailableLocalAI(),
        openai_service=openai,
    )

    result = service.parse("listado de clientes activos")

    assert result.ok is True
    assert result.used_ai is True
    assert result.provider == "openai"
    assert result.intent.filters[0] == customer_report_service_module.ReportFilter("activo", "=", True)
    assert openai.prompts
    assert "No generes SQL" in openai.prompts[0]


def test_report_flow_labels_local_ai_as_the_active_provider() -> None:
    intent = CustomerReportIntent(columns=["codigo", "nombre_comercial"])
    intent_result = ReportIntentResult(True, intent, "Generado con IA local.", True, "local_ai")
    flow = CustomerReportFlowService(_FakeIntentService(intent_result), _FakeReportService(_report()))

    result = flow.generate_report("clientes activos")

    assert result.status == "ready"
    assert result.source == "IA local"
