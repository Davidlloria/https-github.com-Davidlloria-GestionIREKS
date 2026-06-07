from __future__ import annotations

from dataclasses import dataclass

from app.services.customer_report_service import (
    CustomerReportIntentService,
    CustomerReportResult,
    CustomerReportService,
    ReportIntentResult,
)


@dataclass
class CustomerReportFlowResult:
    status: str
    message: str = ""
    report: CustomerReportResult | None = None
    source: str = ""
    used_ai: bool = False


class CustomerReportFlowService:
    def __init__(
        self,
        intent_service: CustomerReportIntentService | None = None,
        report_service: CustomerReportService | None = None,
    ) -> None:
        self.intent_service = intent_service or CustomerReportIntentService()
        self.report_service = report_service or CustomerReportService()
        self.last_report: CustomerReportResult | None = None
        self.last_result: CustomerReportFlowResult = CustomerReportFlowResult(status="idle")

    def generate_report(self, prompt: str) -> CustomerReportFlowResult:
        text = str(prompt or "").strip()
        if not text:
            result = CustomerReportFlowResult(status="empty", message="Escribe que listado necesitas.")
            self.last_report = None
            self.last_result = result
            return result

        intent_result = self.intent_service.parse(text)
        if not intent_result.ok:
            result = CustomerReportFlowResult(status="error", message=intent_result.message)
            self.last_report = None
            self.last_result = result
            return result

        try:
            report = self.report_service.run(intent_result.intent)
        except Exception as exc:  # noqa: BLE001
            result = CustomerReportFlowResult(status="error", message=f"No se pudo generar el listado.\n{exc}")
            self.last_report = None
            self.last_result = result
            return result

        self.last_report = report
        if not report.rows:
            result = CustomerReportFlowResult(
                status="empty",
                message="No se encontraron resultados.",
                report=report,
                source="ChatGPT" if intent_result.used_ai else "interprete local",
                used_ai=bool(intent_result.used_ai),
            )
            self.last_result = result
            return result
        result = CustomerReportFlowResult(
            status="ready",
            message=intent_result.message,
            report=report,
            source="ChatGPT" if intent_result.used_ai else "interprete local",
            used_ai=bool(intent_result.used_ai),
        )
        self.last_result = result
        return result

    def has_last_report(self) -> bool:
        return self.last_report is not None
